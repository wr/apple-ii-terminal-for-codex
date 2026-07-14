# Changelog

## Unreleased

- Forked the upstream Apple II terminal into an independent Codex client while preserving Git history and the MIT license.
- Replaced the provider backend with the authenticated Codex CLI JSONL protocol, resumable turns, fail-closed approvals, cancellation, and redacted errors.
- Added required Git work directories plus `workspace-write` and `read-only` sandbox modes.
- Isolated pairing state with the `CDXTK1` token format, TCP port 6401, and modem phonebook entry 1.
- Renamed and rebranded both native clients. The release artifact is `CODEX.dsk`, containing `CODEX` and `CODEX8`.
- Added Patch, an original four-color terminal mechanic, plus CODEX dial cues.
- Removed old provider artwork and demo media.
- Added security, physical-disk, attribution, and release-gate documentation.

The earlier release history belongs to the upstream [Apple II Terminal for Claude Code](https://github.com/wr/apple-ii-terminal-for-claude-code) project and remains available in this repository's Git history.
