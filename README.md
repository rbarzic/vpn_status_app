# ONIO Network Status

A small Python 3 panel indicator for **Ubuntu MATE 24.04**. It sends one ICMP
ping to `ansible.onio.com` every second:

- **Green with a check mark:** reachable, with no recovery period pending.
- **Red with a cross:** the last ping failed, timed out, or could not resolve the hostname.
- **Orange with a clock:** pings are succeeding again, but recovery is still in progress.

After any failed ping, the icon stays orange from the first successful reply
until a successful reply at least **five seconds later**, with no failed probes
in between. Another failure immediately turns it red and resets the recovery
period. The menu shows recovery progress.

The icon starts red; the first successful check turns it green immediately if
no failure has been observed. Click the icon for the current status and **Quit**. Probes run in a background thread, not on the UI
thread. There are no overlapping probes; each probe has a one-second timeout.

This checks **reachability of this host**, not general Internet connectivity or
VPN state. A firewall blocking ICMP also produces a red icon. Each probe resolves
the hostname again so DNS/address changes are picked up.

## Install dependencies

Use Ubuntu's system Python, not a virtual environment, because GTK and the
indicator bindings are installed by apt:

```sh
sudo apt update
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 iputils-ping
```

## Run

From this directory, in your logged-in MATE desktop session:

```sh
/usr/bin/python3 network_status.py
```

Keep the `icons/` directory beside `network_status.py`. No root privileges are
needed to run the app. Do not launch it with `sudo`.

If no icon appears, right-click the MATE panel → **Add to Panel** and ensure
**Indicator Applet Complete** is present. On a minimal MATE installation, install
it with `sudo apt install mate-indicator-applet`, then add it to the panel.

You can independently check the target with:

```sh
ping -n -c 1 -W 1 ansible.onio.com
```

## Start automatically at login (optional)

Open **Control Center → Startup Applications → Add**, and use:

- **Name:** ONIO Network Status
- **Command:** `/usr/bin/python3 /absolute/path/to/vpn_status_app/network_status.py`
- **Comment:** Show whether ansible.onio.com is reachable

Replace the path with the actual location of this checkout. Quote the script
path if it contains spaces. Leave the files in that location afterward. Start
only one instance to avoid duplicate icons. To stop autostarting, remove or
uncheck the entry in Startup Applications.

## Tests

The tests use mocked pings and do not require GTK, a desktop session, or network
access:

```sh
/usr/bin/python3 -m unittest discover -s tests -v
```

To change the target, edit `HOST` near the top of `network_status.py`.
