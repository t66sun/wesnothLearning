"""Pause a student's remaining CALL budget for one separately bounded query."""
import math


class QueryClock:
    def __init__(self):
        self.remaining = None

    def begin(self, deadline, now, budget):
        if self.remaining is not None or not math.isfinite(budget) or budget <= 0:
            raise ValueError('invalid nested teacher query budget')
        self.remaining = max(0, deadline-now)
        return now+budget if self.remaining else deadline

    def end(self, deadline, now):
        if self.remaining is None:
            raise ValueError('teacher query returned without starting')
        remaining, self.remaining = self.remaining, None
        # A late RETURN must not erase an already expired hard deadline.
        return now+remaining if now <= deadline else deadline
