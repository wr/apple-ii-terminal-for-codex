# Security

Apple II Terminal for Codex connects an Apple II to a local Codex CLI. The bridge can expose a repository and shell-capable agent over serial or plaintext TCP, so its boundary needs to be explicit.

## Reporting a vulnerability

Use GitHub's private **Report a vulnerability** flow for the repository, or email media [at] wells [dot] ee. Public issues are fine for non-sensitive bugs. This is a hobby project with no formal response SLA.

## Network exposure

`--telnet` listens on TCP port 6401 and binds to `0.0.0.0` by default so a WiFi modem can reach it. Telnet does not encrypt pairing codes, device tokens, prompts, or replies. Use it only on a trusted home LAN. Never port-forward the bridge or expose any mode to the public internet.

Use `--host 127.0.0.1` for emulator-only access. A direct `--serial` connection avoids LAN exposure. `--no-pair` removes the access gate and is only suitable for an isolated network or direct local test.

## Pairing token

The first native-client pairing exchanges a six-character console code for a device token. That token is a bearer credential: possession grants access without the code.

- The Apple II stores the plaintext token in a reserved sector of its boot disk.
- The host stores only its SHA-256 hash, first-seen IP, and pairing time in `$XDG_CONFIG_HOME/codex-ii-terminal/paired.json`, or `~/.config/codex-ii-terminal/paired.json` when XDG is unset.
- Telnet carries the code and token in plaintext.
- Run with `--clear-paired` to revoke all issued tokens. Rebuild or erase the client disk before giving it to someone else.

Treat `CODEX.dsk`, its FloppyEmu copy, and any physical floppy containing it like house keys.

## Codex boundary

The bridge does not receive, store, or transmit Codex credentials or an API key. It starts the installed `codex` executable. Codex owns authentication and retains its normal local session data.

The required `--workdir` selects an existing Git repository. The default `--sandbox workspace-write` allows Codex to edit files and run commands only within Codex's sandbox boundary. Use `--sandbox read-only` for inspection-only sessions.

The subprocess uses `approval_policy=never`. An Apple II cannot service a host approval prompt, so operations outside the selected sandbox fail instead of waiting invisibly or gaining broader authority.

## Local data and console output

Every Apple II prompt prints on the host bridge console. Reply content travels over the selected transport. Codex may keep its own session records and other local state according to the installed CLI's behavior. Do not enter secrets that should not appear on the bridge console, wire, terminal screen, or Codex session history.

## Supported versions

Security fixes target the latest release. Codex CLI 0.144.1 is the minimum supported host version.
