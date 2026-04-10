# Mini Fax

A tiny thermal printer that prints text messages. Text its phone number from anywhere in the world and your message prints out on a little receipt.

Built on a Raspberry Pi with a USB thermal printer and Twilio for SMS. No app needed — just text a phone number.

**Features:**
- Text the number, message prints instantly
- Wi-Fi setup via phone (no monitor/keyboard needed after initial setup)
- Web-based contacts manager at `mini-fax.local` — control who can send messages and give them names on the printouts
- Prints a startup receipt with the phone number and setup instructions every time it boots
- Survives reboots, auto-restarts on failure

**Ongoing cost:** ~$1.50/month (Twilio phone number + incoming SMS)

---

## What You Need

| Item | Price | Link |
|------|-------|------|
| Raspberry Pi 3 Model A+ | ~$25 | [Adafruit](https://www.adafruit.com/product/4027) |
| Pi Case (base) | ~$5 | [Adafruit](https://www.adafruit.com/product/2361) |
| Pi Case (lid) | ~$5 | [Adafruit](https://www.adafruit.com/product/2360) |
| NETUM NT-1809 58mm Thermal Printer | ~$22 | [Amazon](https://www.amazon.com/dp/B0919HGLSH) |
| USB-A to USB-B Cable | ~$7 | [Amazon](https://www.amazon.com/dp/B08BZD66H4) |
| Micro USB power supply (5V 2.5A+) | ~$8 | Any phone charger works |
| Micro SD card (8GB or larger) | ~$8 | Any brand works |
| Micro SD card reader | ~$8 | Any USB reader works (skip if your computer has a built-in SD slot) |

**Total: ~$75–90**

---

## Step 1: Flash the Raspberry Pi

1. Download and install [Raspberry Pi Imager](https://www.raspberrypi.com/software/) on your computer.

2. Insert the micro SD card into your computer.

3. Open Raspberry Pi Imager and choose:
   - **Device:** Raspberry Pi 3
   - **OS:** Raspberry Pi OS Lite (64-bit) — under "Raspberry Pi OS (other)"
   - **Storage:** Your SD card

4. Click **Next**, then **Edit Settings** and configure:
   - **Hostname:** `mini-fax`
   - **Username / Password:** Pick something you'll remember (e.g. `pi` / `your-password`)
   - **Wi-Fi:** Enter YOUR Wi-Fi network (for initial setup — the recipient will change this later)
   - **Enable SSH:** Yes, use password authentication

5. Flash the card, put it in the Pi, and plug in power. Wait about 2 minutes for it to boot.

6. Find the Pi on your network. Try:

```
ping mini-fax.local
```

If that doesn't work, check your router's admin page for connected devices.

7. SSH in:

```
ssh your-username@mini-fax.local
```

---

## Step 2: Set Up Twilio

You need a Twilio account to get a phone number that receives texts.

1. Go to [twilio.com](https://www.twilio.com) and create an account.

2. From the [Twilio Console](https://console.twilio.com), note your **Account SID** and **Auth Token**.

3. Buy a phone number:
   - Go to **Phone Numbers** → **Buy a Number**
   - Pick any US number you like (~$1.15/month)
   - Note the number (e.g. `+16625478683`)

4. That's it — Mini Fax polls Twilio's API directly, so no webhook or server setup is needed.

**If you're building multiple Mini Fax units:** You only need one Twilio account. Just buy an additional phone number for each unit (~$1.15/month each). They all share the same Account SID and Auth Token.

---

## Step 3: Install Mini Fax Software

SSH into the Pi and run these commands. Each one is a single line — copy and paste them one at a time.

**Install system dependencies:**

```
sudo apt update && sudo apt install -y python3-venv python3-pip libusb-1.0-0-dev git
```

**Get the code onto the Pi:**

Option A — Clone from GitHub:
```
git clone https://github.com/Cheem-cloud/mini-fax.git ~/mini-fax
```

Option B — If you received the files as a zip, copy them to the Pi:
```
scp -r /path/to/mini-fax your-username@mini-fax.local:~/mini-fax
```

Run that `scp` command from your computer (not from the Pi). Replace `/path/to/mini-fax` with wherever you unzipped the files.

**Set up Python environment:**

```
cd ~/mini-fax && python3 -m venv venv && venv/bin/pip install -r requirements.txt
```

**Create your config file:**

```
cp config.example.py config.py && nano config.py
```

Fill in your Twilio credentials and phone number. The printer USB IDs (0x0416 / 0x5011) are already set for the NETUM NT-1809.

---

## Step 4: Set Up the Printer

1. Plug the printer into the Pi's USB port with the USB-A to USB-B cable.

2. Turn on the printer (switch on the side).

3. Verify the Pi sees it:

```
lsusb
```

You should see a line like: `Bus 001 Device 002: ID 0416:5011` — those are the vendor/product IDs.

4. Create a udev rule so the printer is always accessible:

```
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0416", ATTR{idProduct}=="5011", MODE="0666"' | sudo tee /etc/udev/rules.d/99-thermal-printer.rules
```

5. Reload udev rules:

```
sudo udevadm control --reload-rules && sudo udevadm trigger
```

6. Test the printer:

```
cd ~/mini-fax && venv/bin/python test_print.py
```

---

## Step 5: Set the Hostname

This makes the contacts manager available at `http://mini-fax.local` on the local network.

```
sudo hostnamectl set-hostname mini-fax
```

Verify avahi (mDNS) is running:

```
sudo systemctl enable avahi-daemon && sudo systemctl start avahi-daemon
```

---

## Step 6: Install Services

These systemd services make everything start automatically on boot.

**Copy service files:**

```
sudo cp ~/mini-fax/wifi-setup.service /etc/systemd/system/ && sudo cp ~/mini-fax/mini-fax.service /etc/systemd/system/ && sudo cp ~/mini-fax/contacts-web.service /etc/systemd/system/
```

**Update the service files with your username** (if you didn't use `samcrocker09`):

```
sudo sed -i "s/samcrocker09/$(whoami)/g" /etc/systemd/system/wifi-setup.service /etc/systemd/system/mini-fax.service /etc/systemd/system/contacts-web.service
```

**Enable and start everything:**

```
sudo systemctl daemon-reload && sudo systemctl enable wifi-setup mini-fax contacts-web && sudo systemctl start mini-fax contacts-web
```

The printer should print a startup receipt. If it does, everything is working.

---

## Step 7: Add Contacts

Open `http://mini-fax.local` in a browser on any device connected to the same Wi-Fi. You'll see the contacts manager where you can add names and phone numbers.

Only people in the contacts list can send messages to the printer.

---

## Step 8 (Optional): Remote Access with Tailscale

If you want to manage the Mini Fax remotely (SSH in from anywhere, check logs, update contacts), install Tailscale:

```
curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up --ssh
```

Follow the link it prints to log in with your Tailscale account. Then from your own computer (with Tailscale installed), you can SSH in from anywhere:

```
ssh your-username@mini-fax
```

Free for personal use. The recipient never needs to know about it.

---

## Giving It to Someone

### Before you ship it

1. Flash the SD card and do all the setup above on YOUR Wi-Fi
2. Verify everything works — text the number, confirm it prints
3. Add their initial contacts through the web UI
4. Install Tailscale so you can help remotely
5. Forget your Wi-Fi network so the setup portal runs on first boot:

```
sudo nmcli con delete "YourWiFiName" && sudo shutdown -h now
```

### What to put in the box

- Pi (in case, SD card inserted)
- Thermal printer
- USB cable
- Power supply
- A spare roll of thermal paper
- The instruction card (below)

### Instruction card

Print or write this on a card to include in the box:

> **Mini Fax Setup**
>
> 1. Plug the USB cable from the printer into the Pi
> 2. Plug in the printer's power cable
> 3. Plug in the Pi's power cable
> 4. Wait 1–2 minutes
> 5. On your phone, go to Wi-Fi settings and connect to **Mini-Fax-Setup** (password: **minifax123**)
> 6. A setup page will open — pick your home Wi-Fi and enter the password
> 7. Wait for the printer to print a receipt — that means it worked!
>
> The receipt has the phone number to text and a link to manage contacts.
>
> **To add or remove contacts:** Open Safari and go to **mini-fax.local**
>
> **If it stops working:** Unplug the Pi, wait 10 seconds, plug it back in.

---

## How It Works

- **Wi-Fi setup:** On boot, if the Pi has no Wi-Fi connection, it creates a hotspot called "Mini-Fax-Setup". Connecting to it opens a page to pick a Wi-Fi network. Once connected, the hotspot goes away and the fax service starts.
- **Printing messages:** The Pi polls Twilio's API every 5 seconds for new incoming texts. If a message is from a contact in the list, it prints. Messages from unknown numbers are ignored.
- **Contacts:** Stored in `contacts.json`. Managed through the web UI at `http://mini-fax.local` or by editing the file directly over SSH.
- **Startup receipt:** Every time the Pi boots and connects, it prints a receipt with the phone number and the contacts management URL.

---

## Troubleshooting

**Printer doesn't print on boot:**
```
sudo journalctl -u mini-fax -n 50
```

**Contacts page not loading:**
```
sudo journalctl -u contacts-web -n 50
```

**Need to redo Wi-Fi setup:**
```
sudo nmcli con delete "NetworkName" && sudo reboot
```

**Check all service status:**
```
sudo systemctl status wifi-setup mini-fax contacts-web
```

**Restart everything:**
```
sudo systemctl restart mini-fax contacts-web
```
