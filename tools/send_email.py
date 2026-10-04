from __future__ import annotations

import os, smtplib, ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.memory import recent_episodes


def main() -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    to = os.environ["EMAIL_TO"]
    episodes = recent_episodes(7)
    sections = []
    for e in episodes[-40:]:
        sections.append(
            f"{e.get('timestamp')} — {e.get('title')}\n"
            f"{e.get('summary','')}\n"
            f"Facts: {'; '.join(e.get('facts', [])[:5])}\n"
            f"Open loops: {'; '.join(e.get('open_loops', [])[:5])}\n"
            f"Sources: {'; '.join(s.get('url','') for s in e.get('sources', [])[:5])}"
        )
    body = "AUTONOMOUS RESEARCH — LAST 7 DAYS\n\n" + ("\n\n---\n\n".join(sections) if sections else "No runs were recorded.")
    body += "\n\nNote: this digest is generated directly from the persisted research records."
    msg = EmailMessage()
    msg["Subject"] = f"Autonomous Research Digest — {datetime.now(timezone.utc).date().isoformat()}"
    msg["From"] = user; msg["To"] = to; msg.set_content(body[:50000])
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30) as s:
            s.login(user, password); s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.ehlo(); s.starttls(context=ssl.create_default_context()); s.ehlo(); s.login(user, password); s.send_message(msg)
    print(f"sent digest with {len(episodes)} episodes")

if __name__ == "__main__":
    main()
