#!/usr/bin/python3
"""MATE panel indicator for reachability of ansible.onio.com."""

from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time

HOST = "ansible.onio.com"
INTERVAL_SECONDS = 1.0
RECOVERY_SECONDS = 5.0


def ping_host(host: str, ping_binary: str = "ping") -> bool:
    """Send one ICMP probe, allowing at most one second for a reply.

    The outer timeout also bounds failures such as slow DNS resolution.
    No shell is used, and stdout/stderr are deliberately discarded.
    """
    try:
        result = subprocess.run(
            [ping_binary, "-n", "-c", "1", "-W", "1", host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=INTERVAL_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


class NetworkStatus:
    def __init__(self, Gtk, GLib, AppIndicator3, ping_binary: str):
        self.Gtk = Gtk
        self.GLib = GLib
        self.ping_binary = ping_binary
        self.stopped = threading.Event()
        self.recovery_required = False
        self.recovery_started = None
        self.icons = Path(__file__).resolve().parent / "icons"
        self.indicator = AppIndicator3.Indicator.new(
            "onio-network-status",
            str(self.icons / "network-offline.svg"),
            AppIndicator3.IndicatorCategory.SYSTEM_SERVICES,
        )
        self.indicator.set_title("ONIO Network Status")
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        menu = Gtk.Menu()
        self.status_item = Gtk.MenuItem(label=f"{HOST}: checking…")
        self.status_item.set_sensitive(False)
        menu.append(self.status_item)
        menu.append(Gtk.SeparatorMenuItem())
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self.quit)
        menu.append(quit_item)
        menu.show_all()
        self.indicator.set_menu(menu)

    def update_status(self, reachable: bool):
        if self.stopped.is_set():
            return False
        if not reachable:
            self.recovery_required = True
            self.recovery_started = None
            state = "offline"
            message = "no reply"
        elif self.recovery_required:
            now = time.monotonic()
            if self.recovery_started is None:
                self.recovery_started = now
            elapsed = now - self.recovery_started
            if elapsed >= RECOVERY_SECONDS:
                self.recovery_required = False
                self.recovery_started = None
                state = "online"
                message = "reachable"
            else:
                state = "recovering"
                message = f"recovering ({elapsed:.0f}/{RECOVERY_SECONDS:.0f}s of successful pings)"
        else:
            state = "online"
            message = "reachable"
        description = f"{HOST}: {message}"
        self.indicator.set_icon_full(
            str(self.icons / f"network-{state}.svg"), description
        )
        self.status_item.set_label(description)
        return False  # GLib idle callbacks must run only once.

    def monitor(self):
        # One worker prevents overlapping probes; the GTK thread stays responsive.
        while not self.stopped.is_set():
            started = time.monotonic()
            reachable = ping_host(HOST, self.ping_binary)
            if self.stopped.is_set():
                break
            self.GLib.idle_add(self.update_status, reachable)
            self.stopped.wait(max(0.0, INTERVAL_SECONDS - (time.monotonic() - started)))

    def quit(self, *_args):
        self.stopped.set()
        self.Gtk.main_quit()

    def run(self):
        self.GLib.unix_signal_add(self.GLib.PRIORITY_DEFAULT, signal.SIGINT, self.quit)
        self.GLib.unix_signal_add(self.GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.quit)
        worker = threading.Thread(target=self.monitor, daemon=True)
        worker.start()
        try:
            self.Gtk.main()
        finally:
            self.stopped.set()
            worker.join(timeout=2)


def main() -> int:
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import AyatanaAppIndicator3, GLib, Gtk
    except (ImportError, ValueError) as error:
        print(
            f"Missing desktop dependency: {error}\n"
            "Install with: sudo apt install python3-gi gir1.2-gtk-3.0 "
            "gir1.2-ayatanaappindicator3-0.1 iputils-ping",
            file=sys.stderr,
        )
        return 1

    ping_binary = shutil.which("ping")
    if ping_binary is None:
        print("Missing ping command. Install with: sudo apt install iputils-ping", file=sys.stderr)
        return 1

    NetworkStatus(Gtk, GLib, AyatanaAppIndicator3, ping_binary).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
