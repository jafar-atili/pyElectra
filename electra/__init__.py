import aiohttp
import asyncio
import logging
import math

from datetime import timedelta, datetime
from json import JSONDecodeError
import json
import random

from threading import Lock

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

logger = logging.getLogger(__name__)


INTRUDER_LOCKOUT = "Intruder lockout"
ATTR_DESC = "res_desc"
ATTR_DATA = "data"
ATTR_TOKEN = "token"
ATTR_SID = "sid"
ATTR_SID = "sid"
ATTR_RES = "res"
ATTR_STATUS = "status"
ATTR_DEVICES = "devices"
STATUS_SUCCESS = 0


OPER_MODE_COOL = "COOL"
OPER_MODE_HEAT = "HEAT"
OPER_MODE_AUTO = "AUTO"
OPER_MODE_DRY = "DRY"
OPER_MODE_FAN = "FAN"

OPER_FAN_SPEED_LOW = "LOW"
OPER_FAN_SPEED_MED = "MED"
OPER_FAN_SPEED_HIGH = "HIGH"
OPER_FAN_SPEED_AUTO = "AUTO"
OPER_ON = "ON"
OPER_OFF = "OFF"

"""
oper_state = {
	'id': 99,
	'status': 0,
	'desc': None,
	'data': {
		'timeDelta': 15,
		'commandJson': {
			'OPER': '{"OPER":{"TURN_ON_OFF":"OFF","AC_MODE":"COOL","SPT":"24","FANSPD":"AUTO","VSWING":"OFF","SLEEP":"OFF","HSWING":"OFF","CLEAR_FILT":"OFF","IDU_PN":"","IFEEL":"OFF","MSGTYPE":"OPER","OP_VAL_ERR":"OK","SHABAT":"OFF","TIMER":"OFF","TURBO":"OFF"}}',
			'DIAG_L2': '{"DIAG_L2":{"I_RAT":"24","O_ODU_MODE":"COOL","IDU_FAN":"AUTO","IDU_PN":"","MSGTYPE":"DIAG_L2","O_OAT":""}}'
		},
		'res': 0,
		'res_desc': None
	}
}
"""

"""
resp = {
	'id': 99,
	'status': 0,
	'desc': None,
	'data': {
		'devices': [
            {
			'providerName': None,
			'deviceTypeName': 'A/C',
			'manufactor': 'Midea',
			'photoId': None,
			'permissions': 15,
			'deviceTypeId': 1,
			'name': 'סלון',
			'status': 1,
			'providerid': 1,
			'latitude': None,
			'longitude': None,
			'location': None,
			'sn': 'XXXXXX',
			'mac': 'XXXXX',
			'model': 'XXXXX',
			'hwVersion': None,
			'fmVersion': None,
			'userId': 99999,
			'manufactorId': 2,
			'iconId': '1',
			'hasImage': False,
			'deviceToken': 'XXXXX',
			'mqttId': 'XXXXX',
			'enableEvents': True,
			'isActivated': False,
			'logLevel': None,
			'lastIntervalActivity': None,
			'PowerOnID': None,
			'IsDebugMode': False,
			'regdate': '2021-03-31T21:12:39',
			'id': 9999
		    }
        ],
		'res': 0,
		'res_desc': None
	}
}
"""

MAX_TEMP = 30
MIN_TEMP = 17

DELAY_BETWEEM_SID_REQUESTS = int(timedelta(minutes=5).total_seconds())  # 5 minutes
SID_EXPIRATION = int(timedelta(hours=1).total_seconds())  # 1 hour


class ElectraApiError(Exception):
    pass


def generate_imei():
    minimum = int(math.pow(10, 7))
    maximum = int(math.pow(10, 8) - 1)
    return f"2b950000{str(math.floor(random.randint(minimum, maximum)))}"


class ElectraAirConditioner(object):
    def __init__(self, data) -> None:
        self.id = data["id"]
        self.name = data["name"]
        self.regdate = data["regdate"]
        self.model = data["model"]
        self.mac = data["mac"]
        self.serial_number = data["sn"]
        self.manufactor = data["manufactor"]
        self.type = data["deviceTypeName"]
        self.status = data["status"]
        self.token = data["deviceToken"]

        self.current_mode = None
        self.collected_measure = None
        self._oper_data = None

    def get_sensor_temperature(self):
        return self.collected_measure

    def get_mode(self):
        return self._oper_data["AC_MODE"]

    def set_mode(self, mode: str):
        if mode in [
            OPER_MODE_AUTO,
            OPER_MODE_COOL,
            OPER_MODE_DRY,
            OPER_MODE_FAN,
            OPER_MODE_HEAT,
        ]:
            if mode != self._oper_data["AC_MODE"]:
                self._oper_data["AC_MODE"] = mode

    def set_horizontal_swing(self, enable: bool):
        self._oper_data["HSWING"] = OPER_ON if enable else OPER_OFF

    def set_vertical_swing(self, enable: bool):
        self._oper_data["VSWING"] = OPER_ON if enable else OPER_OFF

    def is_vertical_swing(self):
        return self._oper_data["VSWING"] == OPER_ON

    def is_horizontal_swing(self):
        return self._oper_data["HSWING"] == OPER_ON

    def is_on(self):
        return self._oper_data["TURN_ON_OFF"] == OPER_ON

    def turn_on(self):
        if not self.is_on():
            self._oper_data["TURN_ON_OFF"] = OPER_ON

    def turn_off(self):
        if self.is_on():
            self._oper_data["TURN_ON_OFF"] = OPER_OFF

    def get_temperature(self):
        return int(self._oper_data["SPT"])

    def set_temperature(self, val: int):
        if self.get_temperature() != val:
            self._oper_data["SPT"] = str(val)

    def get_fan_speed(self):
        return self._oper_data["FANSPD"]

    def set_fan_speed(self, speed):
        if speed in [
            OPER_FAN_SPEED_AUTO,
            OPER_FAN_SPEED_HIGH,
            OPER_FAN_SPEED_MED,
            OPER_FAN_SPEED_LOW,
        ]:
            if speed != self._oper_data["FANSPD"]:
                self._oper_data["FANSPD"] = speed

    def set_turbo_mode(self, enable: bool):
        self._oper_data["TURBO"] = OPER_ON if enable else OPER_OFF

    def get_turbo_mode(self):
        return self._oper_data["SHABAT"] == OPER_ON

    def set_shabat_mode(self, enable: bool):
        self._oper_data["SHABAT"] = OPER_ON if enable else OPER_OFF

    def get_shabat_mode(self):
        return self._oper_data["SHABAT"] == OPER_ON

    def update_operation_states(self, data):
        self._oper_data = json.loads(data["OPER"])["OPER"]
        measurments = json.loads(data["DIAG_L2"])["DIAG_L2"]
        if "I_RAT" in measurments:
            self.collected_measure = int(measurments["I_RAT"])
        if "I_CALC_AT" in measurments:
            self.collected_measure = int(measurments["I_CALC_AT"])

        self.current_mode = measurments["O_ODU_MODE"]

    def get_operation_state(self):
        if "AC_STSRC" in self._oper_data:
            self._oper_data["AC_STSRC"] = "WI-FI"

        json_state = json.dumps({"OPER": self._oper_data})
        return json_state


class ElectraAPI(object):
    def __init__(self, websession, imei=None, token=None):
        self._base_url = "https://app.ecpiot.co.il/mobile/mobilecommand"
        self._sid = None
        self._imei = imei
        self._token = token
        self._sid_expiration = 0
        self._last_sid_request_ts = 0
        self._session = websession
        self._phone_number = None
        self.lock = Lock()

    async def _send_request(self, payload) -> dict:
        try:
            resp = await self._session.post(
                url=self._base_url,
                json=payload,
                headers={"user-agent": "Electra Client"},
            )
            json_resp = await resp.json(content_type=None)
        except asyncio.TimeoutError as e:
            raise ElectraApiError(
                "Failed to communicate with Electra API due to time out"
            )
        except aiohttp.ClientError as e:
            raise ElectraApiError(
                "Failed to communicate with Electra API due to client error"
            )
        except JSONDecodeError as e:
            raise ElectraApiError("Recieved invalid response from Electra API: %s", e)

        return json_resp

    async def generate_new_token(self, phone_number, imei):

        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "SEND_OTP",
            "data": {"imei": imei, "phone": phone_number},
        }

        return await self._send_request(payload=payload)

    async def validate_one_time_password(self, otp, imei, phone_number):
        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "CHECK_OTP",
            "data": {
                "imei": imei,
                "phone": phone_number,
                "code": otp,
                "os": "android",
                "osver": "M4B30Z",
            },
        }

        return await self._send_request(payload=payload)

    def _sid_expired(self) -> bool:
        current_time = int(datetime.now().timestamp())
        refresh_in = self._sid_expiration - current_time
        if refresh_in > 0:
            logger.debug("Should refresh in %s minutes", round(refresh_in / 60))

        if current_time < self._sid_expiration:
            return False
        else:
            self._sid = None
            return True

    async def _get_sid(self, force=False) -> bool:

        with self.lock:

            current_ts = int(datetime.now().timestamp())
            if not force and not self._sid_expired():
                logger.debug("Found valid sid (%s) in cache, using it", self._sid)
                return

            if self._last_sid_request_ts and current_ts < (
                self._last_sid_request_ts + DELAY_BETWEEM_SID_REQUESTS
            ):
                logger.debug(
                    'Session ID was requested less than 5 minutes ago! waiting in order to prevent "intruder lockdown"...'
                )

            payload = {
                "pvdid": 1,
                "id": 99,
                "cmd": "VALIDATE_TOKEN",
                "data": {
                    "imei": self._imei,
                    "token": self._token,
                    "os": "android",
                    "osver": "M4B30Z",
                },
            }

            resp = await self._send_request(payload=payload)
            if resp is None:
                raise ElectraApiError("Failed to retrieve sid")
            else:
                if not resp[ATTR_DATA][ATTR_SID]:
                    raise ElectraApiError(
                        "Failed to retrieve SID due to %s", resp[ATTR_DATA][ATTR_DESC]
                    )

                else:
                    self._sid = resp[ATTR_DATA][ATTR_SID]
                    self._sid_expiration = current_ts + SID_EXPIRATION
                    self._last_sid_request_ts = current_ts
                    logger.debug("Successfully acquired sid: %s", self._sid)

    async def get_devices(self) -> list:
        if self._sid_expired():
            await self._get_sid()

        payload = {"pvdid": 1, "id": 99, "cmd": "GET_DEVICES", "sid": self._sid}

        ac_list = []
        resp = await self._send_request(payload=payload)
        if resp[ATTR_STATUS] == STATUS_SUCCESS:
            for ac in resp[ATTR_DATA][ATTR_DEVICES]:
                if ac["deviceTypeName"] == "A/C":
                    ac_list.append(ElectraAirConditioner(ac))

            return ac_list

        else:
            raise ElectraApiError("Failed to fetch devices %s", resp)

    async def get_last_telemtry(self, ac: ElectraAirConditioner):

        if self._sid_expired():
            await self._get_sid()

        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "GET_LAST_TELEMETRY",
            "sid": self._sid,
            "data": {"id": ac.id, "commandName": "OPER,DIAG_L2"},
        }

        resp = await self._send_request(payload=payload)
        if resp[ATTR_STATUS] != STATUS_SUCCESS:
            raise ElectraApiError(f"Failed to get AC operation state: {resp}")
        else:
            ac.update_operation_states(resp[ATTR_DATA]["commandJson"])

    async def set_state(self, device: ElectraAirConditioner):
        json_command = device.get_operation_state()
        if self._sid_expired():
            await self._get_sid()

        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "SEND_COMMAND",
            "sid": self._sid,
            "data": {"id": device.id, "commandJson": json_command},
        }

        return await self._send_request(payload=payload)
