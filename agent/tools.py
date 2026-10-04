from __future__ import annotations

import email.utils
import html
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from agent.memory import cache_source, search

ROOT = Path(__file__).resolve().parents[1]
MAX_TEXT = 12000
UA = "free-autonomous-research-agent/2.0"


def _clip(v: Any, n: int = MAX_TEXT) -> str:
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=2)
    return s if len(s) <= n else s[:n] + "\n...[truncated]"


def _get(url: str, timeout: int = 20, max_bytes: int = 900_000, headers: dict[str, str] | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(max_bytes)


def _normalize_url(url: str) -> str:
    try:
        p = urllib.parse.urlsplit(url)
        return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", p.query, ""))
    except Exception:
        return url


class SearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[dict[str, str]] = []
        self.current: dict[str, str] | None = None
        self.in_title = False
        self.in_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = dict(attrs)
        cls = d.get("class") or ""
        if tag == "a" and "result__a" in cls:
            self.current = {"title": "", "url": d.get("href", "")}
            self.in_title = True
        elif self.current is not None and "result__snippet" in cls:
            self.in_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.in_title:
            self.in_title = False
        if self.in_snippet and tag in {"div", "span"}:
            self.in_snippet = False
            if self.current and self.current.get("url"):
                self.items.append(self.current)
                self.current = None

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            if self.in_title:
                self.current["title"] += data
            elif self.in_snippet:
                self.current["snippet"] = self.current.get("snippet", "") + data


def web_search(args: dict[str, Any]) -> str:
    q = str(args.get("query", "")).strip()
    limit = min(10, max(1, int(args.get("limit", 8))))
    if not q:
        raise ValueError("query is required")
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(q)
    raw = _get(url, timeout=25).decode("utf-8", errors="replace")
    p = SearchParser(); p.feed(raw)
    out, seen = [], set()
    for item in p.items:
        u = urllib.parse.unquote(html.unescape(item.get("url", "")))
        try:
            parsed = urllib.parse.urlsplit(u)
            qs = urllib.parse.parse_qs(parsed.query)
            if "uddg" in qs:
                u = qs["uddg"][0]
        except Exception:
            pass
        u = _normalize_url(u)
        if not u.startswith("http") or u in seen:
            continue
        seen.add(u)
        out.append({"title": html.unescape(item.get("title", "")).strip(), "url": u, "snippet": html.unescape(item.get("snippet", "")).strip(), "provider": "duckduckgo"})
        if len(out) >= limit:
            break
    cache_source("search", q.lower(), out)
    return _clip(out, 9000)


def web_get(args: dict[str, Any]) -> str:
    url = str(args.get("url", "")).strip()
    if not re.match(r"^https?://", url):
        raise ValueError("url must start with http:// or https://")
    body = _get(url, timeout=min(30, int(args.get("timeout", 20))), max_bytes=1_500_000).decode("utf-8", errors="replace")
    # Extract visible-ish content; preserve links with a tiny amount of structure.
    body = re.sub(r"<script[^>]*>.*?</script>", " ", body, flags=re.I | re.S)
    body = re.sub(r"<style[^>]*>.*?</style>", " ", body, flags=re.I | re.S)
    body = re.sub(r"<noscript[^>]*>.*?</noscript>", " ", body, flags=re.I | re.S)
    body = re.sub(r"<svg[^>]*>.*?</svg>", " ", body, flags=re.I | re.S)
    body = re.sub(r"<br\s*/?>", "\n", body, flags=re.I)
    body = re.sub(r"</(p|div|li|h[1-6]|article|section)>", "\n", body, flags=re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    text = html.unescape(body)
    text = re.sub(r"\s+", " ", text).strip()
    cache_source("page", _normalize_url(url), {"url": url, "text": text[:5000]})
    return _clip(text, min(MAX_TEXT, int(args.get("max_chars", MAX_TEXT))))


def _xml_text(elem: ET.Element | None, default: str = "") -> str:
    return "".join(elem.itertext()).strip() if elem is not None else default


def news_search(args: dict[str, Any]) -> str:
    q = str(args.get("query", "")).strip()
    limit = min(10, max(1, int(args.get("limit", 8))))
    if not q:
        raise ValueError("query is required")
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote_plus(q) + "&hl=en-US&gl=US&ceid=US:en"
    raw = _get(url, timeout=20).decode("utf-8", errors="replace")
    root = ET.fromstring(raw)
    out = []
    for item in root.findall(".//item")[:limit]:
        title = _xml_text(item.find("title"))
        link = _xml_text(item.find("link"))
        pub = _xml_text(item.find("pubDate"))
        source = _xml_text(item.find("source"))
        out.append({"title": title, "url": link, "published": pub, "source": source, "provider": "google-news-rss"})
    cache_source("news", q.lower(), out)
    return _clip(out, 9000)


def arxiv_search(args: dict[str, Any]) -> str:
    q = str(args.get("query", "")).strip()
    limit = min(10, max(1, int(args.get("limit", 8))))
    if not q:
        raise ValueError("query is required")
    url = "https://export.arxiv.org/api/query?search_query=all:" + urllib.parse.quote(q) + f"&start=0&max_results={limit}&sortBy=submittedDate&sortOrder=descending"
    root = ET.fromstring(_get(url, timeout=25).decode("utf-8", errors="replace"))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for entry in root.findall("a:entry", ns):
        out.append({
            "title": re.sub(r"\s+", " ", _xml_text(entry.find("a:title", ns))),
            "summary": re.sub(r"\s+", " ", _xml_text(entry.find("a:summary", ns)))[:1200],
            "url": next((x.attrib.get("href") for x in entry.findall("a:link", ns) if x.attrib.get("rel") == "alternate"), ""),
            "published": _xml_text(entry.find("a:published", ns)),
            "authors": [_xml_text(x) for x in entry.findall("a:author/a:name", ns)][:8],
            "provider": "arxiv",
        })
    cache_source("arxiv", q.lower(), out)
    return _clip(out, 10000)


def crossref_search(args: dict[str, Any]) -> str:
    q = str(args.get("query", "")).strip()
    limit = min(10, max(1, int(args.get("limit", 8))))
    if not q:
        raise ValueError("query is required")
    url = "https://api.crossref.org/works?query.bibliographic=" + urllib.parse.quote_plus(q) + f"&rows={limit}&select=DOI,title,author,published,URL,container-title"
    data = json.loads(_get(url, timeout=25, headers={"Accept": "application/json"}).decode("utf-8", errors="replace"))
    out = []
    for item in data.get("message", {}).get("items", []):
        out.append({"title": (item.get("title") or [""])[0], "doi": item.get("DOI"), "url": item.get("URL"), "published": item.get("published", {}).get("date-parts", [[""]])[0][0], "venue": (item.get("container-title") or [""])[0], "provider": "crossref"})
    cache_source("crossref", q.lower(), out)
    return _clip(out, 9000)


def github_api(args: dict[str, Any]) -> str:
    endpoint = str(args.get("endpoint", "")).strip()
    method = str(args.get("method", "GET")).upper()
    if not endpoint.startswith("/"):
        raise ValueError("endpoint must start with /")
    endpoint = endpoint.replace("{repo}", os.environ.get("GITHUB_REPOSITORY", ""))
    if not endpoint.startswith("/repos/") and endpoint not in {"/user", "/rate_limit"}:
        raise PermissionError("github_api is restricted to repository-scoped endpoints")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN unavailable")
    allowed_write = method == "POST" and (endpoint.endswith("/issues") or "/comments" in endpoint)
    if method not in {"GET", "POST"} or (method == "POST" and not allowed_write):
        raise PermissionError("only GET and issue/comment POST are allowed")
    body = args.get("body")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request("https://api.github.com" + endpoint, data=data, method=method, headers={
        "User-Agent": UA, "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    })
    raw = _get(req.full_url, timeout=30, max_bytes=600_000, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }) if method == "GET" else urllib.request.urlopen(req, timeout=30).read(600_000)
    return _clip(json.loads(raw.decode("utf-8", errors="replace")), 10000)


def github_search(args: dict[str, Any]) -> str:
    q = str(args.get("query", "")).strip()
    kind = str(args.get("kind", "repositories")).lower()
    limit = min(10, max(1, int(args.get("limit", 8))))
    if kind not in {"repositories", "issues", "code"}:
        raise ValueError("kind must be repositories, issues, or code")
    if not q:
        raise ValueError("query is required")
    endpoint = f"https://api.github.com/search/{kind}?q={urllib.parse.quote_plus(q)}&per_page={limit}"
    data = json.loads(_get(endpoint, timeout=25, headers={"Accept": "application/vnd.github+json"}).decode("utf-8", errors="replace"))
    out = []
    for item in data.get("items", [])[:limit]:
        out.append({"name": item.get("full_name") or item.get("title") or item.get("name"), "url": item.get("html_url"), "description": item.get("description"), "stars": item.get("stargazers_count"), "updated_at": item.get("updated_at"), "provider": "github"})
    cache_source("github", f"{kind}:{q.lower()}", out)
    return _clip(out, 9000)


def hackernews_search(args: dict[str, Any]) -> str:
    q = str(args.get("query", "")).strip()
    limit = min(10, max(1, int(args.get("limit", 8))))
    if not q:
        raise ValueError("query is required")
    url = "https://hn.algolia.com/api/v1/search?query=" + urllib.parse.quote_plus(q) + f"&tags=story&hitsPerPage={limit}"
    data = json.loads(_get(url, timeout=20).decode("utf-8", errors="replace"))
    out = [{"title": x.get("title"), "url": x.get("url") or f"https://news.ycombinator.com/item?id={x.get('objectID')}", "points": x.get("points"), "created_at": x.get("created_at"), "provider": "hacker-news"} for x in data.get("hits", [])[:limit]]
    cache_source("hackernews", q.lower(), out)
    return _clip(out, 9000)


def rss_fetch(args: dict[str, Any]) -> str:
    url = str(args.get("url", "")).strip()
    limit = min(30, max(1, int(args.get("limit", 20))))
    if not url:
        raise ValueError("url is required")
    raw = _get(url, timeout=20).decode("utf-8", errors="replace")
    root = ET.fromstring(raw)
    out = []
    # RSS
    for item in root.findall(".//item")[:limit]:
        out.append({"title": _xml_text(item.find("title")), "url": _xml_text(item.find("link")), "published": _xml_text(item.find("pubDate")), "provider": "rss"})
    # Atom
    if not out:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for e in root.findall("a:entry", ns)[:limit]:
            link = next((x.attrib.get("href") for x in e.findall("a:link", ns) if x.attrib.get("href")), "")
            out.append({"title": _xml_text(e.find("a:title", ns)), "url": link, "published": _xml_text(e.find("a:updated", ns)), "provider": "atom"})
    return _clip(out, 9000)


def file_read(args: dict[str, Any]) -> str:
    rel = str(args.get("path", ""))
    p = _workspace(rel)
    if not p.is_file():
        raise FileNotFoundError(rel)
    return _clip(p.read_text(encoding="utf-8", errors="replace"))


def file_list(args: dict[str, Any]) -> str:
    rel = str(args.get("path", "workspace"))
    p = _workspace(rel)
    if not p.is_dir():
        raise NotADirectoryError(rel)
    return json.dumps([{"path": x.relative_to(ROOT).as_posix(), "type": "dir" if x.is_dir() else "file"} for x in sorted(p.iterdir())[:200]], ensure_ascii=False)


def file_write(args: dict[str, Any]) -> str:
    rel = str(args.get("path", ""))
    p = _workspace(rel)
    relative = p.relative_to(ROOT).as_posix()
    if not relative.startswith("workspace/"):
        raise PermissionError("file_write is limited to workspace/")
    content = str(args.get("content", ""))
    if len(content) > 25000:
        raise ValueError("content exceeds 25000 characters")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"wrote {relative}"


def _workspace(rel: str) -> Path:
    p = (ROOT / rel).resolve()
    if p != ROOT and ROOT not in p.parents:
        raise ValueError("path escapes repository")
    return p


def repo_status(_: dict[str, Any]) -> str:
    return subprocess.check_output(["git", "status", "--short", "--branch"], cwd=ROOT, text=True)


def repo_log(args: dict[str, Any]) -> str:
    n = min(50, max(1, int(args.get("n", 10))))
    return subprocess.check_output(["git", "log", "--oneline", f"-{n}"], cwd=ROOT, text=True)


def shell(args: dict[str, Any]) -> str:
    command = str(args.get("command", "")).strip()
    if not command:
        raise ValueError("command is required")
    low = command.lower().strip()
    denied = [
        "github_token", "gh_token", "smtp_password", "smtp_user", "curl |", "wget |",
        "git push", "git remote", "git config", "ssh ", "scp ", "nc ", "netcat ",
        "rm ", "mv ", "cp ", "chmod ", "chown ", "mount ", "umount ", "sudo ",
        "systemctl ", "launchctl ", "docker ", "podman ", "python -c", "python3 -c",
        ":(){", "/etc/", "/var/", "/proc/", "/sys/", ".. /", "../",
    ]
    if any(x in low for x in denied) or re.search(r"(^|[;&|\s])(env|printenv|set)([;&|\s]|$)", low):
        raise PermissionError("command blocked by sandbox policy")
    allowed = (
        "ls", "find", "grep", "rg ", "sed ", "awk ", "cat ", "head ", "tail ", "wc ",
        "du ", "df ", "file ", "sha256sum ", "sort ", "uniq ", "cut ", "tr ",
        "date", "python3 ", "python ", "git status", "git log", "git diff", "git show",
    )
    if not low.startswith(allowed):
        raise PermissionError("shell is restricted to inspection/calculation commands")
    p = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=45)
    return _clip({"exit_code": p.returncode, "stdout": p.stdout, "stderr": p.stderr}, 9000)


def memory_search(args: dict[str, Any]) -> str:
    return _clip(search(str(args.get("query", "")), min(20, max(1, int(args.get("limit", 12))))), 10000)


TOOLS = {
    "memory_search": memory_search,
    "web_search": web_search,
    "web_get": web_get,
    "news_search": news_search,
    "arxiv_search": arxiv_search,
    "crossref_search": crossref_search,
    "github_search": github_search,
    "github_api": github_api,
    "hackernews_search": hackernews_search,
    "rss_fetch": rss_fetch,
    "file_read": file_read,
    "file_list": file_list,
    "file_write": file_write,
    "repo_status": repo_status,
    "repo_log": repo_log,
    "shell": shell,
}
