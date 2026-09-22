"""Per-node sample queue (T2.2, decision D2.3).

Default discipline is LCFS with a single buffer slot: a fresh sample
always overwrites whatever is waiting, so a successful delivery resets
AoI to roughly one sampling interval rather than to the age of whatever
happened to reach the front of a FIFO backlog. FIFO with a configurable
capacity is kept as an ablation option (config.scheduler.queue_discipline).

The alarm latch is a separate sticky flag from the queued data: an
overwrite (LCFS discarding a stale sample for a fresh one) must never
silently drop the fact that an alarm was raised. It is cleared only by an
explicit acknowledgement (`clear_alarm`), mirroring the real protocol's
FLAG_ALARM_ACK (common/contracts/packets.py).
"""

from collections import deque

LCFS = "lcfs"
FIFO = "fifo"


class NodeQueue:
    def __init__(self, discipline: str = LCFS, capacity: int = 1):
        if discipline not in (LCFS, FIFO):
            raise ValueError(f"Unknown queue discipline: {discipline}")
        if discipline == LCFS and capacity != 1:
            raise ValueError("LCFS discipline is only defined for capacity 1")

        self.discipline = discipline
        self.capacity = capacity
        self._ages: deque[float] = deque()
        self.alarm_latched = False

    def has_data(self) -> bool:
        return len(self._ages) > 0

    def age_all(self, t_slot: float) -> None:
        """Ages every buffered (undelivered) sample by one slot duration."""
        self._ages = deque(age + t_slot for age in self._ages)

    def push(self, is_alarm: bool = False) -> None:
        """Buffers a freshly generated sample (age 0)."""
        if self.discipline == LCFS:
            self._ages = deque([0.0])
        else:
            if len(self._ages) < self.capacity:
                self._ages.append(0.0)
            # else: tail-drop -- the new arrival is discarded, the
            # existing backlog is untouched (this is exactly what makes
            # FIFO AoI-pessimal under load, per F2.3).

        if is_alarm:
            self.alarm_latched = True

    def pop_for_delivery(self) -> float:
        """Removes and returns the age (seconds) of the delivered sample.

        LCFS has at most one sample, so this is trivially the newest.
        FIFO delivers from the front (oldest first) -- latency-optimal,
        which is precisely why it is AoI-pessimal under backlog.
        """
        if not self._ages:
            raise ValueError("pop_for_delivery() called on an empty queue")
        return self._ages.popleft()

    def clear_alarm(self) -> None:
        self.alarm_latched = False
