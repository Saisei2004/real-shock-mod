#!/usr/bin/env python3
import argparse
import os
import select
import sys
import termios
import time


def configure_posix_serial(fd, baud):
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attrs[3] = 0
    speed = getattr(termios, f"B{baud}", termios.B115200)
    attrs[4] = speed
    attrs[5] = speed
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    termios.tcflush(fd, termios.TCIOFLUSH)


def read_posix(fd, wait_seconds):
    end = time.time() + wait_seconds
    chunks = []
    while time.time() < end:
        readable, _, _ = select.select([fd], [], [], max(0, end - time.time()))
        if not readable:
            break
        data = os.read(fd, 256)
        if data:
            chunks.append(data)
    return b"".join(chunks).decode(errors="replace").strip()


def send_line(port, baud, line, wait_seconds):
    try:
        import serial
    except ImportError:
        if not port.startswith("/dev/"):
            print("pyserial is not installed. Run: python -m pip install -r requirements.txt", file=sys.stderr)
            return 2
        fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            configure_posix_serial(fd, baud)
            time.sleep(1.8)
            termios.tcflush(fd, termios.TCIOFLUSH)
            os.write(fd, (line.strip() + "\n").encode("ascii"))
            text = read_posix(fd, wait_seconds)
            if text:
                print(text)
        finally:
            os.close(fd)
        return 0

    with serial.Serial(port, baud, timeout=0.1, write_timeout=2) as ser:
        time.sleep(1.8)
        ser.reset_input_buffer()
        ser.write((line.strip() + "\n").encode("ascii"))
        ser.flush()
        end = time.time() + wait_seconds
        chunks = []
        while time.time() < end:
            data = ser.read(256)
            if data:
                chunks.append(data)
            else:
                time.sleep(0.03)
        text = b"".join(chunks).decode(errors="replace").strip()
        if text:
            print(text)
    return 0


def main():
    parser = argparse.ArgumentParser(description="ESP32 LED test controller debug tool")
    parser.add_argument("command", nargs="*", help="status | none | level N | button A | event kind intensity duration_ms")
    parser.add_argument("--port", default=os.environ.get("REAL_SHOCK_ESP32_SERIAL_PORT", "/dev/cu.usbserial-120"))
    parser.add_argument("--baud", type=int, default=int(os.environ.get("REAL_SHOCK_ESP32_SERIAL_BAUD", "115200")))
    parser.add_argument("--wait", type=float, default=2.5)
    args = parser.parse_args()

    if not args.command:
        line = "status"
    elif args.command[0] == "fire" and len(args.command) >= 3:
        intensity = args.command[1]
        seconds = float(args.command[2])
        line = f"event debug {int(intensity)} {int(seconds * 1000)} 0"
        args.wait = max(args.wait, seconds + 2.5)
    else:
        line = " ".join(args.command)
        if args.command[0] == "event" and len(args.command) >= 4:
            args.wait = max(args.wait, int(args.command[3]) / 1000 + 2.5)

    return send_line(args.port, args.baud, line, args.wait)


if __name__ == "__main__":
    raise SystemExit(main())
