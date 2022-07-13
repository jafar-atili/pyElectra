from dataclasses import dataclass
from datetime import timedelta

STATUS_SUCCESS = 0
DELAY_BETWEEM_SID_REQUESTS = int(timedelta(minutes=5).total_seconds())
SID_EXPIRATION = int(timedelta(hours=1).total_seconds())


@dataclass
class Attributes:
    INTRUDER_LOCKOUT = "Intruder lockout"
    DESC = "res_desc"
    DATA = "data"
    TOKEN = "token"
    SID = "sid"
    RES = "res"
    STATUS = "status"
    DEVICES = "devices"
