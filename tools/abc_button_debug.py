#!/usr/bin/env python3
import argparse
import os
import select
import termios
import time


def configure_serial(fd, baud):
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


def read_available(fd, seconds):
    end = time.time() + seconds
    chunks = []
    while time.time() < end:
        readable, _, _ = select.select([fd], [], [], max(0, end - time.time()))
        if not readable:
            break
        data = os.read(fd, 512)
        if data:
            chunks.append(data)
    return b"".join(chunks).decode(errors="replace").strip()


def send_command(fd, command, wait_seconds=0.25):
    print(f"> {command}", flush=True)
    os.write(fd, (command + "\n").encode("ascii"))
    response = read_available(fd, wait_seconds)
    if response:
        print(response, flush=True)


def main():
    parser = argparse.ArgumentParser(description="Press A, B, C once with a fixed interval over ESP32 serial.")
    parser.add_argument("--port", default=os.environ.get("REAL_SHOCK_ESP32_SERIAL_PORT", "/dev/cu.usbserial-120"))
    parser.add_argument("--baud", type=int, default=int(os.environ.get("REAL_SHOCK_ESP32_SERIAL_BAUD", "115200")))
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--cycles", type=int, default=1)
    args = parser.parse_args()

    fd = os.open(args.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        configure_serial(fd, args.baud)
        time.sleep(1.8)
        termios.tcflush(fd, termios.TCIOFLUSH)

        for cycle in range(args.cycles):
            if args.cycles > 1:
                print(f"cycle {cycle + 1}/{args.cycles}", flush=True)
            for button in ("A", "B", "C"):
                send_command(fd, f"button {button}")
                time.sleep(args.interval)

        send_command(fd, "status", wait_seconds=0.5)
    finally:
        os.close(fd)


if __name__ == "__main__":
    raise SystemExit(main())
