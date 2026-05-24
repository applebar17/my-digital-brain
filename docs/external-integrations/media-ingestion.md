# Media Ingestion

## Purpose

Media ingestion extends the digital brain beyond typed text. Images, audio, documents, and links can become evidence sources and eventually generate entities, relationships, captions, transcripts, and claims.

Voice messages are a first-class ingestion path because the user may naturally describe memories by speaking. Other media can be deeper roadmap work, but audio transcription should be part of the early system.

## Source Types

Potential media sources:

- Images.
- Audio and voice messages.
- Video.
- PDFs and documents.
- Links and web pages.
- Screenshots.
- Calendar exports.
- Location exports.

## Processing Pipeline

1. Receive media from Telegram, frontend, or another integration.
2. Store the original artifact or a secure reference to it.
3. Extract metadata such as timestamp, filename, MIME type, size, sender, and channel.
4. Run type-specific processing when enabled.
5. Produce text artifacts such as captions, OCR text, transcripts, or summaries.
6. Feed extracted text into the normal ingestion flow.
7. Link generated entities and relationships back to the media source.

## Voice Message Pipeline

Voice messages should follow a dedicated pipeline:

1. Receive voice message from Telegram, frontend, or another chat interface.
2. Store the original audio artifact or a secure reference.
3. Extract audio metadata such as duration, format, size, source timestamp, sender, and channel.
4. Transcribe the audio with speech-to-text.
5. Store the transcript as a derived source artifact linked to the original audio.
6. Optionally produce time-coded transcript segments.
7. Run the transcript through the normal LLM extraction pipeline.
8. Preserve transcript confidence and uncertain spans.
9. Ask clarifications through chat when transcription or memory extraction is ambiguous.
10. Link graph entities, relationships, claims, and profile memories back to both transcript and original audio.

The transcript is evidence, but the original audio remains the strongest source artifact when the transcript is uncertain.

## Type-Specific Processing

### Images

Potential outputs:

- Caption.
- Detected people, places, objects, and text.
- OCR text.
- EXIF metadata.
- Visual embedding.

### Audio

Potential outputs:

- Transcript.
- Transcript confidence.
- Uncertain transcript spans.
- Speaker hints.
- Summary.
- Mentioned entities.
- Time-coded segments.

Voice-message specific concerns:

- Background noise may reduce extraction quality.
- Names and places may be mistranscribed.
- The user may speak in mixed languages.
- The message may contain multiple memories in one recording.
- Clarification may be needed when transcription uncertainty affects entity resolution.

### Documents

Potential outputs:

- Text extraction.
- Structured sections.
- Tables.
- Document summary.
- Referenced people, places, dates, and organizations.

### Links And Web Pages

Potential outputs:

- Page title.
- Canonical URL.
- Extracted readable text.
- Summary.
- Referenced entities.

## Graph Modeling

Every media item should be represented as a `Source`. Derived artifacts such as transcripts, captions, and OCR output should either be linked source records or source properties, depending on storage design.

Entities extracted from media should link back to:

- Original media source.
- Derived text artifact.
- Processing run.
- Model or tool version.

## Open Questions

- Whether original media is stored locally, in object storage, or externally referenced.
- Whether media processing runs automatically or only on explicit request.
- Which speech-to-text provider or local model should be used.
- Whether voice messages should be transcribed automatically by default.
- How to handle private or sensitive media.
- Whether face recognition is allowed, disabled, or confirmation-only.
- How long derived artifacts and raw media should be retained.
