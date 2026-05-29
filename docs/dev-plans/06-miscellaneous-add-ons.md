# Miscellaneous Add-Ons

## Goal

Track useful supporting features that do not deserve standalone planning yet, but may become important as the system matures.

## Wave 0: Baseline Setup

- Local container setup.
- Environment configuration.
- Basic logging.
- Backup/export decision.
- Secret management approach.
- Graph database authentication decision.
- Secure backup package format.
- Simple project structure.

## Wave 1: MVP Support Features

- Local development scripts.
- Basic health checks.
- Source/media folder management.
- Minimal pending ingestion persistence.
- Error reporting for failed ingestion.
- Simple reprocessing command for one source.
- Basic prompt/schema version tracking.

## Wave 2: Reliability And Maintenance

- Backup and restore.
- Encrypted graph/source backup packages.
- Authenticated remote download flow for backups.
- Export graph and sources.
- Ingestion replay.
- Prompt/model evaluation examples.
- Duplicate scan job.
- Stale fact scan job.
- Cost and latency tracking for model calls.
- Privacy checks before provider calls.

## Wave 3: Advanced Add-Ons

- Personal memory digest.
- Scheduled maintenance summaries.
- Graph analytics.
- Profile memory inspector.
- Model routing dashboard.
- Prompt/version experiment tracking.
- Offline/local-only mode.
- Multi-device local access.
- Key rotation for backup encryption.

## Possible Future Standalone Topics

These may deserve their own docs later:

- Deployment and operations.
- AI evaluation strategy.
- Backup/export/delete strategy.
- Security and privacy implementation.
- Secure backup/export/delete strategy.
- Prompt and model operations.

For now, keep them here to avoid over-planning before the MVP takes shape.

## Initial Success Criteria

- Local setup is repeatable.
- Failures are visible.
- Sources and graph data can be backed up.
- Backups can be encrypted and restored.
- Model calls can be traced when they affect memory.
- The project remains easy to run as a personal system.

## Secure Graph Copies And Downloads

Running graph database authentication and backup security are separate.

Graph database authentication protects access to the live database server. It should use strong generated credentials, isolated container networking, and separate users where useful.

Local copies and remote downloads should be protected as export packages:

1. Export graph data, source records, and media references.
2. Create a manifest with schema version, created timestamp, included stores, file hashes, and export tool version.
3. Encrypt the package before local storage or remote upload.
4. Optionally sign the manifest so tampering can be detected.
5. Require authentication before remote download.
6. Prefer short-lived download tokens or signed URLs when remote storage is used.
7. Verify checksum and manifest before restore.

The encryption key or passphrase should not be stored inside the backup package.
