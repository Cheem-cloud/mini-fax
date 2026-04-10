# Mini Fax — Configuration
# Copy this file to config.py and fill in your values:
#   cp config.example.py config.py

# ── Twilio credentials (from https://console.twilio.com) ──
TWILIO_ACCOUNT_SID = "your_account_sid"
TWILIO_AUTH_TOKEN = "your_auth_token"
TWILIO_PHONE_NUMBER = "+1234567890"  # Your Twilio number

# ── Who can send messages to the printer ──
# Contacts are managed through the web UI at http://mini-fax.local
# and stored in contacts.json. You can also seed them here — on first
# boot, these will be copied to contacts.json automatically.
ALLOWED_NUMBERS = {
    "+1XXXXXXXXXX": "Sam",
    "+1XXXXXXXXXX": "Kendall",
}

# ── Printer USB IDs ──
# Find these by running: lsusb
# Look for your printer and note the ID like "0416:5011"
# That means vendor=0x0416, product=0x5011
PRINTER_VENDOR_ID = 0x0000
PRINTER_PRODUCT_ID = 0x0000

# Uncomment these if you get "Invalid endpoint address" errors.
# Find the correct values with: lsusb -v -d VENDOR:PRODUCT | grep bEndpointAddress
# PRINTER_IN_EP = 0x81
# PRINTER_OUT_EP = 0x03

# ── Polling settings ──
POLL_INTERVAL = 5  # seconds between checks for new messages

# File to remember which messages have already been printed.
# This survives restarts so you don't get duplicate prints.
STATE_FILE = "printed_messages.json"
