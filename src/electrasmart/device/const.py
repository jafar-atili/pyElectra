from dataclasses import dataclass

MAX_TEMP = 30
MIN_TEMP = 17


@dataclass
class OperationMode:
    MODE_COOL = "COOL"
    MODE_HEAT = "HEAT"
    MODE_AUTO = "AUTO"
    MODE_DRY = "DRY"
    MODE_FAN = "FAN"
    FAN_SPEED_LOW = "LOW"
    FAN_SPEED_MED = "MED"
    FAN_SPEED_HIGH = "HIGH"
    FAN_SPEED_AUTO = "AUTO"
    ON = "ON"
    OFF = "OFF"
    STANDBY = "STBY"


# The values ``AC_MODE`` holds while the unit is running. ``STANDBY`` is
# deliberately absent: it is the "off" value, not a mode.
MODE_VALUES = (
    OperationMode.MODE_AUTO,
    OperationMode.MODE_COOL,
    OperationMode.MODE_DRY,
    OperationMode.MODE_FAN,
    OperationMode.MODE_HEAT,
)


@dataclass
class Feature:
    V_SWING = 0
    H_SWING = 1


# The ``DIAG_L2`` fields that carry a sensor-health sentinel, with the value a
# healthy unit reports for each. The sentinel is NOT identical across models:
# ``NORM`` on one unit, ``NORMAL`` for ``O_RLT_BAD`` / ``O_RGT_BAD`` on another,
# ``0`` for ``O_PROT_STAT`` / ``O_PROT_RESON`` on a third. So only the flags
# whose healthy value has actually been observed are listed - a flag absent from
# this map has no decoding that would not be a guess about the hardware.
INDOOR_COIL_SENSOR_FLAG = "I_BAD_ICT"
RETURN_AIR_SENSOR_FLAG = "I_BAD_RAT"
MEASUREMENT_HEALTHY_VALUES: dict[str, str] = {
    INDOOR_COIL_SENSOR_FLAG: "NORM",
    RETURN_AIR_SENSOR_FLAG: "NORM",
}
