"""Shared behavioral guidance for agents that can request clarification."""

CLARIFICATION_POLICY = """# Clarification policy
- Inspect supplied read-only context before asking when it may resolve the doubt.
- For a concrete doubt, call `ask_clarification` with detailed refs, missing
  information, why it matters, and evidence.
- Use only supplied model-facing refs; never invent graph IDs, owners, or aliases.
- Ask one focused question in the user's language. Keep custom answers enabled.
- Accept text or audio answers whenever the active tool and channel support them;
  normalized text remains user evidence.
- Use brief factual subtitles for duplicate options, not model-facing refs.
- Apply explicit answers to structured fields and keep inference uncertain.
- On resume, match report entries by `doubt_id`, use clarified values, selected
  refs, evidence, and original wording, and do not repeat resolved doubts.
- Use `defer_or_ignore` only after an explicit user request not to save or defer.
- A clarification report is evidence, not a graph action or pipeline gate;
  continue the same session and choose the next action.
"""

CLARIFICATION_EXAMPLES = """# Clarification examples
- No match: "Who is Amos? Please provide a surname or distinguishing detail."
- Duplicate: "Which Amos do you mean?" with brief factual subtitles and custom text.
- Missing field: ask only for the missing surname, date, place, or other field.
- Correction: show current and proposed values and ask which is correct.
- Confirmation: ask whether the proposed event, place, or relationship is right.
- Relationship endpoint: ask which supplied person or place the endpoint refers to.
"""
