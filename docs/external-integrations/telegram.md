# Telegram Integration

## Role

Telegram is the likely first ingestion and chat interface. It gives the user a low-friction way to send memories, voice notes, images, corrections, and questions from mobile or desktop.

## Initial Capabilities

- Receive text messages.
- Send clarification questions.
- Receive clarification answers.
- Send ingestion summaries.
- Handle commands for basic control.
- Link Telegram messages to source records.

## Useful Commands

Potential commands:

- `/remember`: explicitly ingest a memory.
- `/ask`: ask the digital brain a question.
- `/status`: show pending clarifications or processing state.
- `/cancel`: cancel the current pending ingestion.
- `/correct`: start a correction flow.
- `/help`: list available commands.

Free-form messages can still be supported, but explicit commands may reduce ambiguity during early development.

## Message Lifecycle

1. Telegram webhook receives a message.
2. Integration verifies the sender.
3. Message is normalized into an internal source payload.
4. Source is stored with Telegram metadata.
5. Ingestion flow starts.
6. Clarification questions are sent back through Telegram if needed.
7. User replies are correlated to the pending ingestion session.

## Identity And Security

The integration should:

- Restrict access to approved Telegram users.
- Avoid accepting messages from unknown chats.
- Store Telegram identifiers as external references, not as primary user identity.
- Avoid exposing sensitive graph details in group chats unless explicitly enabled.
- Support revoking access.

## Clarification Handling

Clarification messages should be short and answerable in one reply.

Good:

```text
Which Marco do you mean: Marco Rossi, Marco Bianchi, or someone new?
```

Good:

```text
Where in Italy did this happen?
```

Avoid:

```text
Please provide all missing details for the event, including participants, date, location, topic, and context.
```

## Later Capabilities

- Voice note transcription.
- Image ingestion.
- File ingestion.
- Inline buttons for disambiguation.
- Pending clarification list.
- Quick merge/split confirmation.
- Notification when a memory is ready for review.
