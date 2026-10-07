"""Regression tests for the fixes on top of pyElectra 1.2.4."""

import json

from electrasmart.device import ElectraAirConditioner


def _device_record() -> dict:
    return {
        "id": "1234123456",
        "name": "Living Room AC",
        "regdate": "2023-01-01 00:00:00",
        "model": "HTPC-12",
        "mac": "aa:bb:cc:dd:ee:ff",
        "sn": "SN123",
        "manufactor": "Electra",
        "deviceTypeName": "A/C",
        "status": "1",
        "deviceToken": "some-token",
    }


def _telemetry(raw_temp: int) -> dict:
    return {
        "commandJson": {
            "OPER": json.dumps({"OPER": {"TURN_ON_OFF": "ON", "SPT": "22"}}),
            "DIAG_L2": json.dumps(
                {"DIAG_L2": {"I_RAT": str(raw_temp), "O_ODU_MODE": "COOL"}}
            ),
        },
        "timeDelta": 5,
    }


def test_device_without_device_token_does_not_crash() -> None:
    """The deviceToken field is optional on some units."""
    record = _device_record()
    del record["deviceToken"]

    ac = ElectraAirConditioner(record)

    assert ac.token == ""


def test_device_with_device_token() -> None:
    ac = ElectraAirConditioner(_device_record())
    assert ac.token == "some-token"


def test_raw_x256_temperature_is_normalized() -> None:
    """Raw 5632 == 22 °C; the ×256 left-shift must be undone."""
    ac = ElectraAirConditioner(_device_record())
    ac.update_operation_states(_telemetry(5632))
    assert ac.get_sensor_temperature() == 22


def test_already_normalized_temperature_is_left_alone() -> None:
    """Some units report the value already normalized; don't shift it again."""
    ac = ElectraAirConditioner(_device_record())
    ac.update_operation_states(_telemetry(22))
    assert ac.get_sensor_temperature() == 22


def test_missing_telemetry_leaves_no_temperature() -> None:
    ac = ElectraAirConditioner(_device_record())
    assert ac.get_sensor_temperature() is None


def test_incomplete_telemetry_is_skipped() -> None:
    """Devices that answer with an empty commandJson must not raise."""
    ac = ElectraAirConditioner(_device_record())

    for payload in (
        {},
        {"commandJson": None, "timeDelta": 5},
        {"commandJson": {"OPER": None, "DIAG_L2": None}, "timeDelta": 5},
        {"commandJson": {"OPER": "", "DIAG_L2": ""}, "timeDelta": 5},
    ):
        ac.update_operation_states(payload)

    assert ac.get_sensor_temperature() is None
    assert ac._oper_data == {}


def _telemetry_for(
    oper: dict[str, str], diag: dict[str, str], time_delta: int = 5
) -> dict:
    return {
        "commandJson": {
            "OPER": json.dumps({"OPER": oper}),
            "DIAG_L2": json.dumps({"DIAG_L2": diag}),
        },
        "timeDelta": time_delta,
    }


def _legacy_telemetry(ac_mode: str, odu_mode: str) -> dict:
    """Telemetry for a unit with no ``TURN_ON_OFF`` field.

    On these units ``AC_MODE`` carries the power state and ``O_ODU_MODE`` keeps
    reporting the mode the unit was last running in, even while it is off.
    """
    return _telemetry_for({"AC_MODE": ac_mode, "SPT": "22"}, {"O_ODU_MODE": odu_mode})


def _legacy_off_telemetry(odu_mode: str = "COOL") -> dict:
    return _legacy_telemetry("STBY", odu_mode)


def test_legacy_unit_turn_on_restores_the_last_mode() -> None:
    """Turning a legacy unit on must not fall back to a hard-coded mode."""
    ac = ElectraAirConditioner(_device_record())
    ac.update_operation_states(_legacy_off_telemetry())
    assert not ac.is_on()

    assert ac.turn_on() is True

    assert ac.is_on()
    assert ac.get_mode() == "COOL"
    assert json.loads(ac.get_operation_state())["OPER"]["AC_MODE"] == "COOL"


def test_legacy_turn_on_restores_a_mode_set_outside_this_library() -> None:
    """A mode last set from the Electra app must be visible to turn_on()."""
    ac = ElectraAirConditioner(_device_record())
    ac.update_operation_states(_legacy_off_telemetry(odu_mode="HEAT"))

    assert ac.get_last_mode() == "HEAT"
    assert ac.turn_on() is True
    assert ac.get_mode() == "HEAT"


def test_legacy_turn_off_writes_stby_but_keeps_the_mode_recoverable() -> None:
    ac = ElectraAirConditioner(_device_record())
    ac.update_operation_states(_legacy_telemetry("COOL", "COOL"))

    ac.turn_off()
    assert not ac.is_on()
    assert ac.get_mode() == "STBY"

    # The next poll reports STBY as AC_MODE, with O_ODU_MODE still COOL.
    ac.update_operation_states(_legacy_off_telemetry())
    assert ac.get_last_mode() == "COOL"


def test_legacy_turn_on_without_a_known_mode_reports_failure() -> None:
    """No usable previous mode -> callers must be able to fall back."""
    for odu_mode in ("IDLE", "OFF", "0", ""):
        ac = ElectraAirConditioner(_device_record())
        ac.update_operation_states(_legacy_off_telemetry(odu_mode=odu_mode))

        assert ac.get_last_mode() is None
        assert ac.turn_on() is False
        assert not ac.is_on()
        assert ac.get_mode() == "STBY"


def test_turn_on_off_unit_keeps_ac_mode_untouched() -> None:
    """Units with TURN_ON_OFF store the mode separately from the power flag."""
    ac = ElectraAirConditioner(_device_record())
    ac.update_operation_states(
        _telemetry_for(
            {"AC_MODE": "COOL", "TURN_ON_OFF": "OFF"}, {"O_ODU_MODE": "COOL"}
        )
    )
    assert not ac.is_on()

    assert ac.turn_on() is True

    assert ac.is_on()
    assert ac.get_mode() == "COOL"


def test_turn_on_is_a_noop_when_already_on() -> None:
    ac = ElectraAirConditioner(_device_record())
    ac.update_operation_states(_legacy_telemetry("COOL", "COOL"))
    oper_before = dict(ac._oper_data)

    assert ac.turn_on() is True
    assert ac._oper_data == oper_before


def test_turn_off_is_a_noop_when_already_off() -> None:
    ac = ElectraAirConditioner(_device_record())
    ac.update_operation_states(_legacy_off_telemetry())
    oper_before = dict(ac._oper_data)

    ac.turn_off()
    assert ac._oper_data == oper_before


def test_missing_odu_mode_does_not_break_the_update() -> None:
    """Not every unit reports O_ODU_MODE; that must not raise."""
    ac = ElectraAirConditioner(_device_record())
    ac.update_operation_states(_telemetry_for({"AC_MODE": "STBY"}, {}))

    assert ac.current_mode is None
    assert ac.get_last_mode() is None
    assert ac.turn_on() is False
