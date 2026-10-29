from __future__ import annotations

import json
from logging import getLogger
from typing import Any

from .const import MODE_VALUES, Feature, OperationMode

logger = getLogger(__name__)


class ElectraAirConditioner:
    def __init__(self, data: dict[str, str]) -> None:
        self.id: str = data["id"]
        self.mac: str = data["mac"]
        self.name: str = data.get("name", "")
        self.regdate: str = data.get("regdate", "")
        self.model = data.get("model", "")
        self.serial_number: str = data.get("sn", "")
        self.fm_version: str = data.get("fmVersion", "")
        self.hw_version: str = data.get("hwVersion", "")
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
        # The raw ``DIAG_L2`` telemetry block, which carries far more than the
        # three fields this library reads out of it (radio signal, coil
        # temperatures, health flags, bus counters). Callers that want to
        # surface any of it read it from here rather than the library dropping
        # it on the floor.
        self.measurements: dict[str, Any] = {}
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
        if mode in MODE_VALUES and mode != self._oper_data["AC_MODE"]:
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

    def get_last_mode(self) -> str | None:
        """Return the mode the unit was last running in, if the API reports one.

        Units without a ``TURN_ON_OFF`` field encode the power state in
        ``AC_MODE``: turning off writes ``STBY`` over it. The last running mode
        is still reported by the cloud in the ``DIAG_L2`` telemetry
        (``O_ODU_MODE``), which also covers modes set from the Electra app or
        the infrared remote rather than by this library.
        """
        if self.current_mode in MODE_VALUES:
            return self.current_mode
        return None

    def turn_on(self) -> bool:
        """Turn the unit on, keeping the mode it was last running in.

        Returns ``False`` when the previous mode is unknown, so callers can
        apply their own fallback instead of sending a no-op.
        """
        if self.is_on():
            return True
        if "TURN_ON_OFF" in self._oper_data:
            self._oper_data["TURN_ON_OFF"] = OperationMode.ON
            return True
        last_mode = self.get_last_mode()
        if last_mode is None:
            return False
        self._oper_data["AC_MODE"] = last_mode
        return True

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
        """Turn the turbo mode on or off.

        A unit that does not report ``TURBO`` is left alone: writing the field
        anyway would add it to the full ``OPER`` map this library sends back on
        every command.
        """
        self._set_flag("TURBO", enable)

    def get_turbo_mode(self) -> bool | None:
        """Return whether turbo is on, or ``None`` for a unit without it."""
        return self._is_flag_enabled("TURBO")

    def set_shabat_mode(self, enable: bool) -> None:
        """Turn the Shabat mode on or off, leaving a unit without it alone."""
        self._set_flag("SHABAT", enable)

    def get_shabat_mode(self) -> bool | None:
        """Return whether Shabat mode is on, or ``None`` for a unit without it."""
        return self._is_flag_enabled("SHABAT")

    def _is_flag_enabled(self, field: str) -> bool | None:
        """Read an on/off ``OPER`` field, or ``None`` when the unit omits it."""
        value = self._oper_data.get(field)
        if value is None:
            return None

        return value == OperationMode.ON

    def _set_flag(self, field: str, enable: bool) -> None:
        """Write an on/off ``OPER`` field, ignoring a unit without the field."""
        if field in self._oper_data:
            self._oper_data[field] = OperationMode.ON if enable else OperationMode.OFF

    def set_ifeel_mode(self, enable: bool) -> None:
        """Turn iFeel on or off.

        iFeel follows the temperature measured by the remote instead of the
        one the unit measures; the flag rides in the same ``OPER`` map as the
        other modes. A unit that does not report ``IFEEL`` is left alone.
        """
        self._set_flag("IFEEL", enable)

    def get_ifeel_mode(self) -> bool | None:
        """Return whether iFeel is on, or ``None`` for a unit without it."""
        return self._is_flag_enabled("IFEEL")

    def set_sleep_mode(self, enable: bool) -> None:
        """Turn the sleep mode on or off.

        Sleep mode lets the unit ramp the temperature down (or up, when
        heating) while the room is asleep. A unit that does not report
        ``SLEEP`` is left alone.
        """
        self._set_flag("SLEEP", enable)

    def get_sleep_mode(self) -> bool | None:
        """Return whether the sleep mode is on, or ``None`` without the field."""
        return self._is_flag_enabled("SLEEP")

    def set_timer_mode(self, enable: bool) -> None:
        """Turn the unit's timer INDICATION on or off.

        ``OPER.TIMER`` is not the account's timers. It is the app's own "at
        least one timer is armed" note, which the app writes itself: measured
        live, every timer the app enabled or disabled moved this field and
        nothing else, while enabling or disabling the same event - and the
        per-device events flag - over this API left it untouched. Writing it
        directly is accepted and holds, moving no other field; nothing on the
        server keeps it truthful, so it follows the app and goes stale for a
        client that changes timers over the API. The scheduled timers are the
        events, which ``ElectraAPI.get_events`` reads. A unit that does not
        report ``TIMER`` is left alone.
        """
        self._set_flag("TIMER", enable)

    def get_timer_mode(self) -> bool | None:
        """Return the unit's timer indication, or ``None`` without the field.

        This is ``OPER.TIMER``, which the account's timers do not drive over this
        API - see ``set_timer_mode``. It is the app's own note that a timer is
        armed, so read it that way only when the app is what set the timers: a
        client that changes timers here does not move it.
        """
        return self._is_flag_enabled("TIMER")

    def get_filter_clean_required(self) -> bool | None:
        """Return whether the unit is asking for the filter to be cleaned.

        ``CLEAR_FILT`` is the filter-cleaning reminder the Electra app shows.
        ``None`` means the unit does not report the field at all, so a caller
        can leave its entity out instead of reporting a reminder that the unit
        never sent.
        """
        return self._is_flag_enabled("CLEAR_FILT")

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
        self.measurements = json.loads(diag_l2)["DIAG_L2"]
        # ``I_RAT``/``I_CALC_AT`` both report the room temperature; the
        # calculated one wins when the unit sends both.
        for field in ("I_RAT", "I_CALC_AT"):
            temperature = self.get_measurement_temperature(field)
            if temperature is not None:
                self.collected_measure = temperature

        # ``O_ODU_MODE`` reports the mode the unit was last running in, and is
        # still populated while the unit is off, so it is the only way to know
        # what to restore on units without a ``TURN_ON_OFF`` field. Not every
        # unit reports it, so tolerate its absence.
        self.current_mode = self.measurements.get("O_ODU_MODE")

    def get_measurement_temperature(self, field: str) -> int | None:
        """Return a temperature field from the diagnostics, in Celsius.

        Temperature fields in ``DIAG_L2`` are reported as a ×256 left-shifted
        integer (e.g. raw 5632 == 22 °C), while some units already send the
        normalized value, so only shift beyond the 100 °C threshold, in either
        direction: an encoded -1280 is -5 °C. Returns ``None`` for a unit that
        does not report the field, or reports something that is not a number.
        """
        raw = self.measurements.get(field)
        if raw is None:
            return None

        try:
            raw_temp = int(raw)
        except (TypeError, ValueError):
            logger.debug("Ignoring non-numeric %s measurement: %r", field, raw)
            return None

        return raw_temp >> 8 if abs(raw_temp) > 100 else raw_temp

    def get_operation_state(self) -> str:
        if "AC_STSRC" in self._oper_data:
            self._oper_data["AC_STSRC"] = "WI-FI"

        return json.dumps({"OPER": self._oper_data})
