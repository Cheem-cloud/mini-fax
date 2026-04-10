#!/usr/bin/env python3
"""
Wi-Fi Setup — captive portal for first-time configuration.

On boot, if the Pi isn't connected to Wi-Fi:
  1. Creates a hotspot called "Mini-Fax-Setup"
  2. Serves a web page where the user picks their Wi-Fi network
  3. Connects to the chosen network
  4. Exits so the fax service can start

Usage: sudo venv/bin/python wifi_setup.py
"""

import subprocess
import time
import os
import json
import sys
import threading
from html import escape as html_escape

from flask import Flask, request

app = Flask(__name__)

HOTSPOT_SSID = "Mini-Fax-Setup"
HOTSPOT_PASSWORD = "minifax123"

connection_state = {"status": "idle"}


# ── Network helpers ─────────────────────────────────────


def run(cmd):
    """Run a command and return (success, stdout, stderr)."""
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.stdout.strip():
        print(f"    stdout: {result.stdout.strip()}")
    if result.stderr.strip():
        print(f"    stderr: {result.stderr.strip()}")
    return result.returncode == 0, result.stdout, result.stderr


def is_wifi_connected():
    """Check if we're connected to a Wi-Fi network."""
    ok, out, _ = run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "dev"])
    if ok:
        for line in out.strip().split("\n"):
            parts = line.split(":")
            if len(parts) >= 3 and parts[1] == "wifi" and parts[2] == "connected":
                return True
    return False


def scan_networks():
    """Scan for available Wi-Fi networks."""
    run(["nmcli", "dev", "wifi", "rescan"])
    time.sleep(3)

    ok, out, _ = run(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"])
    if not ok:
        return []

    networks = []
    seen = set()
    for line in out.strip().split("\n"):
        parts = line.split(":")
        if len(parts) >= 2:
            ssid = parts[0].strip()
            signal = parts[1].strip() if len(parts) > 1 else "0"
            security = parts[2].strip() if len(parts) > 2 else ""
            if ssid and ssid not in seen and ssid != HOTSPOT_SSID and ssid != "--":
                seen.add(ssid)
                networks.append({"ssid": ssid, "signal": signal, "security": security})

    networks.sort(key=lambda n: int(n["signal"] or "0"), reverse=True)
    return networks


def start_hotspot():
    """Create a Wi-Fi hotspot."""
    print(f"\n  Creating hotspot '{HOTSPOT_SSID}'...")

    # Delete any old hotspot
    run(["nmcli", "con", "delete", "hotspot"])
    time.sleep(1)

    # Create new hotspot
    ok, out, err = run([
        "nmcli", "dev", "wifi", "hotspot",
        "ifname", "wlan0",
        "con-name", "hotspot",
        "ssid", HOTSPOT_SSID,
        "password", HOTSPOT_PASSWORD
    ])

    if ok:
        print(f"  Hotspot active!")
        print(f"  Connect to '{HOTSPOT_SSID}' (password: {HOTSPOT_PASSWORD})")
        print(f"  Then open http://10.42.0.1\n")
        return True

    # If that failed, try the manual way
    print("  Hotspot command failed, trying manual setup...")
    run(["nmcli", "con", "add", "type", "wifi", "ifname", "wlan0",
         "con-name", "hotspot", "autoconnect", "no",
         "ssid", HOTSPOT_SSID])
    run(["nmcli", "con", "modify", "hotspot",
         "802-11-wireless.mode", "ap",
         "802-11-wireless.band", "bg",
         "ipv4.method", "shared",
         "wifi-sec.key-mgmt", "wpa-psk",
         "wifi-sec.psk", HOTSPOT_PASSWORD])
    ok2, _, _ = run(["nmcli", "con", "up", "hotspot"])

    if ok2:
        print(f"  Hotspot active (manual method)!")
        return True

    print("  ERROR: Could not create hotspot.")
    return False


def stop_hotspot():
    """Stop the hotspot."""
    run(["nmcli", "con", "down", "hotspot"])
    run(["nmcli", "con", "delete", "hotspot"])


def connect_to_wifi(ssid, password):
    """Try to connect to a Wi-Fi network."""
    print(f"\n  Connecting to '{ssid}'...")

    # Stop hotspot first
    stop_hotspot()
    time.sleep(2)

    # Try simple connect first
    ok, _, _ = run(["nmcli", "dev", "wifi", "connect", ssid, "password", password])
    if ok:
        print(f"  Connected to '{ssid}'!")
        return True

    # Try manual connection as fallback
    print("  Simple connect failed, trying manual...")
    run(["nmcli", "con", "delete", ssid])
    run(["nmcli", "connection", "add",
         "type", "wifi", "ifname", "wlan0",
         "con-name", ssid, "ssid", ssid,
         "wifi-sec.key-mgmt", "wpa-psk",
         "wifi-sec.psk", password])
    ok2, _, _ = run(["nmcli", "connection", "up", ssid])

    if ok2:
        print(f"  Connected to '{ssid}' (manual method)!")
        return True

    print(f"  ERROR: Could not connect to '{ssid}'")
    return False


# ── Web interface ───────────────────────────────────────


HTML_SETUP = """<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Mini Fax Setup</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, sans-serif; max-width: 400px;
               margin: 30px auto; padding: 0 20px; color: #222;
               background: #f9f9f9; }
        h1 { font-size: 1.4em; text-align: center; }
        p.sub { text-align: center; color: #666; font-size: 14px; margin-top: -10px; }
        .net { background: white; border: 2px solid #ddd; border-radius: 8px;
               padding: 12px; margin-bottom: 8px; cursor: pointer; }
        .net:hover { border-color: #333; }
        .net .name { font-weight: 600; font-size: 16px; }
        .net .info { color: #888; font-size: 12px; margin-top: 2px; }
        .sig { float: right; font-size: 14px; color: #666; }
        .pwform { display: none; background: white; border: 2px solid #333;
                  border-radius: 8px; padding: 15px; margin-bottom: 10px; }
        .pwform.active { display: block; }
        .pwform label { font-size: 14px; font-weight: 600; display: block; margin-bottom: 5px; }
        .pwform input[type=password], .pwform input[type=text] {
            width: 100%%; padding: 10px; font-size: 16px;
            border: 2px solid #ccc; border-radius: 6px; margin-bottom: 10px; }
        .showpw { font-size: 13px; margin-bottom: 10px; display: flex;
                  align-items: center; gap: 5px; }
        .showpw input { width: 16px; height: 16px; }
        button { width: 100%%; padding: 12px; font-size: 16px; font-weight: 600;
                 background: #333; color: white; border: none; border-radius: 8px;
                 cursor: pointer; }
        button:active { background: #555; }
        .refresh { text-align: center; margin: 15px 0; }
        .refresh a { color: #666; font-size: 14px; }
        .err { background: #fee; border: 2px solid #c00; border-radius: 8px;
               padding: 12px; margin-bottom: 10px; color: #c00; font-weight: 600; }
    </style>
</head>
<body>
    <h1>Mini Fax Setup</h1>
    <p class="sub">Choose your Wi-Fi network</p>
    %(error)s
    %(networks)s
    <div class="refresh"><a href="/">Refresh networks</a></div>
    <script>
    function sel(id) {
        document.querySelectorAll('.pwform').forEach(function(f){f.classList.remove('active')});
        var el = document.getElementById('f-'+id);
        if(el) el.classList.add('active');
    }
    function tp(id) {
        var el = document.getElementById('p-'+id);
        el.type = el.type==='password' ? 'text' : 'password';
    }
    </script>
</body>
</html>"""


CONNECTING_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Mini Fax — Connecting</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, sans-serif; max-width: 400px;
               margin: 30px auto; padding: 0 20px; color: #222;
               background: #f9f9f9; }
        h1 { font-size: 1.4em; text-align: center; }
        .card { background: white; border-radius: 12px; padding: 20px;
                margin-bottom: 15px; border: 2px solid #ddd; }
        .spinner { display: inline-block; width: 20px; height: 20px;
                   border: 3px solid #ddd; border-top-color: #333;
                   border-radius: 50%; animation: spin 0.8s linear infinite;
                   vertical-align: middle; margin-right: 8px; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .step { margin-bottom: 14px; line-height: 1.5; }
        .step:last-child { margin-bottom: 0; }
        .check { color: #4caf50; font-weight: bold; margin-right: 6px; }
        .err { background: #fee; border-color: #c00; }
        .ok { background: #e8f5e9; border-color: #4caf50; }
        .tip { color: #666; font-size: 13px; margin-top: 12px; }
        button { width: 100%; padding: 12px; font-size: 16px; font-weight: 600;
                 background: #333; color: white; border: none; border-radius: 8px;
                 cursor: pointer; margin-top: 12px; }
        button:active { background: #555; }
    </style>
</head>
<body>
    <h1>Mini Fax Setup</h1>

    <div id="phase-testing" class="card">
        <div class="step">
            <span class="spinner"></span>
            Testing connection to <strong>{{SSID}}</strong>...
        </div>
    </div>

    <div id="phase-waiting" class="card" style="display:none">
        <div class="step">
            <span class="check">&#10003;</span> Credentials sent
        </div>
        <div class="step">
            <span class="check">&#10003;</span> Connecting to <strong>{{SSID}}</strong>
        </div>
        <div class="step" style="margin-top: 18px; font-size: 17px; font-weight: 600;">
            Now watch the printer!
        </div>
        <p class="tip">
            When it prints a receipt, setup is complete!
            The receipt has the phone number and instructions
            for managing your contacts.
        </p>
        <p class="tip">
            If <strong>Mini-Fax-Setup</strong> reappears in your Wi-Fi list,
            the connection didn't work &mdash; rejoin it to try again.
        </p>
        <p class="tip">
            If nothing happens after 2 minutes, unplug the Mini Fax, wait 10 seconds,
            and plug it back in.
        </p>
    </div>

    <div id="phase-failed" class="card err" style="display:none">
        <p style="font-weight: 600; font-size: 16px; margin-bottom: 8px; color: #c00;">
            Couldn't connect to {{SSID}}
        </p>
        <p style="font-size: 14px; color: #c00;">
            Double-check the password and try again.
        </p>
        <a href="/"><button>Try Again</button></a>
    </div>

    <div id="phase-success" class="card ok" style="display:none">
        <p style="font-weight: 600; font-size: 16px; margin-bottom: 8px;">
            Connected to {{SSID}}!
        </p>
        <p style="font-size: 14px;">
            The printer will print a confirmation receipt any moment now.
        </p>
    </div>

    <script>
    var pollFails = 0;
    var phase = "testing";

    function setPhase(p) {
        phase = p;
        ["testing","waiting","failed","success"].forEach(function(id) {
            document.getElementById("phase-" + id).style.display = id === p ? "block" : "none";
        });
    }

    function poll() {
        if (phase === "failed" || phase === "success") return;
        fetch("/status", {cache: "no-store"})
            .then(function(r) { return r.json(); })
            .then(function(data) {
                pollFails = 0;
                if (data.status === "failed") { setPhase("failed"); }
                else if (data.status === "success") { setPhase("success"); }
                else { setTimeout(poll, 2000); }
            })
            .catch(function() {
                pollFails++;
                if (pollFails >= 2 && phase === "testing") { setPhase("waiting"); }
                if (pollFails < 30) { setTimeout(poll, 3000); }
            });
    }

    setTimeout(poll, 1500);
    </script>
</body>
</html>"""


def build_page(networks, error=""):
    err_html = '<div class="err">'+error+'</div>' if error else ""
    net_html = ""
    for i, net in enumerate(networks):
        sig = int(net["signal"] or 0)
        bars = "|||" if sig > 70 else "||" if sig > 40 else "|"
        lock = "* " if net["security"] else ""
        net_html += (
            '<div class="net" onclick="sel('+str(i)+')">'
            '<span class="sig">'+bars+'</span>'
            '<div class="name">'+lock+net["ssid"]+'</div>'
            '<div class="info">Signal: '+net["signal"]+'%</div>'
            '</div>'
            '<div class="pwform" id="f-'+str(i)+'">'
            '<form method="POST" action="/connect">'
            '<input type="hidden" name="ssid" value="'+net["ssid"]+'">'
            '<label>Password for '+net["ssid"]+'</label>'
            '<input type="password" name="password" id="p-'+str(i)+'" placeholder="Enter Wi-Fi password">'
            '<label class="showpw"><input type="checkbox" onclick="tp('+str(i)+')"> Show password</label>'
            '<button type="submit">Connect</button>'
            '</form></div>'
        )
    return HTML_SETUP % {"networks": net_html, "error": err_html}


@app.route("/")
def home():
    connection_state["status"] = "idle"
    networks = scan_networks()
    if not networks:
        return build_page([], error="No networks found. Try refreshing.")
    return build_page(networks)


@app.route("/status")
def status():
    return json.dumps(connection_state), 200, {"Content-Type": "application/json"}


@app.route("/connect", methods=["POST"])
def connect():
    ssid = request.form.get("ssid", "").strip()
    password = request.form.get("password", "").strip()

    if not ssid or not password:
        return build_page(scan_networks(), error="Network and password required.")

    connection_state["status"] = "connecting"
    connection_state["ssid"] = ssid

    def do_connect():
        time.sleep(4)  # Let the page load and start polling
        success = connect_to_wifi(ssid, password)
        if success:
            connection_state["status"] = "success"
            print(f"\n  SUCCESS! Connected to '{ssid}'")
            print("  Exiting setup — fax service will start.\n")
            time.sleep(3)
            os._exit(0)
        else:
            connection_state["status"] = "failed"
            print(f"\n  FAILED to connect to '{ssid}'")
            print("  Restarting hotspot...\n")
            start_hotspot()

    threading.Thread(target=do_connect, daemon=True).start()

    safe_ssid = html_escape(ssid)
    return CONNECTING_HTML.replace("{{SSID}}", safe_ssid)


# ── Main ────────────────────────────────────────────────


def main():
    print("\n============================")
    print("  Mini Fax Wi-Fi Setup")
    print("============================\n")

    if is_wifi_connected():
        print("  Already connected to Wi-Fi. Exiting setup.\n")
        return

    print("  No Wi-Fi connection found.")

    if not start_hotspot():
        print("  Could not start hotspot. Will retry in 10 seconds...")
        time.sleep(10)
        if not start_hotspot():
            print("  Hotspot failed twice. Exiting.")
            sys.exit(1)

    time.sleep(2)

    print("  Starting web server on port 80...")
    sys.stdout.flush()
    app.run(host="0.0.0.0", port=80)


if __name__ == "__main__":
    main()
