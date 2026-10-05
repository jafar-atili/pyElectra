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
