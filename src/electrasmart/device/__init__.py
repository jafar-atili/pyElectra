from __future__ import annotations

import json
from logging import getLogger
from typing import Any

from .const import Feature, OperationMode

logger = getLogger(__name__)


class ElectraAirConditioner:
    def __init__(self, data: dict[str, str]) -> None:
        self.id: str = data["id"]
        self.mac: str = data["mac"]
        self.name: str = data.get("name", "")
        self.regdate: str = data.get("regdate", "")
        self.model = data.get("model", "")
        self.serial_number: str = data.get("sn", "")
        self.manufactor: str = data.get("manufactor", "")
        self.type: str = data.get("deviceTypeName", "")
        self.status: str = data.get("status", "")
        # ``deviceToken`` is not always present in the device record (some units
        # omit it), so tolerate a missing field instead of crashing on lookup.
        self.token: str = data.get("deviceToken", "")
        self._time_delta: int = 0
        self.features: list[int] = []

        self.current_mode: str | None = None
        self.collected_measure: int | None = None
        self._oper_data: dict[str, str] = {}

    def is_disconnected(self, thresh_sec: int = 60) -> bool:
        return self._time_delta > thresh_sec

    def update_features(self) -> None:
        if "VSWING" in self._oper_data:
            self.features.append(Feature.V_SWING)
        if "HSWING" in self._oper_data:
            self.features.append(Feature.H_SWING)

    def get_sensor_temperature(self) -> int | None:
        return self.collected_measure

    def get_mode(self) -> str:
        return self._oper_data["AC_MODE"]

    def set_mode(self, mode: str) -> None:
        if (
            mode
            in [
                OperationMode.MODE_AUTO,
                OperationMode.MODE_COOL,
                OperationMode.MODE_DRY,
                OperationMode.MODE_FAN,
                OperationMode.MODE_HEAT,
            ]
            and mode != self._oper_data["AC_MODE"]
        ):
            self._oper_data["AC_MODE"] = mode

    def set_horizontal_swing(self, enable: bool) -> None:
        if "HSWING" in self._oper_data:
            self._oper_data["HSWING"] = (
                OperationMode.ON if enable else OperationMode.OFF
            )

    def set_vertical_swing(self, enable: bool) -> None:
        if "VSWING" in self._oper_data:
            self._oper_data["VSWING"] = (
                OperationMode.ON if enable else OperationMode.OFF
            )

    def is_vertical_swing(self) -> bool:
        if "VSWING" in self._oper_data:
            return self._oper_data["VSWING"] == OperationMode.ON
        return False

    def is_horizontal_swing(self) -> bool:
        if "HSWING" in self._oper_data:
            return self._oper_data["HSWING"] == OperationMode.ON
        return False

    def is_on(self) -> bool:
        if "TURN_ON_OFF" in self._oper_data:
            return self._oper_data["TURN_ON_OFF"] == OperationMode.ON
        else:
            return self._oper_data["AC_MODE"] != OperationMode.STANDBY

    def turn_on(self) -> None:
        if not self.is_on() and "TURN_ON_OFF" in self._oper_data:
            self._oper_data["TURN_ON_OFF"] = OperationMode.ON

    def turn_off(self) -> None:
        if self.is_on():
            if "TURN_ON_OFF" in self._oper_data:
                self._oper_data["TURN_ON_OFF"] = OperationMode.OFF
            else:
                self._oper_data["AC_MODE"] = OperationMode.STANDBY

    def get_temperature(self) -> int:
        return int(self._oper_data["SPT"])

    def set_temperature(self, val: int) -> None:
        if self.get_temperature() != val:
            self._oper_data["SPT"] = str(val)

    def get_fan_speed(self) -> str:
        return self._oper_data["FANSPD"]

    def set_fan_speed(self, speed: str) -> None:
        if (
            speed
            in [
                OperationMode.FAN_SPEED_AUTO,
                OperationMode.FAN_SPEED_HIGH,
                OperationMode.FAN_SPEED_MED,
                OperationMode.FAN_SPEED_LOW,
            ]
            and speed != self._oper_data["FANSPD"]
        ):
            self._oper_data["FANSPD"] = speed

    def set_turbo_mode(self, enable: bool) -> None:
        self._oper_data["TURBO"] = OperationMode.ON if enable else OperationMode.OFF

    def get_turbo_mode(self) -> bool:
        return self._oper_data["TURBO"] == OperationMode.ON

    def set_shabat_mode(self, enable: bool) -> None:
        self._oper_data["SHABAT"] = OperationMode.ON if enable else OperationMode.OFF

    def get_shabat_mode(self) -> bool:
        return self._oper_data["SHABAT"] == OperationMode.ON

    def update_operation_states(self, data: dict[str, Any]) -> None:
        command_json = (data or {}).get("commandJson") or {}
        oper = command_json.get("OPER")
        diag_l2 = command_json.get("DIAG_L2")
        if not oper or not diag_l2:
            logger.debug(
                "Skipping state update for %s: incomplete telemetry payload", self.name
            )
            return

        self._oper_data = json.loads(oper)["OPER"]
        self._time_delta = data["timeDelta"]
        measurments = json.loads(diag_l2)["DIAG_L2"]
        # ``I_RAT``/``I_CALC_AT`` are reported as a ×256 left-shifted integer
        # (e.g. raw 5632 == 22 °C). Normalize back to Celsius when the raw value
        # is implausible for a room temperature; some units already return the
        # normalized value, so only shift above the 100 °C threshold.
        if "I_RAT" in measurments:
            raw_temp = int(measurments["I_RAT"])
            self.collected_measure = raw_temp >> 8 if raw_temp > 100 else raw_temp
        if "I_CALC_AT" in measurments:
            raw_temp = int(measurments["I_CALC_AT"])
            self.collected_measure = raw_temp >> 8 if raw_temp > 100 else raw_temp

        self.current_mode = measurments["O_ODU_MODE"]

    def get_operation_state(self) -> str:
        if "AC_STSRC" in self._oper_data:
            self._oper_data["AC_STSRC"] = "WI-FI"

        return json.dumps({"OPER": self._oper_data})
