"""Tests for the server-side timer model."""

import pytest

from electrasmart.event import (
    ALL_WEEKDAYS,
    WEEKDAYS,
    ElectraEvent,
    mask_to_weekdays,
    validate_time,
    weekdays_to_mask,
)

# Sunday and Friday off, as the cloud stored it after two known weekdays were
# cleared: 94 == 0b1011110, so bit 0 is Sunday through bit 6 is Saturday.
WEEKDAYS_WITHOUT_SUNDAY_AND_FRIDAY = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "saturday",
)


def test_the_weekday_mask_round_trips_through_the_names() -> None:
    assert weekdays_to_mask(WEEKDAYS) == ALL_WEEKDAYS == 127
    assert mask_to_weekdays(ALL_WEEKDAYS) == WEEKDAYS


def test_bit_zero_is_sunday() -> None:
    """The cloud answered 94 when Sunday and Friday were cleared."""
    mask = weekdays_to_mask(WEEKDAYS_WITHOUT_SUNDAY_AND_FRIDAY)

    assert mask == 94
    assert mask_to_weekdays(mask) == WEEKDAYS_WITHOUT_SUNDAY_AND_FRIDAY
    assert mask_to_weekdays(0) == ()


def test_weekday_names_are_case_insensitive() -> None:
    assert weekdays_to_mask(["Sunday", "SUNDAY", " sunday "]) == 1


def test_a_time_must_be_a_local_hh_mm() -> None:
    validate_time("00:00")
    validate_time("23:59")

    for rejected in ("24:00", "23:60", "7:00", "2359", "", "17:5", None, 1758):
        with pytest.raises(ValueError, match="HH:MM"):
            validate_time(rejected)  # type: ignore[arg-type]


def test_an_event_reads_the_cloud_shape() -> None:
    event = ElectraEvent.from_api(
        {
            "eventId": "0ebb4e8669f24fbc8041bbc2e4068b71",
            "time": "17:58",
            "days": 94,
            "enabled": False,
            "actionsJson": {"TURN_ON_OFF": "ON", "AC_MODE": "COOL", "SPT": "21"},
        }
    )

    assert event.event_id == "0ebb4e8669f24fbc8041bbc2e4068b71"
    assert event.time == "17:58"
    assert event.enabled is False
    assert event.actions == {"TURN_ON_OFF": "ON", "AC_MODE": "COOL", "SPT": "21"}
    assert event.weekdays == WEEKDAYS_WITHOUT_SUNDAY_AND_FRIDAY
    assert event.fires_on("monday") is True
    assert event.fires_on("SUNDAY") is False


def test_an_event_parses_an_action_map_sent_as_a_string() -> None:
    """The cloud stringifies the map into ``eventData``; some answers carry it."""
    event = ElectraEvent.from_api({"actionsJson": '{"TURBO": "ON"}'})

    assert event.actions == {"TURBO": "ON"}


def test_an_event_defaults_everything_a_sparse_record_omits() -> None:
    event = ElectraEvent.from_api({})

    assert event.event_id == ""
    assert event.time == ""
    assert event.days == 0
    assert event.enabled is False
    assert event.actions == {}


def test_to_api_carries_the_id_only_when_asked() -> None:
    event = ElectraEvent("an-id", "06:15", 3, True, {"SPT": "22"})
    body = {"time": "06:15", "days": 3, "enabled": True, "actionsJson": {"SPT": "22"}}

    assert event.to_api() == {**body, "eventId": "an-id"}
    assert event.to_api(include_id=False) == body
