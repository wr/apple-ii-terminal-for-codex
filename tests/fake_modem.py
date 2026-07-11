"""Fake Hayes modem for MAME's bitbanger socket: answers the client's
ATDS=0 with CONNECT (or BUSY) shortly after, logging what it hears."""
import socket, sys, time

verdict = sys.argv[1] if len(sys.argv) > 1 else "CONNECT"
srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", 6502))
srv.listen(1)
print("fake modem: listening", flush=True)
conn, _ = srv.accept()
print("fake modem: MAME connected", flush=True)
conn.settimeout(0.1)
buf = b""
while True:
    try:
        b = conn.recv(256)
        if not b:
            break
        buf += b
        print(f"fake modem: rx {b!r}", flush=True)
        if b"ATDS=0\r" in buf:
            buf = buf.replace(b"ATDS=0\r", b"")
            # reply immediately: with -nothrottle, wall-clock delays overshoot
            # the emulated dial window entirely
            conn.sendall(verdict.encode() + b"\r\n")
            print(f"fake modem: sent {verdict}", flush=True)
    except socket.timeout:
        pass
    except OSError:
        break
print("fake modem: done", flush=True)
