#!/usr/bin/env python3
"""
RC Timing Light Sensor — Calibration Tool

Use this script to find the right DARK_THRESHOLD value for your
photoresistor + capacitor circuit before running raspberry_pi_sensor.py.

Wiring
------
  GPIO pin (BOARD 7)  ──┬── photoresistor ── 3.3 V
                        └── capacitor      ── GND

How it works
------------
  1. Drive the pin LOW to discharge the capacitor.
  2. Switch to INPUT and measure how long until the pin reads HIGH.
  3. Short time  = low resistance = bright light = door open.
  4. Long time   = high resistance = dark        = door closed.

Usage
-----
  python pi_lightsensing.py            # continuous readings
  python pi_lightsensing.py --samples  # print 20 samples then exit
"""

import argparse
import time
import lgpio

# Physical BOARD pin 11 = BCM GPIO 17 on all Pi models
BCM_PIN = 17

# Open gpiochip4 — the main GPIO bank on Pi 4
_chip = lgpio.gpiochip_open(4)


def measure_darkness_ms(timeout_ms: float = 500.0) -> float:
    """
    Discharge the cap then time the recharge through the photoresistor.
    Returns charge time in milliseconds (lower = brighter).
    """
    # Discharge: claim as output, drive LOW
    lgpio.gpio_claim_output(_chip, BCM_PIN, 0)
    time.sleep(0.05)

    # Switch to input and time the recharge
    lgpio.gpio_free(_chip, BCM_PIN)
    lgpio.gpio_claim_input(_chip, BCM_PIN, lgpio.SET_PULL_NONE)
    t_start = time.time()
    deadline = t_start + timeout_ms / 1000.0

    while lgpio.gpio_read(_chip, BCM_PIN) == 0:
        if time.time() > deadline:
            lgpio.gpio_free(_chip, BCM_PIN)
            return timeout_ms

    elapsed = (time.time() - t_start) * 1000.0
    lgpio.gpio_free(_chip, BCM_PIN)
    return elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Light sensor calibration tool")
    parser.add_argument(
        "--samples",
        action="store_true",
        help="Collect 20 samples then print a suggested threshold and exit",
    )
    args = parser.parse_args()

    print(f"RC timing light sensor — BCM GPIO {BCM_PIN} (BOARD pin 7)")
    print("Open and close the fridge door to see the value range.")
    print("Press Ctrl+C to stop.\n")

    readings: list[float] = []

    try:
        while True:
            ms = measure_darkness_ms()
            label = "BRIGHT (door open?)" if ms < 10 else "dark   (door closed?)"
            print(f"  darkness: {ms:8.2f} ms   {label}")
            readings.append(ms)

            if args.samples and len(readings) >= 20:
                break

            time.sleep(0.15)

    except KeyboardInterrupt:
        pass
    finally:
        lgpio.gpiochip_close(_chip)

    if readings:
        lo, hi = min(readings), max(readings)
        suggested = (lo + hi) / 2
        print(f"\n--- Summary ({len(readings)} samples) ---")
        print(f"  Min (brightest): {lo:.2f} ms")
        print(f"  Max (darkest):   {hi:.2f} ms")
        print(f"  Suggested DARK_THRESHOLD: {suggested:.1f} ms")
        print(f"\nAdd to your .env on the Pi:")
        print(f"  DARK_THRESHOLD={suggested:.1f}")


if __name__ == "__main__":
    main()
