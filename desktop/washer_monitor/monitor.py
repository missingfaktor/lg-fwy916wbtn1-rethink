"""Notification rules, independent of Qt and tested without a real appliance."""
from dataclasses import dataclass
from datetime import datetime

ACTIVE = {"Detecting", "Washing", "Rinsing", "Spinning", "Drying", "Cooling down"}


def report_time(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None


@dataclass(frozen=True)
class Notice:
    kind: str
    title: str
    body: str
    urgent: bool = False


class Monitor:
    def __init__(self, stale_minutes=15, stuck_minutes=30, offline_seconds=120):
        self.stale_seconds = stale_minutes * 60
        self.stuck_seconds = stuck_minutes * 60
        self.offline_seconds = offline_seconds
        self.previous = None
        self.progress = None
        self.progress_at = None
        self.pause_at = None
        self.failure_at = None
        self.sent = set()
        self.last_sample_at = None
        self.problem = None

    def restore(self, previous, now):
        # Retain transition deduplication, never invent elapsed progress across restart.
        if isinstance(previous, dict) and report_time(previous.get("last_status_at")) is not None:
            self.previous = previous
        self.progress_at = now

    def lost(self, now, reason="The local server or washer is unavailable."):
        self.problem = reason
        if self.failure_at is None:
            self.failure_at = now
        if now - self.failure_at >= self.offline_seconds and "offline" not in self.sent:
            self.sent.add("offline")
            return [Notice("offline", "Washer connection lost", reason + " Completion cannot be confirmed.", True)]
        return []

    def observe(self, sample, now, wall):
        if not isinstance(sample, dict) or sample.get("online") is not True:
            return self.lost(now, "Rethink cannot currently see the washer.")
        p = sample.get("properties")
        if not isinstance(p, dict):
            return self.lost(now, "The server returned no readable washer status.")
        stamp = report_time(p.get("last_status_at"))
        if stamp is None or stamp > wall + 300 or not isinstance(p.get("status"), str):
            return self.lost(now, "Waiting for a valid status report from the washer.")
        age = max(0, wall - stamp)
        self.problem = None
        notices = []
        if self.failure_at is not None or (self.last_sample_at is not None and now - self.last_sample_at > 45):
            # An unobserved interval (sleep/network outage) cannot establish a stall.
            self.progress_at = now
            self.pause_at = now if p["status"] == "Paused" else None
            self.sent.discard("stuck")
        if "offline" in self.sent:
            notices.append(Notice("reconnected", "Washer reconnected", "Local monitoring is available again."))
        self.sent.discard("offline")
        self.failure_at = None
        state = p["status"]
        old = self.previous
        old_state = old.get("status") if old else None
        old_stamp = report_time(old.get("last_status_at")) if old else None
        # Ignore regressed/cached reports for transitions. Polling GETs are not new reports.
        fresh = age < self.stale_seconds
        newer = old_stamp is None or stamp > old_stamp
        if old_stamp is not None and stamp < old_stamp:
            self.problem = "The server is returning an older report; waiting for a new one."
            return notices
        fingerprint = tuple(p.get(k) for k in ("status", "course", "remaining_time"))
        if fingerprint != self.progress or self.progress_at is None:
            self.progress, self.progress_at = fingerprint, now
            self.sent.discard("stuck")
        if state != "Paused":
            self.pause_at = None
            self.sent.discard("paused")
        elif self.pause_at is None:
            self.pause_at = now
        if fresh and newer:
            if old_state and state == "Drying" and old_state != "Drying":
                notices.append(Notice("drying", "Washer started drying", f"{p.get('course', 'Cycle')} · drying stage has begun."))
            if old_state in ACTIVE | {"Paused"} and state == "Finished":
                notices.append(Notice("finished", "Laundry finished", "The washer reports the cycle has finished. Your laundry is ready."))
            if old_state in ACTIVE and state == "Off":
                notices.append(Notice("stopped", "Washer switched off", "The cycle was active, but the washer now reports Off. Completion was not confirmed.", True))
        error = p.get("error_code", 0)
        error_key = f"error:{error}:{state == 'Error'}"
        if fresh and (state == "Error" or error != 0):
            if error_key not in self.sent:
                notices.append(Notice("error", "Washer needs attention", f"The washer reports an error (code {error}). Check its display and door.", True))
                self.sent.add(error_key)
        else:
            self.sent = {key for key in self.sent if not key.startswith("error:")}
        if state in ACTIVE | {"Paused"} and not fresh:
            self.problem = "No recent machine report — the displayed stage and time may be old."
            if "stale" not in self.sent:
                notices.append(Notice("stale", "No recent washer update", f"No machine status for {self.stale_seconds // 60} minutes or more. It may still be running; check the washer. This does not prove it is stuck.", True))
                self.sent.add("stale")
        else:
            self.sent.discard("stale")
        if "stuck" in self.sent and fresh and state in ACTIVE:
            self.problem = "Possible delay: new reports arrive, but the stage and remaining time have not progressed."
        if fresh and newer and state in ACTIVE and now - self.progress_at >= self.stuck_seconds:
            self.problem = "Possible delay: new reports arrive, but the stage and remaining time have not progressed."
            if "stuck" not in self.sent:
                notices.append(Notice("stuck", "Washer may be stuck", f"Fresh reports show no stage or remaining-time change for {self.stuck_seconds // 60} minutes or more. Long stages can be normal; check the machine.", True))
                self.sent.add("stuck")
        if fresh and state == "Paused" and now - self.pause_at >= 300 and "paused" not in self.sent:
            notices.append(Notice("paused", "Washer is still paused", "The washer has reported Paused for at least five minutes.", True))
            self.sent.add("paused")
        self.previous = {k: p.get(k) for k in ("status", "course", "remaining_time", "last_status_at")}
        self.last_sample_at = now
        return notices
