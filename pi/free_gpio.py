#!/usr/bin/env python3
import lgpio
try:
    h = lgpio.gpiochip_open(4)
    lgpio.gpio_free(h, 17)
    lgpio.gpiochip_close(h)
    print("GPIO 17 freed")
except Exception as e:
    print(f"Already free or error: {e}")
