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

### Verification

- `pytest -m 'not codex_live'` passes the offline bridge, renderer, pairing,
  protocol, cancellation, process-group, disk, and documentation suite.
- The opt-in authenticated Codex smoke passes first turn, persisted resume,
  workspace write, and read-only denial against Codex CLI 0.144.1.
- Live cancellation could not be certified from inside a nested Codex Desktop
  task because the outer task intercepts the cancellation signal. The offline
  real-process-group cancellation regressions pass; rerun the live cancellation
  case from a normal terminal before release.
- Both native clients assemble. The master-based build produces a reproducible
  143,360-byte `CODEX.dsk`; its catalog and reserved token sector pass, and the
  damaged-image gate rejects a disk missing `CODEX8`.
- MAME client runs remain unverified because the required user-supplied Apple II
  ROM set is not installed. KEGS, FloppyEmu, physical IIgs/IIc, and two-sided
  physical-media checks also remain unverified. These are release blockers, not
  inferred passes.

The earlier release history belongs to the upstream [Apple II Terminal for Claude Code](https://github.com/wr/apple-ii-terminal-for-claude-code) project and remains available in this repository's Git history.
