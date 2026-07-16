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

The modem should answer `ATDS=1` and connect to the bridge. `ATI` prints its current baud, IP, SSID, and network status. Other WiFi join methods include `AT*WPS`, the `AT*WIFI` configuration portal, or `AT*N` followed by `AT*NS<number>,<passphrase>`. On current firmware, pulsing red means the modem is searching for WiFi, yellow means WiFi is up, and green means the TCP connection is live.

`AT*D` changes DCD polarity, which can matter with a Super Serial Card. `AT*MODE1` followed by `AT&W` keeps the radio off at boot until it is needed.

## Cables

| Machine | Port | Cable |
|---|---|---|
| IIgs | mini-DIN-8 modem port | Classic Mac/Apple mini-DIN-8 to DB25 male modem cable |
| IIc | DIN-5 modem port | Apple IIc DIN-5 to DB25 male modem cable |
| IIc Plus | mini-DIN-8 modem port | Same modem cable as IIgs |
| IIe / II+ | Super Serial Card in slot 2 | Straight-through DB25, or a gender changer; SSC jumper points to MODEM |

A printer cable may look identical to a IIgs modem cable but cross the wrong signals. On a Super Serial Card, point the jumper block arrow to MODEM and set SW1-5, SW1-6, and SW1-7 ON for modem use. The client programs the baud rate directly, so the baud DIP switches do not matter. Do not add a null-modem adapter between an SSC in MODEM mode and a modem; a plain gender changer is fine.

## Other WiFi modems

Firmware differs on phonebook syntax. Store the host on port 6401 in entry 1 if the modem supports it. The native auto-dial string is fixed at `ATDS=1`.

| Device | Example store command | Dial behavior | Initial setup |
|---|---|---|---|
| WiModem 232 | `AT&Z1=host:6401` | `ATDS=1`; works directly | Ships at 300 baud; use `AT*B9600`, then `AT&W` |
| WiFi232 | `AT&Z1=host:6401` | Often expects `ATDS1` without `=` | Often ships at 1200 baud; join with `AT$SSID=name`, `AT$PASS=pw`, `ATC1`, set baud with `AT$SB=9600`, then `AT&W` |
| Zimodem / RetroWiFi | `ATP"0000001=host:6401"` on common builds | `ATDS` may mean SSH; dial the numbered entry manually | Join with `ATW"ssid,password"`; firmware defaults vary |
| FujiNet-style modem | Usually direct host dialing | Dial `ATDT host:6401` manually | Firmware-specific |

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

1. On an SSC, point the jumper block arrow to MODEM, set SW1-5 through SW1-7 ON, and use slot 2.
2. Confirm DCD is asserted. The SSC may refuse received data when carrier detect is low. On WiModem firmware, `AT*D1` may correct its polarity; save with `AT&W`. WiFi232 hardware commonly loops DCD to DTR; a cable-level workaround is to assert DB25 pin 8.
3. Confirm the IIgs/IIc Plus cable is a modem cable, not a printer cable.
4. Match both ends at 9600 8N1.
5. Remove any null-modem adapter.
6. Send `ATE0` and `AT&W` if every typed character appears twice.
7. An immediate `ERROR` usually means entry 1 was not saved or the modem rejected `ATDS=1`.

WiFi modems may print status chatter such as `RECONNECTED` or `RING` before dialing. The native client flushes old input before the dial and the bridge filters known modem chatter. If it appears constantly, recheck the baud rate.

The listener is plaintext and LAN-reachable by default. Do not port-forward it. See [SECURITY.md](../SECURITY.md).
