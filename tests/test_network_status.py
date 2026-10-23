import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from network_status import NetworkStatus, ping_host


class PingHostTests(unittest.TestCase):
    @patch("network_status.subprocess.run")
    def test_success(self, run):
        run.return_value.returncode = 0
        self.assertTrue(ping_host("ansible.onio.com", "/usr/bin/ping"))
        run.assert_called_once_with(
            ["/usr/bin/ping", "-n", "-c", "1", "-W", "1", "ansible.onio.com"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1.0,
            check=False,
        )

    @patch("network_status.subprocess.run")
    def test_failure_exit_codes(self, run):
        for code in (1, 2, -15):
            with self.subTest(code=code):
                run.return_value.returncode = code
                self.assertFalse(ping_host("ansible.onio.com"))

    @patch("network_status.subprocess.run", side_effect=subprocess.TimeoutExpired("ping", 1))
    def test_timeout_is_offline(self, _run):
        self.assertFalse(ping_host("ansible.onio.com"))

    @patch("network_status.subprocess.run", side_effect=FileNotFoundError)
    def test_missing_binary_is_offline(self, _run):
        self.assertFalse(ping_host("ansible.onio.com"))

    @patch("network_status.subprocess.run", side_effect=PermissionError)
    def test_permission_error_is_offline(self, _run):
        self.assertFalse(ping_host("ansible.onio.com"))


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.app = NetworkStatus.__new__(NetworkStatus)
        self.app.stopped = Mock()
        self.app.stopped.is_set.return_value = False
        self.app.recovery_required = False
        self.app.recovery_started = None
        self.app.icons = Path("icons")
        self.app.indicator = Mock()
        self.app.status_item = Mock()

    def check_status(self, reachable, now, expected):
        with patch("network_status.time.monotonic", return_value=now):
            self.assertFalse(self.app.update_status(reachable))
        icon, _description = self.app.indicator.set_icon_full.call_args.args
        self.assertEqual(Path(icon).name, f"network-{expected}.svg")

    def test_first_success_without_loss_is_green(self):
        self.check_status(True, 0, "online")

    def test_loss_requires_five_full_seconds_of_success(self):
        self.check_status(False, 0, "offline")
        self.check_status(True, 10, "recovering")
        for now in (11, 12, 13, 14, 14.999):
            self.check_status(True, now, "recovering")
        self.check_status(True, 15, "online")
        self.check_status(True, 16, "online")

    def test_failure_during_recovery_resets_timer(self):
        self.check_status(False, 0, "offline")
        self.check_status(True, 1, "recovering")
        self.check_status(True, 5, "recovering")
        self.check_status(False, 6, "offline")
        self.check_status(True, 7, "recovering")
        self.check_status(True, 11, "recovering")
        self.check_status(True, 12, "online")
        self.check_status(False, 13, "offline")
        self.check_status(True, 14, "recovering")

    def test_time_offline_does_not_count_as_recovery(self):
        self.check_status(False, 0, "offline")
        self.check_status(False, 100, "offline")
        self.check_status(True, 200, "recovering")
        self.check_status(True, 204, "recovering")
        self.check_status(True, 205, "online")

    def test_stopped_app_does_not_update_indicator(self):
        self.app.stopped.is_set.return_value = True
        self.assertFalse(self.app.update_status(True))
        self.app.indicator.set_icon_full.assert_not_called()


class MonitorTests(unittest.TestCase):
    @patch("network_status.time.monotonic", side_effect=[10.0, 10.25])
    @patch("network_status.ping_host", return_value=True)
    def test_probe_result_is_dispatched_and_interval_accounts_for_probe_time(self, ping, _clock):
        app = NetworkStatus.__new__(NetworkStatus)
        app.ping_binary = "/usr/bin/ping"
        app.GLib = Mock()
        app.stopped = Mock()
        app.stopped.is_set.side_effect = [False, False, True]
        app.monitor()
        ping.assert_called_once_with("ansible.onio.com", "/usr/bin/ping")
        app.GLib.idle_add.assert_called_once_with(app.update_status, True)
        app.stopped.wait.assert_called_once_with(0.75)


if __name__ == "__main__":
    unittest.main()
