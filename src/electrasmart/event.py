"""The server-side timers, which this API models as events.

A timer is not an ``OPER`` field: ``OPER.TIMER`` is the app's own note that one
is armed, and only the app writes it - the same change made over this API leaves
it untouched.
The schedule itself lives in the account's events, each of which is a partial
``OPER`` map applied at a local ``HH:MM`` time on the weekdays its mask selects.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

#: ``days`` is a 7-bit weekday mask and this tuple is the bit order: index 0 is
#: bit 0. Bit 0 = Sunday through bit 6 = Saturday, verified against the cloud by
#: clearing exactly two known weekdays and reading the mask back.
WEEKDAYS: tuple[str, ...] = (
    "sunday",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
)

#: Every weekday selected: 127.
ALL_WEEKDAYS: int = (1 << len(WEEKDAYS)) - 1

TIME_PATTERN = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


def validate_time(value: str) -> None:
    """Raise ``ValueError`` unless ``value`` is a local ``HH:MM`` time."""
    if not isinstance(value, str) or not TIME_PATTERN.match(value):
        raise ValueError(f"{value!r} is not a local HH:MM time")


def weekdays_to_mask(weekdays: Iterable[str]) -> int:
    """Return the mask that selects the given weekday names (any case)."""
    mask = 0
    for weekday in weekdays:
        mask |= 1 << WEEKDAYS.index(str(weekday).strip().lower())
    return mask


def mask_to_weekdays(mask: int) -> tuple[str, ...]:
    """Return the weekday names a mask selects, earliest first."""
    return tuple(day for index, day in enumerate(WEEKDAYS) if mask >> index & 1)


@dataclass
class ElectraEvent:
    """One timer as the cloud stores it.

    ``actions`` is a PARTIAL ``OPER`` map - the fields the timer applies when it
    fires, e.g. ``{"TURN_ON_OFF": "ON", "AC_MODE": "COOL", "SPT": "21"}``. The
    cloud generates the ``eventData`` field of its own answer from it, and
    generates ``event_id`` when a new event is created.
    """

    event_id: str
    time: str
    days: int
    enabled: bool
    actions: dict[str, str]

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> ElectraEvent:
        actions = data.get("actionsJson") or {}
        if isinstance(actions, str):
            actions = json.loads(actions)
        return cls(
            event_id=data.get("eventId") or "",
            time=data.get("time") or "",
            days=int(data.get("days") or 0),
            enabled=bool(data.get("enabled")),
            actions=dict(actions),
        )

    def to_api(self, include_id: bool = True) -> dict[str, Any]:
        """Return the payload shape ``SET_EVENT`` expects.

        The id is omitted when creating an event: the cloud generates one, and
        sending one of our own is rejected.
        """
        payload: dict[str, Any] = {
            "time": self.time,
            "days": self.days,
            "enabled": self.enabled,
            "actionsJson": dict(self.actions),
        }
        if include_id:
            payload["eventId"] = self.event_id
        return payload

    @property
    def weekdays(self) -> tuple[str, ...]:
        """The weekdays this timer fires on."""
        return mask_to_weekdays(self.days)

    def fires_on(self, weekday: str) -> bool:
        """Return whether this timer fires on the given weekday."""
        return bool(self.days & weekdays_to_mask([weekday]))
