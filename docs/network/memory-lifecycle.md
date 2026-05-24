# Memory Lifecycle

## Purpose

The purpose of the product is to preserve memories and avoid losing them. The lifecycle model should therefore protect memory retention by default while still making room for correction, contradiction handling, stale values, and explicit deletion.

This is not a heavy review workflow. It is a lightweight state model that lets the system answer honestly and maintain itself over time.

## Lifecycle States

### Candidate

Extracted from a source but not yet written as canonical graph memory.

### Active

Stored and available for retrieval. This is the default state for accepted memories.

### Confirmed

Explicitly confirmed by the user or strongly supported by repeated evidence.

### Inferred

Derived by the system or an LLM from available evidence. It can be useful, but answers should expose that it is inferred.

### Disputed

Conflicts with another memory or has been challenged by the user. It should not be hidden, but answers should show the conflict.

### Stale

Possibly outdated, especially for mutable facts such as phone numbers, addresses, jobs, relationships, and preferences.

### Expired

No longer current but preserved for history. Example: an old phone number or former workplace.

### Archived

Kept for preservation but excluded from normal retrieval unless the user asks for older or archived memories.

### Deleted

Removed or suppressed according to deletion policy. Derived facts from deleted sources should be removed, hidden, or marked as orphaned according to implementation policy.

## Default Policy

- Preserve memories by default.
- Prefer marking facts as stale, expired, disputed, or archived over deleting them.
- Delete when the user explicitly asks, when data is unsafe to retain, or when legal/privacy policy requires it.
- Keep old values when historical context matters.
- Return current values by default, but make historical values available when asked.

## Mutable Facts

Some facts should be expected to change:

- Contact details.
- Addresses.
- Jobs and roles.
- Relationship status.
- Preferences.
- Profile memories.
- Project status.

Mutable facts should include validity metadata such as `valid_from`, `valid_to`, `observed_at`, and `is_current` where appropriate.

## Memory Management Agent

Lifecycle changes should eventually be handled by a dedicated memory management agent using safe tools:

- Mark stale.
- Mark disputed.
- Confirm.
- Expire.
- Archive.
- Delete.
- Merge.
- Split.
- Attach evidence.
- Ask clarification.

The agent should act conservatively and involve the user when the action affects important or sensitive memory.

## User Experience Principle

The user should not feel like they are maintaining a database. Lifecycle state should mostly appear through natural chat behavior:

- "I found two conflicting memories about this. Which one is correct?"
- "I have an older phone number and a newer one. Should I mark the older one as expired?"
- "This looks like the same Marco. Should I merge them?"

The system should preserve memory first, then ask only when the clarification improves trust or usefulness.
