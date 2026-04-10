#!/usr/bin/env python3
"""
Mini Fax — text a phone number, get a printed message.

Polls Twilio for new inbound SMS messages and prints them
on a USB thermal receipt printer. Only prints messages from
phone numbers listed in config.ALLOWED_NUMBERS.

Run directly:  python3 mini_fax.py
Or as a service: see mini-fax.service
"""

import json
import os
import sys
import time
import textwrap
from datetime import datetime, timedelta, timezone

from twilio.rest import Client
from escpos.printer import Usb

import config

# ── Paper width ──
# 58mm thermal paper = 32 characters per line at default font size
LINE_WIDTH = 32


def load_contacts():
    """Load allowed contacts from contacts.json, falling back to config."""
    try:
        with open("contacts.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return getattr(config, "ALLOWED_NUMBERS", {})


def init_printer():
    """Connect to the thermal printer over USB."""
    kwargs = {
        "idVendor": config.PRINTER_VENDOR_ID,
        "idProduct": config.PRINTER_PRODUCT_ID,
    }
    # Use explicit endpoints if configured (fixes "Invalid endpoint" errors)
    if hasattr(config, "PRINTER_IN_EP"):
        kwargs["in_ep"] = config.PRINTER_IN_EP
    if hasattr(config, "PRINTER_OUT_EP"):
        kwargs["out_ep"] = config.PRINTER_OUT_EP
    return Usb(**kwargs)


def load_printed_sids():
    """Load the set of already-printed message SIDs from disk."""
    try:
        with open(config.STATE_FILE, "r") as f:
            data = json.load(f)
            return set(data.get("printed_sids", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_printed_sids(sids):
    """Save printed message SIDs to disk. Keeps the most recent 500."""
    recent = list(sids)[-500:]
    with open(config.STATE_FILE, "w") as f:
        json.dump({"printed_sids": recent}, f)


def sender_name(phone_number, contacts):
    """Look up a friendly name for a phone number."""
    return contacts.get(phone_number, phone_number)


def format_message(msg, contacts):
    """Format a Twilio message for the thermal printer (32 chars wide)."""
    name = sender_name(msg.from_, contacts)
    # Convert UTC timestamp to local time
    local_time = msg.date_sent.astimezone()
    timestamp = local_time.strftime("%-I:%M %p  %b %-d, %Y")
    body = msg.body.strip()

    lines = []
    lines.append("=" * LINE_WIDTH)
    lines.append(f"From: {name}")
    lines.append(timestamp)
    lines.append("-" * LINE_WIDTH)
    lines.append(textwrap.fill(body, width=LINE_WIDTH))
    lines.append("=" * LINE_WIDTH)
    lines.append("")  # blank lines for easy tearing
    lines.append("")

    return "\n".join(lines)


def poll_once(client, printer, printed_sids):
    """Check Twilio for new messages and print any we haven't seen yet.

    Returns True if anything was printed.
    """
    # Look back 24 hours for messages we might have missed
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    messages = client.messages.list(
        to=config.TWILIO_PHONE_NUMBER,
        date_sent_after=since,
    )

    # Filter to unprinted messages, oldest first
    contacts = load_contacts()
    new_messages = [
        m
        for m in reversed(messages)
        if m.sid not in printed_sids and (not contacts or m.from_ in contacts)
    ]

    for msg in new_messages:
        formatted = format_message(msg, contacts)
        print(f"  Printing from {sender_name(msg.from_, contacts)}: {msg.body[:50]}...")
        try:
            printer.text(formatted)
        except Exception as e:
            print(f"  Print error: {e}")
            # Try reconnecting the printer once
            try:
                printer.close()
            except Exception:
                pass
            try:
                printer.open()
                printer.text(formatted)
            except Exception as e2:
                print(f"  Retry failed: {e2} — skipping message")
        # Always mark as printed so we don't spam retries
        printed_sids.add(msg.sid)

    return len(new_messages) > 0


def print_startup_receipt(printer):
    """Print a confirmation receipt so the user knows it's working."""
    # Format the phone number nicely
    num = config.TWILIO_PHONE_NUMBER
    if len(num) == 12 and num.startswith("+1"):
        nice_num = f"({num[2:5]}) {num[5:8]}-{num[8:12]}"
    else:
        nice_num = num

    printer.set(align="center")
    printer.text("================================\n")
    printer.text("\n")
    printer.text("MINI FAX IS READY!\n")
    printer.text("\n")
    printer.text("--------------------------------\n")
    printer.text(f"Text this number to print:\n")
    printer.set(double_height=True)
    printer.text(f"{nice_num}\n")
    printer.set(double_height=False)
    printer.text("--------------------------------\n")
    printer.text("\n")
    printer.text("Send any text message and\n")
    printer.text("it will print here!\n")
    printer.text("\n")
    printer.text("--------------------------------\n")
    printer.text("\n")
    printer.text("To manage contacts, open\n")
    printer.text("your phone's browser and go to:\n")
    printer.text("\n")
    printer.set(double_height=True)
    printer.text("mini-fax.local\n")
    printer.set(double_height=False)
    printer.text("\n")
    printer.text("Bookmark it for easy access!\n")
    printer.text("\n")
    printer.text("================================\n")
    printer.text("\n\n\n")
    printer.set(align="left")


def main():
    print("Mini Fax starting up...")

    # Connect to Twilio
    client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
    print(f"  Twilio connected (number: {config.TWILIO_PHONE_NUMBER})")

    # Connect to printer
    printer = init_printer()
    print(f"  Printer connected")

    # Print startup receipt
    try:
        print_startup_receipt(printer)
        print("  Startup receipt printed!")
    except Exception as e:
        print(f"  Could not print startup receipt: {e}")

    # Migrate contacts from config to JSON on first run
    if not os.path.exists("contacts.json"):
        initial = getattr(config, "ALLOWED_NUMBERS", {})
        if initial:
            with open("contacts.json", "w") as f:
                json.dump(initial, f, indent=2)
            print(f"  Migrated {len(initial)} contacts to contacts.json")

    # Load state so we don't reprint old messages
    printed_sids = load_printed_sids()

    # On first boot (no state file), mark all existing messages as printed
    # so we don't flood the printer with old messages
    if not printed_sids and not os.path.exists(config.STATE_FILE):
        print("  First boot — marking existing messages as printed...")
        try:
            since = datetime.now(timezone.utc) - timedelta(hours=24)
            existing = client.messages.list(to=config.TWILIO_PHONE_NUMBER, date_sent_after=since)
            for m in existing:
                printed_sids.add(m.sid)
            save_printed_sids(printed_sids)
            print(f"  Marked {len(printed_sids)} existing messages")
        except Exception as e:
            print(f"  Could not check existing messages: {e}")

    print(f"  {len(printed_sids)} messages already printed")

    print(f"  Polling every {config.POLL_INTERVAL}s — Ctrl+C to stop\n")

    try:
        while True:
            try:
                if poll_once(client, printer, printed_sids):
                    save_printed_sids(printed_sids)
            except Exception as e:
                print(f"  Error: {e}")
            time.sleep(config.POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nMini Fax shutting down.")
        save_printed_sids(printed_sids)


if __name__ == "__main__":
    main()
