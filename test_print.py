#!/usr/bin/env python3
"""
Test script — prints a test message to verify the thermal printer works over USB.

Steps:
  1. Connect the printer via USB and turn it on
  2. Run: lsusb
  3. Find your printer, note the vendor:product ID (e.g. "0416:5011")
  4. Update config.py with those IDs
  5. Run: python3 test_print.py
"""

from escpos.printer import Usb
import config


def main():
    print("Connecting to printer...")
    print(f"  Vendor ID:  {hex(config.PRINTER_VENDOR_ID)}")
    print(f"  Product ID: {hex(config.PRINTER_PRODUCT_ID)}")

    kwargs = {
        "idVendor": config.PRINTER_VENDOR_ID,
        "idProduct": config.PRINTER_PRODUCT_ID,
    }
    # Use explicit endpoints if configured
    if hasattr(config, "PRINTER_IN_EP"):
        kwargs["in_ep"] = config.PRINTER_IN_EP
    if hasattr(config, "PRINTER_OUT_EP"):
        kwargs["out_ep"] = config.PRINTER_OUT_EP

    printer = Usb(**kwargs)

    print("Printing test message...")
    printer.text("================================\n")
    printer.text("Squeaky beaky, K\n")
    printer.text("\n")
    printer.text("Flowers, daffodils, and plane,\n")
    printer.text("and shark\n")
    printer.text("================================\n")
    printer.text("\n\n\n")

    print("Done! Check the printer for output.")


if __name__ == "__main__":
    main()
