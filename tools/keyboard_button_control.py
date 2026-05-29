#!/usr/bin/env python3
import argparse
import os
import select
import sys
import termios
import time
import tty


BUTTON_KEYS = {
    "a": "A",
    "b": "B",
    "c": "C",
}


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


def send_line(fd, line, wait_seconds):
    os.write(fd, (line + "\n").encode("ascii"))
    return read_available(fd, wait_seconds)


def press_button(fd, button, wait_seconds):
    response = send_line(fd, f"button {button}", wait_seconds)
    if response:
        print(f"{button}: {response}", flush=True)
    else:
        print(f"{button}: sent", flush=True)


def run_sequence(fd, sequence, wait_seconds, gap_seconds):
    for char in sequence:
        key = char.lower()
        if key in BUTTON_KEYS:
            press_button(fd, BUTTON_KEYS[key], wait_seconds)
            time.sleep(gap_seconds)


def run_interactive(fd, wait_seconds):
    if not sys.stdin.isatty():
        print("Interactive mode needs a terminal. Use --sequence ABC for non-interactive testing.", file=sys.stderr)
        return 2

    old_attrs = termios.tcgetattr(sys.stdin.fileno())
    try:
        tty.setcbreak(sys.stdin.fileno())
        print("Press A/B/C to send that button. Q or Ctrl-C quits.", flush=True)
        while True:
            readable, _, _ = select.select([sys.stdin], [], [], 0.1)
            if not readable:
                continue
            char = sys.stdin.read(1)
            key = char.lower()
            if key == "q" or char == "\x03":
                print("quit", flush=True)
                return 0
            if key in BUTTON_KEYS:
                press_button(fd, BUTTON_KEYS[key], wait_seconds)
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, old_attrs)


def main():
    parser = argparse.ArgumentParser(description="Control ESP32 A/B/C buttons from this PC keyboard.")
    parser.add_argument("--port", default=os.environ.get("REAL_SHOCK_ESP32_SERIAL_PORT", "/dev/cu.usbserial-120"))
    parser.add_argument("--baud", type=int, default=int(os.environ.get("REAL_SHOCK_ESP32_SERIAL_BAUD", "115200")))
    parser.add_argument("--wait", type=float, default=0.25, help="Seconds to wait for ESP32 response after each key.")
    parser.add_argument("--sequence", help="Optional test sequence such as ABC or AACC. If omitted, reads keyboard live.")
    parser.add_argument("--gap", type=float, default=0.05, help="Gap between sequence buttons.")
    args = parser.parse_args()

    fd = os.open(args.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        configure_serial(fd, args.baud)
        time.sleep(1.8)
        termios.tcflush(fd, termios.TCIOFLUSH)
        if args.sequence:
            run_sequence(fd, args.sequence, args.wait, args.gap)
            return 0
        return run_interactive(fd, args.wait)
    finally:
        os.close(fd)


if __name__ == "__main__":
    raise SystemExit(main())
