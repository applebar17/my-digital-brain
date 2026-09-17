"""Shared behavioral guidance for agents that can request clarification."""

CLARIFICATION_POLICY = (
    "# Clarification policy\n"
    "- Inspect read-only context first when useful. Call `ask_clarification` only for a "
    "concrete doubt; include detailed refs, missing information, why it matters, and "
    "evidence.\n"
    "- A real context gap is unresolved information that prevents a reference from being "
    "resolved or would make the intended durable write ambiguous or unsupported. An "
    "optional unmentioned detail is not a context gap.\n"
    "- When a real context gap remains after inspecting the available context, call "
    "`ask_clarification` before planning or performing the affected write. Do not return "
    "it only in `context_gaps`, `missing_context_questions`, or "
    "`clarification_candidates` and then continue toward that write.\n"
    "- Hand off a source-grounded doubt, not a user-facing question. The clarification "
    "agent chooses the natural question and response format.\n"
    "- Use only supplied model-facing refs; never invent graph IDs, owners, or aliases.\n"
    "- Keep each handoff focused and keep custom answers enabled. Accept text or audio "
    "when supported; normalized text remains user evidence.\n"
    "- Choose tools by answer shape: free text/audio uses `ask_text` or "
    "`ask_text_or_audio` with `options=[]`; one, many, or two confirmation choices "
    "use `pick_one`, `pick_many`, or `confirm`. Never pass choices, placeholders, or "
    "empty-label options to free-text tools.\n"
    "- Use brief factual subtitles for duplicate options, not model-facing refs.\n"
    "- Apply explicit answers to fields; keep inference uncertain. On resume, match report "
    "entries by `doubt_id`, use clarified values, selected refs, evidence, "
    "and original wording, and do not repeat resolved doubts.\n"
    "- Use `defer_or_ignore` only after an explicit user request not to save or defer.\n"
    "- A clarification report is evidence, not a graph action or pipeline gate; continue "
    "same session and choose the next action.\n"
)

CLARIFICATION_EXAMPLES = """# Clarification examples
- No match: "Who is Amos? Please provide a surname or distinguishing detail."
- Duplicate: "Which Amos do you mean?" with brief factual subtitles and custom text.
- Missing field: ask only for the missing surname, date, place, or other field.
- Correction: show current and proposed values and ask which is correct.
- Confirmation: ask whether the proposed event, place, or relationship is right.
- Relationship endpoint: ask which supplied person or place the endpoint refers to.
"""
