"""Tests for the Electra air conditioner device model."""

import json

from electrasmart.device import ElectraAirConditioner
from electrasmart.device.const import Feature, OperationMode


def _device_record() -> dict:
    return {
        "id": "1234123456",
        "name": "Living Room AC",
        "mac": "aa:bb:cc:dd:ee:ff",
        "manufactor": "Electra",
        "deviceTypeName": "A/C",
        "deviceToken": "some-token",
    }


def _ac(
    oper: dict[str, str],
    diag: dict[str, str] | None = None,
    time_delta: int = 5,
) -> ElectraAirConditioner:
    """An air conditioner holding the given operation state.

    ``update_operation_states`` ignores a payload without both blocks, so the
    diagnostics default to something a real unit would report.
    """
    ac = ElectraAirConditioner(_device_record())
    ac.update_operation_states(
        {
            "commandJson": {
                "OPER": json.dumps({"OPER": oper}),
                "DIAG_L2": json.dumps({"DIAG_L2": diag or {"O_ODU_MODE": "COOL"}}),
            },
            "timeDelta": time_delta,
        }
    )
    return ac


def _running(ac_mode: str = "COOL") -> ElectraAirConditioner:
    return _ac({"AC_MODE": ac_mode, "SPT": "22", "FANSPD": "LOW"})


def test_is_disconnected_only_after_the_threshold() -> None:
    ac = _ac({"AC_MODE": "COOL"}, time_delta=60)

    assert ac.is_disconnected() is False

    ac = _ac({"AC_MODE": "COOL"}, time_delta=61)

    assert ac.is_disconnected() is True


def test_is_disconnected_honours_a_custom_threshold() -> None:
    ac = _ac({"AC_MODE": "COOL"}, time_delta=61)

    assert ac.is_disconnected(thresh_sec=120) is False
    assert ac.is_disconnected(thresh_sec=30) is True


def test_features_report_the_swings_the_unit_supports() -> None:
    ac = _ac({"AC_MODE": "COOL", "VSWING": "OFF", "HSWING": "OFF"})
    ac.update_features()

    assert ac.features == [Feature.V_SWING, Feature.H_SWING]


def test_features_stay_empty_without_swing_fields() -> None:
    ac = _running()
    ac.update_features()

    assert ac.features == []


def test_set_mode_accepts_a_known_mode() -> None:
    ac = _running("COOL")

    ac.set_mode("HEAT")

    assert ac.get_mode() == "HEAT"


def test_set_mode_ignores_an_unknown_mode() -> None:
    ac = _running("COOL")

    ac.set_mode("TURBO")

    assert ac.get_mode() == "COOL"


def test_set_mode_ignores_the_mode_it_is_already_in() -> None:
    ac = _running("COOL")
    oper_before = dict(ac._oper_data)

    ac.set_mode("COOL")

    assert ac._oper_data == oper_before


def test_vertical_swing_can_be_read_and_set() -> None:
    ac = _ac({"AC_MODE": "COOL", "VSWING": "OFF"})

    assert ac.is_vertical_swing() is False

    ac.set_vertical_swing(True)
    assert ac.is_vertical_swing() is True

    ac.set_vertical_swing(False)
    assert ac.is_vertical_swing() is False


def test_horizontal_swing_can_be_read_and_set() -> None:
    ac = _ac({"AC_MODE": "COOL", "HSWING": "OFF"})

    assert ac.is_horizontal_swing() is False

    ac.set_horizontal_swing(True)
    assert ac.is_horizontal_swing() is True

    ac.set_horizontal_swing(False)
    assert ac.is_horizontal_swing() is False


def test_swing_setters_do_nothing_without_the_field() -> None:
    """A unit that does not report a swing must not gain the field."""
    ac = _running()

    ac.set_vertical_swing(True)
    ac.set_horizontal_swing(True)

    assert "VSWING" not in ac._oper_data
    assert "HSWING" not in ac._oper_data
    assert ac.is_vertical_swing() is False
    assert ac.is_horizontal_swing() is False


def test_turn_off_clears_the_power_flag_when_the_unit_has_one() -> None:
    ac = _ac({"AC_MODE": "COOL", "TURN_ON_OFF": "ON"})

    ac.turn_off()

    assert ac.is_on() is False
    assert ac._oper_data["TURN_ON_OFF"] == OperationMode.OFF
    # The mode is stored separately from the power flag on these units.
    assert ac.get_mode() == "COOL"


def test_temperature_can_be_read_and_set() -> None:
    ac = _running()

    assert ac.get_temperature() == 22

    ac.set_temperature(24)
    assert ac.get_temperature() == 24


def test_setting_the_current_temperature_changes_nothing() -> None:
    ac = _running()
    oper_before = dict(ac._oper_data)

    ac.set_temperature(22)

    assert ac._oper_data == oper_before


def test_fan_speed_can_be_read_and_set() -> None:
    ac = _running()

    assert ac.get_fan_speed() == OperationMode.FAN_SPEED_LOW

    for speed in (
        OperationMode.FAN_SPEED_AUTO,
        OperationMode.FAN_SPEED_HIGH,
        OperationMode.FAN_SPEED_MED,
    ):
        ac.set_fan_speed(speed)
        assert ac.get_fan_speed() == speed


def test_set_fan_speed_ignores_an_unknown_speed() -> None:
    ac = _running()

    ac.set_fan_speed("TURBO")

    assert ac.get_fan_speed() == OperationMode.FAN_SPEED_LOW


def test_set_fan_speed_ignores_the_speed_it_is_already_in() -> None:
    ac = _running()
    oper_before = dict(ac._oper_data)

    ac.set_fan_speed(OperationMode.FAN_SPEED_LOW)

    assert ac._oper_data == oper_before


def test_turbo_mode_can_be_read_and_set() -> None:
    ac = _running()

    ac.set_turbo_mode(True)
    assert ac.get_turbo_mode() is True

    ac.set_turbo_mode(False)
    assert ac.get_turbo_mode() is False


def test_shabat_mode_can_be_read_and_set() -> None:
    ac = _running()

    ac.set_shabat_mode(True)
    assert ac.get_shabat_mode() is True

    ac.set_shabat_mode(False)
    assert ac.get_shabat_mode() is False


def test_i_calc_at_is_used_when_i_rat_is_absent() -> None:
    """Units that report only the calculated temperature must still report it."""
    ac = _ac({"AC_MODE": "COOL"}, {"I_CALC_AT": "5632"})

    assert ac.get_sensor_temperature() == 22


def test_get_operation_state_marks_the_source_as_wifi() -> None:
    """The unit reports where the command came from; this library is the app."""
    ac = _running()
    ac._oper_data["AC_STSRC"] = "IR"

    oper = json.loads(ac.get_operation_state())["OPER"]

    assert oper["AC_STSRC"] == "WI-FI"


def test_get_operation_state_leaves_the_source_alone_without_the_field() -> None:
    ac = _running()

    oper = json.loads(ac.get_operation_state())["OPER"]

    assert "AC_STSRC" not in oper
