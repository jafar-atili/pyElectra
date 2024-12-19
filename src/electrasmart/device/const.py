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
    SWING_BOTH = ""
    SWING_HORIZONTAL = ""
    SWING_VERTICAL = ""
    SWING_OFF = ""


@dataclass
class Feature:
    V_SWING = 0
    H_SWING = 1
