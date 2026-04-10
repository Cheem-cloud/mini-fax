#!/usr/bin/env python3
"""
Contacts Manager — web UI for managing who can send messages to the Mini Fax.

Serves a simple page where users can add/remove phone numbers and names.
Stores contacts in contacts.json, which the fax service also reads.

Run directly:  python3 contacts_web.py
Or as a service: see contacts-web.service
"""

import json
import os
import re
from html import escape as html_escape

from flask import Flask, request

app = Flask(__name__)

CONTACTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contacts.json")


def load_contacts():
    """Load contacts from JSON file."""
    try:
        with open(CONTACTS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_contacts(contacts):
    """Save contacts to JSON file."""
    with open(CONTACTS_FILE, "w") as f:
        json.dump(contacts, f, indent=2)


def normalize_phone(raw):
    """Normalize a phone number to E.164 format (+1XXXXXXXXXX)."""
    digits = re.sub(r'\D', '', raw)
    if len(digits) == 10:
        digits = "1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return None


def format_phone(e164):
    """Format +1XXXXXXXXXX as (XXX) XXX-XXXX."""
    if len(e164) == 12 and e164.startswith("+1"):
        return f"({e164[2:5]}) {e164[5:8]}-{e164[8:12]}"
    return e164


HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Mini Fax</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, sans-serif; max-width: 400px;
               margin: 30px auto; padding: 0 20px; color: #222;
               background: #f9f9f9; }
        h1 { font-size: 1.4em; text-align: center; }
        p.sub { text-align: center; color: #666; font-size: 14px; margin-top: -10px; }
        .contact { background: white; border: 2px solid #ddd; border-radius: 8px;
                   padding: 12px 14px; margin-bottom: 8px; display: flex;
                   align-items: center; justify-content: space-between; }
        .contact .name { font-weight: 600; font-size: 16px; }
        .contact .phone { color: #888; font-size: 13px; margin-top: 2px; }
        .remove { background: none; border: 2px solid #ddd; border-radius: 6px;
                  padding: 6px 12px; font-size: 13px; color: #c00; cursor: pointer;
                  font-weight: 600; width: auto; }
        .remove:active { border-color: #c00; background: #fee; }
        .add-form { background: white; border: 2px solid #ddd; border-radius: 8px;
                    padding: 15px; margin-top: 20px; }
        .add-form h2 { font-size: 1.1em; margin: 0 0 12px 0; }
        .add-form input[type=text] {
            width: 100%%; padding: 10px; font-size: 16px;
            border: 2px solid #ccc; border-radius: 6px; margin-bottom: 10px; }
        button { width: 100%%; padding: 12px; font-size: 16px; font-weight: 600;
                 background: #333; color: white; border: none; border-radius: 8px;
                 cursor: pointer; }
        button:active { background: #555; }
        .empty { text-align: center; color: #999; padding: 20px; font-size: 14px; }
        .err { background: #fee; border: 2px solid #c00; border-radius: 8px;
               padding: 12px; margin-bottom: 10px; color: #c00; font-weight: 600;
               font-size: 14px; }
        .ok { background: #e8f5e9; border: 2px solid #4caf50; border-radius: 8px;
              padding: 12px; margin-bottom: 10px; color: #2e7d32; font-weight: 600;
              font-size: 14px; }
    </style>
</head>
<body>
    <h1>Mini Fax</h1>
    <p class="sub">People who can send messages</p>
    %(message)s
    %(contacts)s
    <div class="add-form">
        <h2>Add someone</h2>
        <form method="POST" action="/add">
            <input type="text" name="name" placeholder="Name" required>
            <input type="text" name="phone" placeholder="Phone number"
                   inputmode="tel" required>
            <button type="submit">Add</button>
        </form>
    </div>
</body>
</html>"""


@app.route("/")
def home():
    return render_page()


@app.route("/add", methods=["POST"])
def add():
    name = request.form.get("name", "").strip()
    raw_phone = request.form.get("phone", "").strip()

    if not name or not raw_phone:
        return render_page(error="Name and phone number are required.")

    phone = normalize_phone(raw_phone)
    if not phone:
        return render_page(error="Enter a 10-digit US phone number.")

    contacts = load_contacts()

    if phone in contacts:
        return render_page(error=f"{html_escape(contacts[phone])} already has that number.")

    contacts[phone] = name
    save_contacts(contacts)
    return render_page(success=f"{html_escape(name)} added!")


@app.route("/remove", methods=["POST"])
def remove():
    phone = request.form.get("phone", "").strip()
    contacts = load_contacts()

    if phone in contacts:
        name = contacts.pop(phone)
        save_contacts(contacts)
        return render_page(success=f"{html_escape(name)} removed.")

    return render_page(error="That contact wasn't found.")


def render_page(error="", success=""):
    contacts = load_contacts()

    msg_html = ""
    if error:
        msg_html = '<div class="err">' + error + '</div>'
    elif success:
        msg_html = '<div class="ok">' + success + '</div>'

    if not contacts:
        contacts_html = '<div class="empty">No contacts yet. Add someone below!</div>'
    else:
        contacts_html = ""
        for phone, name in sorted(contacts.items(), key=lambda x: x[1].lower()):
            contacts_html += (
                '<div class="contact">'
                '<div class="info">'
                '<div class="name">' + html_escape(name) + '</div>'
                '<div class="phone">' + html_escape(format_phone(phone)) + '</div>'
                '</div>'
                '<form method="POST" action="/remove" style="margin:0">'
                '<input type="hidden" name="phone" value="' + html_escape(phone) + '">'
                '<button type="submit" class="remove">Remove</button>'
                '</form></div>'
            )

    return HTML_PAGE % {"contacts": contacts_html, "message": msg_html}


if __name__ == "__main__":
    if not os.path.exists(CONTACTS_FILE):
        save_contacts({})
    app.run(host="0.0.0.0", port=80)
