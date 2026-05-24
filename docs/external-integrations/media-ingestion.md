# Media Ingestion

## Purpose

Media ingestion extends the digital brain beyond text. Images, audio, documents, and links can become evidence sources and eventually generate entities, relationships, captions, transcripts, and claims.

The first version should store media as source evidence even if deep analysis is deferred.

## Source Types

Potential media sources:

- Images.
- Audio and voice notes.
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
- Speaker hints.
- Summary.
- Mentioned entities.
- Time-coded segments.

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
- How to handle private or sensitive media.
- Whether face recognition is allowed, disabled, or confirmation-only.
- How long derived artifacts and raw media should be retained.
