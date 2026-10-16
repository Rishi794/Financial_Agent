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

## Memory Type
- Episodic: object locations, movement histories
- Semantic: contextual descriptions
- Procedural: spatial reasoning patterns

## Key Insight
Persistent memory works when:
1. Objects are tracked across scenes
2. Movement is recorded only after repeated evidence
3. Retrieval is query-driven, not passive storage

## Limitations
- Requires 3D spatial tracking
- Performance drops across scene changes
- Storage overhead for movement history

## Open Questions
- How does Ledger handle object permanence when never seen again?
- What happens when objects are modified?
- Can this scale to complex environments?