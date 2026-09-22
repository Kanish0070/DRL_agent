"""LCFS-1 queue with a sticky alarm latch (D2.3).

Each node has a single-slot last-come-first-served buffer: a fresh sample
always overwrites whatever is buffered, so the queue never grows past depth
1 (mirrors IoTSensorApp::GenerateSample in ns3-sim/aoi-scheduler-sim.cc).
The alarm latch is a separate bit that, once set by an alarm-class sample,
survives being overwritten by later non-alarm samples -- it is cleared only
by an explicit ack (mirrors packets.py FLAG_ALARM_LATCHED/FLAG_ALARM_ACK),
so a live criticality escalation (E19) can never be silently lost by the
next routine sample landing on top of it.
"""

from dataclasses import dataclass


@dataclass
class LcfsAlarmQueue:
    sample_interval_s: float
    next_sample_due_s: float = 0.0
    occupied: bool = False
    generation_time_s: float = 0.0
    alarm_latched: bool = False

    def advance_to(self, now_s: float, is_alarm: bool = False) -> None:
        """
        Generates any samples due by `now_s`. LCFS-1 semantics mean only the
        most recent matters, so if multiple sample periods elapsed in one
        call, earlier ones are simply overwritten -- there is nothing to lose.
        """
        while self.next_sample_due_s <= now_s:
            self.generation_time_s = self.next_sample_due_s
            self.occupied = True
            if is_alarm:
                self.alarm_latched = True
            self.next_sample_due_s += self.sample_interval_s

    def take(self) -> float | None:
        """Consumes the buffered sample on a successful grant reply, returning
        its generation time. The alarm latch is untouched -- only ack_alarm()
        clears it."""
        if not self.occupied:
            return None
        gen_time = self.generation_time_s
        self.occupied = False
        return gen_time

    def ack_alarm(self) -> None:
        self.alarm_latched = False
