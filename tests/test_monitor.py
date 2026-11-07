"""Synthetic status transitions only. No network, desktop or hardware."""
import sys
from datetime import datetime, timezone
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
from washer_monitor.monitor import Monitor

WALL = 1800000000


def sample(state="Washing", offset=0, remaining=53, error=0, online=True):
    return {"online": online, "properties": {"status": state, "course": "Cotton", "remaining_time": remaining,
        "last_status_at": datetime.fromtimestamp(WALL + offset, timezone.utc).isoformat(), "error_code": error}}


class MonitorTests(unittest.TestCase):
    def feed(self, monitor, state="Washing", seconds=0, remaining=53, **kwargs):
        return monitor.observe(sample(state, seconds, remaining, **kwargs), seconds, WALL + seconds)

    def test_drying_finished_are_edges_and_repeated_polls_are_quiet(self):
        m = Monitor()
        self.assertEqual(self.feed(m), [])
        self.assertEqual([n.kind for n in self.feed(m, "Drying", 60)], ["drying"])
        self.assertEqual(self.feed(m, "Drying", 60), [])
        self.assertEqual([n.kind for n in self.feed(m, "Finished", 120, 0)], ["finished"])
        self.assertEqual(self.feed(m, "Finished", 120, 0), [])

    def test_startup_finished_does_not_invent_a_completion(self):
        self.assertEqual(self.feed(Monitor(), "Finished", remaining=0), [])

    def test_stale_cache_is_not_progress_or_proof_of_stall(self):
        m = Monitor()
        initial = sample()
        m.observe(initial, 0, WALL)
        result = m.observe(initial, 1900, WALL + 1900)
        self.assertEqual([n.kind for n in result], ["stale"])
        self.assertNotIn("stuck", m.sent)
        self.assertEqual(m.observe(initial, 2000, WALL + 2000), [])

    def test_stuck_requires_new_recent_reports_and_recovers_with_progress(self):
        m = Monitor()
        self.feed(m)
        for second in range(10, 1800, 10):
            self.feed(m, seconds=second)
        self.assertEqual([n.kind for n in self.feed(m, seconds=1800)], ["stuck"])
        self.assertEqual(self.feed(m, seconds=1810), [])
        self.assertEqual(self.feed(m, seconds=1820, remaining=52), [])
        self.assertNotIn("stuck", m.sent)
        for second in range(1830, 3620, 10):
            self.feed(m, seconds=second, remaining=52)
        self.assertEqual([n.kind for n in self.feed(m, seconds=3620, remaining=52)], ["stuck"])

    def test_errors_deduplicate_and_recovery_rearms(self):
        m = Monitor()
        self.assertEqual([n.kind for n in self.feed(m, "Error", error=2)], ["error"])
        self.assertEqual(self.feed(m, "Error", 10, error=2), [])
        self.feed(m, seconds=20)
        self.assertEqual([n.kind for n in self.feed(m, "Error", 30, error=2)], ["error"])

    def test_connection_grace_recovery_and_no_false_completion(self):
        m = Monitor()
        self.feed(m)
        self.assertEqual(m.lost(10), [])
        self.assertEqual([n.kind for n in m.lost(130)], ["offline"])
        self.assertEqual(m.lost(140), [])
        self.assertEqual([n.kind for n in self.feed(m, seconds=150)], ["reconnected"])
        self.assertEqual([n.kind for n in self.feed(m, "Off", 160)], ["stopped"])

    def test_restart_preserves_transition_but_not_old_stall_timer(self):
        m = Monitor()
        m.restore(sample()["properties"], 1000)
        self.assertEqual([n.kind for n in self.feed(m, "Finished", 1100, 0)], ["finished"])
        m = Monitor()
        m.restore(sample()["properties"], 1000)
        self.assertEqual(self.feed(m, seconds=1100), [])

    def test_paused_gets_one_reminder_without_stall_alert(self):
        m = Monitor()
        self.feed(m, "Paused")
        for second in range(10, 300, 10):
            self.feed(m, "Paused", second)
        self.assertEqual([n.kind for n in self.feed(m, "Paused", 300)], ["paused"])
        self.assertEqual(self.feed(m, "Paused", 400), [])

    def test_unobserved_interval_does_not_prove_a_stall(self):
        m = Monitor()
        self.feed(m)
        self.assertEqual(self.feed(m, seconds=2000), [])
        m.lost(2010)
        self.assertEqual(self.feed(m, seconds=4000), [])

    def test_old_or_invalid_report_cannot_signal_completion(self):
        m = Monitor()
        self.feed(m, seconds=100)
        self.assertEqual(self.feed(m, "Finished", 50, 0), [])
        self.assertEqual(m.previous["status"], "Washing")
        self.assertEqual(m.observe({"online": True, "properties": {}}, 120, WALL + 120), [])
        self.assertEqual([n.kind for n in m.observe({"online": True, "properties": {}}, 240, WALL + 240)], ["offline"])


if __name__ == "__main__":
    unittest.main()
