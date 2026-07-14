# Changelog

## v0.1.0 - 2026-07-14

- Forked the upstream Apple II terminal into an independent Codex client while preserving Git history and the MIT license.
- Replaced the provider backend with the authenticated Codex CLI JSONL protocol, resumable turns, fail-closed approvals, cancellation, and redacted errors.
- Added required Git work directories plus `workspace-write` and `read-only` sandbox modes.
- Isolated pairing state with the `CDXTK1` token format, TCP port 6401, and modem phonebook entry 1.
- Renamed and rebranded both native clients. The release artifact is `CODEX.dsk`, containing `CODEX` and `CODEX8`.
- Added an animated monochrome `>_` identity, a distinct wake gesture, and CODEX dial cues.
- Added the Codex-style model, directory, and permissions header, three-tone Working shimmer, and styled interruption status.
- Added distinct WiModem `ERROR`, `BUSY`, `NO CARRIER`, `NO ANSWER`, and timeout guidance.
- Removed old provider artwork and demo media.
- Added security, physical-disk, attribution, and release-gate documentation.

### Verification

- `pytest -m 'not codex_live'` passes the offline bridge, renderer, pairing,
  protocol, cancellation, process-group, disk, and documentation suite.
- The opt-in authenticated Codex smoke passes first turn, persisted resume,
  workspace write, and read-only denial against Codex CLI 0.144.4.
- Offline cancellation tests cover process-group cleanup, partial replies,
  recovery, and the native interruption marker. Manual client testing covers
  Esc cancellation through the bridge.
- Both native clients assemble. The master-based build produces a reproducible
  143,360-byte `CODEX.dsk`; its catalog and reserved token sector pass, and the
  damaged-image gate rejects a disk missing `CODEX8`.
- KEGS and MAME enhanced-IIe paths pass. FloppyEmu plus physical IIgs and IIc
  hardware have been exercised. Physical IIe, IIc Plus, II/II+, and a two-sided
  real-disk copy remain untested and are identified as such in the compatibility
  documentation.

The earlier release history belongs to the upstream [Apple II Terminal for Claude Code](https://github.com/wr/apple-ii-terminal-for-claude-code) project and remains available in this repository's Git history.
