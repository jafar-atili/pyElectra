from dataclasses import dataclass
from datetime import timedelta

STATUS_SUCCESS = 0
DELAY_BETWEEM_SID_REQUESTS = int(timedelta(minutes=5).total_seconds())
SID_EXPIRATION = int(timedelta(minutes=15).total_seconds())

class electra:
    ATTR_STATUS = 'status'
    STATUS_SUCCESS =0
    ATTR_DATA = 'data'
    ATTR_RES = 'res'
    ATTR_TOKEN = 'token'

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
