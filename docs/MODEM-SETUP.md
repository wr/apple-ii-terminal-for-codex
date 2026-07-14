# Modem setup

The native clients use 9600 baud, 8 data bits, no parity, and one stop bit. **Connect** sends `ATDS=1`, so Codex uses phonebook entry 1. The bridge listens on TCP port 6401.

Keeping Codex on entry 1 lets an existing upstream client remain on entry 0 and port 6400.

## WiModem 232 and 232 Pro

A factory WiModem starts at 300 baud. Set 9600 once from a terminal that can speak 300 baud:

```text
AT*B9600
AT&W
```

Then use the boot menu's **Modem** console:

```text
AT*SSIDYourNetwork,YourPassword
AT&Z1=192.168.1.50:6401
AT&W
```

Replace the IP with the computer running the bridge. Start the bridge before choosing **Connect**:

```sh
python3 bridge/bridge.py --telnet --app \
  --workdir /absolute/path/to/git/repo
```

The modem should answer `ATDS=1` and connect to the bridge. `ATI` prints its current baud, IP, and network status.

## Cables

| Machine | Port | Cable |
|---|---|---|
| IIgs | mini-DIN-8 modem port | Classic Mac/Apple mini-DIN-8 to DB25 modem cable |
| IIc | DIN-5 modem port | Apple IIc DIN-5 to DB25 modem cable |
| IIc Plus | mini-DIN-8 modem port | Same modem cable as IIgs |
| IIe / II+ | Super Serial Card in slot 2 | Straight-through DB25; SSC jumper points to MODEM |

A printer cable may look identical to a IIgs modem cable but cross the wrong signals. Do not add a null-modem adapter between an SSC in MODEM mode and a modem.

## Other WiFi modems

Firmware differs on phonebook syntax. Store the host on port 6401 in entry 1 if the modem supports it. The native auto-dial string is fixed at `ATDS=1`.

| Device | Example store command | Dial behavior |
|---|---|---|
| WiModem 232 | `AT&Z1=host:6401` | `ATDS=1`; works directly |
| WiFi232 | `AT&Z1=host:6401` | Often expects `ATDS1` without `=` |
| Zimodem / RetroWiFi | Firmware-specific numbered phonebook | `ATDS` may mean SSH, so dial manually |
| FujiNet-style modem | Usually direct host dialing | Dial `ATDT host:6401` manually |

For incompatible slot syntax, open **Modem**, dial the host manually, press Esc after it connects, and choose **Connect**. A IIgs with a working DCD signal can detect the live carrier and skip redialing.

## Troubleshooting

The native client keeps the modem's raw response visible and adds a short diagnosis:

| Result | What the client suggests |
|---|---|
| `ERROR` | Save entry 1 with `AT&Z1=host:6401`, then `AT&W` |
| `BUSY` | The bridge or destination is occupied; retry |
| `NO CARRIER` | Check entry 1, the bridge process, and WiFi |
| `NO ANSWER` | Check that the bridge is listening on port 6401 |
| No response | Check the modem connection and 9600 8N1 settings |

Then check these in order:

1. On an SSC, point the jumper block arrow to MODEM and use slot 2.
2. Confirm DCD is asserted. On WiModem firmware, `AT*D1` may correct its polarity; save with `AT&W`.
3. Confirm the IIgs/IIc Plus cable is a modem cable, not a printer cable.
4. Match both ends at 9600 8N1.
5. Remove any null-modem adapter.
6. Send `ATE0` and `AT&W` if every typed character appears twice.
7. An immediate `ERROR` usually means entry 1 was not saved or the modem rejected `ATDS=1`.

The listener is plaintext and LAN-reachable by default. Do not port-forward it. See [SECURITY.md](../SECURITY.md).
