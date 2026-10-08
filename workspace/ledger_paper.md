# Ledger: Persistent 3D Object Memory from Egocentric Videos

## Problem
Embodied agents need to remember objects they encounter, even when they leave the view or are never touched. Objects may become relevant only later.

## Method
Ledger combines:
- Object locations (3D spatial tracking)
- Object histories (movement patterns)
- Contextual descriptions (what objects are, where they're placed)

## Supervision
- Temporal persistence: objects retained after leaving view
- Contextual descriptions: preserve details like contents or supporting surface
- Retrieval: answer spatial questions without accessing original images/video

## Memory Architecture
- Clusters observations by resting locations
- Records moves only after repeated evidence (reduces localization noise)
- Saves records to later answer questions

## Retrieval
- Spatial queries answered from stored records
- No need to access original video/images

## Update
- Move recorded only after repeated evidence
- Per-scene construction partially recovers performance lost across scene changes

## Evaluation
- HD-EPIC accuracy: 29.7% → 42.6% (+12.9%)
- UCS-Bench accuracy: 33.8% → 38.5% (+4.7%)
- Ego4D localization: 0.99m median error

## Ablation
- Temporal persistence, contextual descriptions, and retrieval are complementary
- Per-scene construction recovers some performance lost across scene changes

## Failure Modes
- Retrieval failures in stitched streams
- Construction failures in stitched streams
- Performance loss across scene changes

## Compute
- Requires egocentric video processing
- 3D object tracking
- Contextual description generation

## Novelty
- Persistent 3D object memory from egocentric videos
- Clustering by resting locations
- Move recording after repeated evidence
- Contextual descriptions for spatial reasoning

## Reproducibility
- Project page: https://...
- Code: https://...

## Memory Impact
- Temporal persistence is essential
- Contextual descriptions improve retrieval
- Retrieval quality matters
- Scene changes cause performance degradation

## Open Questions
- How does Ledger handle contradictions?
- What happens with long-term persistence (months)?
- Can this scale to thousands of objects?
- How does it compare to semantic memory approaches?
- What are the failure modes in retrieval?

## Confidence
MEDIUM (recent paper, need to verify implementation details)

## Tags
[persistent-memory], [ledger], [egocentric-videos], [3d-object-tracking], [embodied-ai]
