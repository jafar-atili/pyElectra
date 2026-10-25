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
    ac = _ac({"AC_MODE": "COOL", "TURBO": "OFF"})

    assert ac.get_turbo_mode() is False

    ac.set_turbo_mode(True)
    assert ac.get_turbo_mode() is True

    ac.set_turbo_mode(False)
    assert ac.get_turbo_mode() is False


def test_shabat_mode_can_be_read_and_set() -> None:
    ac = _ac({"AC_MODE": "COOL", "SHABAT": "OFF"})

    assert ac.get_shabat_mode() is False

    ac.set_shabat_mode(True)
    assert ac.get_shabat_mode() is True

    ac.set_shabat_mode(False)
    assert ac.get_shabat_mode() is False


def test_ifeel_mode_can_be_read_and_set() -> None:
    ac = _ac({"AC_MODE": "COOL", "IFEEL": "OFF"})

    assert ac.get_ifeel_mode() is False

    ac.set_ifeel_mode(True)
    assert ac.get_ifeel_mode() is True

    ac.set_ifeel_mode(False)
    assert ac.get_ifeel_mode() is False


def test_sleep_mode_can_be_read_and_set() -> None:
    ac = _ac({"AC_MODE": "COOL", "SLEEP": "OFF"})

    assert ac.get_sleep_mode() is False

    ac.set_sleep_mode(True)
    assert ac.get_sleep_mode() is True

    ac.set_sleep_mode(False)
    assert ac.get_sleep_mode() is False


def test_timer_mode_can_be_read_and_set() -> None:
    ac = _ac({"AC_MODE": "COOL", "TIMER": "OFF"})

    assert ac.get_timer_mode() is False

    ac.set_timer_mode(True)
    assert ac.get_timer_mode() is True

    ac.set_timer_mode(False)
    assert ac.get_timer_mode() is False


def test_flag_modes_are_none_without_the_field() -> None:
    """A unit that omits a flag says so, instead of reading as switched off."""
    ac = _running()

    assert ac.get_ifeel_mode() is None
    assert ac.get_sleep_mode() is None
    assert ac.get_timer_mode() is None
    assert ac.get_turbo_mode() is None
    assert ac.get_shabat_mode() is None


def test_flag_setters_do_nothing_without_the_field() -> None:
    """Nothing may be added to the OPER map a unit did not report itself."""
    ac = _running()
    oper_before = dict(ac._oper_data)

    ac.set_ifeel_mode(True)
    ac.set_sleep_mode(True)
    ac.set_timer_mode(True)
    ac.set_turbo_mode(True)
    ac.set_shabat_mode(True)

    assert ac._oper_data == oper_before


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


def test_device_record_carries_the_serial_and_the_versions() -> None:
    """The record reports a serial number, firmware and hardware versions."""
    ac = ElectraAirConditioner(
        {
            **_device_record(),
            "sn": "J4B60300391",
            "fmVersion": "611V4-C20",
            "hwVersion": "V1",
        }
    )

    assert ac.serial_number == "J4B60300391"
    assert ac.fm_version == "611V4-C20"
    assert ac.hw_version == "V1"


def test_versions_default_to_empty_when_the_record_omits_them() -> None:
    """Not every device record carries a serial or a version."""
    ac = ElectraAirConditioner(_device_record())

    assert ac.serial_number == ""
    assert ac.fm_version == ""
    assert ac.hw_version == ""


def test_measurements_keep_the_whole_diagnostics_block() -> None:
    """The telemetry is retained, not just the fields this library reads."""
    ac = _ac({"AC_MODE": "COOL"}, {"WI_FI_RSSI": "-53", "I_ICT": "21"})

    assert ac.measurements["WI_FI_RSSI"] == "-53"
    assert ac.measurements["I_ICT"] == "21"


def test_measurements_are_empty_before_the_first_update() -> None:
    ac = ElectraAirConditioner(_device_record())

    assert ac.measurements == {}


def test_measurement_temperature_normalizes_a_raw_value() -> None:
    """Temperature fields are ×256 left-shifted on some units, not others."""
    ac = _ac({"AC_MODE": "COOL"}, {"I_ICT": "5632", "I_RCT": "22"})

    assert ac.get_measurement_temperature("I_ICT") == 22
    assert ac.get_measurement_temperature("I_RCT") == 22


def test_measurement_temperature_normalizes_a_negative_raw_value() -> None:
    """A raw value below zero is encoded too, and must be shifted as well."""
    ac = _ac({"AC_MODE": "COOL"}, {"O_OCT": "-1280", "I_RCT": "-5"})

    assert ac.get_measurement_temperature("O_OCT") == -5
    assert ac.get_measurement_temperature("I_RCT") == -5


def test_measurement_temperature_is_none_without_the_field() -> None:
    """A unit that does not report the field must not raise."""
    ac = _running()

    assert ac.get_measurement_temperature("O_OAT") is None


def test_measurement_temperature_is_none_for_a_non_numeric_value() -> None:
    ac = _ac({"AC_MODE": "COOL"}, {"O_OAT": "N/A"})

    assert ac.get_measurement_temperature("O_OAT") is None


def test_filter_clean_required_follows_the_reminder_flag() -> None:
    assert (
        _ac({"AC_MODE": "COOL", "CLEAR_FILT": "ON"}).get_filter_clean_required() is True
    )
    assert (
        _ac({"AC_MODE": "COOL", "CLEAR_FILT": "OFF"}).get_filter_clean_required()
        is False
    )


def test_filter_clean_required_is_none_without_the_field() -> None:
    """A unit that does not report the reminder says so instead of raising."""
    assert _running().get_filter_clean_required() is None
