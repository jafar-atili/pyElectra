from asyncio import create_task, TimeoutError
from datetime import datetime
from json import JSONDecodeError
from logging import getLogger
from typing import List

from aiohttp import ClientError, ClientSession

from electrasmart.device import ElectraAirConditioner

from .const import (
    DELAY_BETWEEM_SID_REQUESTS,
    SID_EXPIRATION,
    STATUS_SUCCESS,
    Attributes,
)

logger = getLogger(__name__)


class ElectraApiError(Exception):
    pass


class ElectraAPI(object):
    def __init__(self, websession: ClientSession, imei: str = None, token: str = None):
        self._base_url = "https://app.ecpiot.co.il/mobile/mobilecommand"
        self._sid = None
        self._imei = imei
        self._token = token
        self._sid_expiration = 0
        self._last_sid_request_ts = 0
        self._session = websession
        self._phone_number = None

        logger.debug("Initialized Electra API object")

    async def _send_request(self, payload: dict) -> dict:
        try:
            resp = await self._session.post(
                url=self._base_url,
                json=payload,
                headers={"user-agent": "Electra Client"},
            )
            json_resp = await resp.json(content_type=None)
        except TimeoutError as ex:
            raise ElectraApiError(
                f"Failed to communicate with Electra API due to time out: ({str(ex)})"
            )
        except ClientError as ex:
            raise ElectraApiError(
                f"Failed to communicate with Electra API due to ClientError: ({str(ex)})"
            )
        except JSONDecodeError as ex:
            raise ElectraApiError(
                f"Recieved invalid response from Electra API: {str(ex)}"
            )

        return json_resp

    async def generate_new_token(self, phone_number: str, imei: str):
        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "SEND_OTP",
            "data": {"imei": imei, "phone": phone_number},
        }

        return await self._send_request(payload=payload)

    async def validate_one_time_password(self, otp: str, imei: str, phone_number: str):
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

    async def _get_sid(self, force: bool = False) -> None:

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
            return

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
            if not resp[Attributes.DATA][Attributes.SID]:
                raise ElectraApiError(
                    "Failed to retrieve SID due to %s",
                    resp[Attributes.DATA][Attributes.DESC],
                )

            else:
                self._sid = resp[Attributes.DATA][Attributes.SID]
                self._sid_expiration = current_ts + SID_EXPIRATION
                self._last_sid_request_ts = current_ts
                logger.debug("Successfully acquired sid: %s", self._sid)

    async def get_devices(self=False) -> list:
        fetch_state_tasks = []
        logger.debug("About to Get Electra AC devices")
        await self._get_sid()

        payload = {"pvdid": 1, "id": 99, "cmd": "GET_DEVICES", "sid": self._sid}

        ac_list: List[ElectraAirConditioner] = []
        resp = await self._send_request(payload=payload)
        if resp[Attributes.STATUS] == STATUS_SUCCESS:
            for ac in resp[Attributes.DATA][Attributes.DEVICES]:
                if ac["deviceTypeName"] == "A/C":
                    electra_ac: ElectraAirConditioner = ElectraAirConditioner(ac)
                    logger.debug("Discovered A/C device %s", electra_ac.name)
                    ac_list.append(electra_ac)
                    fetch_state_tasks.append(
                        create_task(self.get_last_telemtry(electra_ac))
                    )
                else:
                    logger.debug("Discovered non AC device %s", ac)

            for task in fetch_state_tasks:
                await task

            for ac in ac_list:
                ac.update_features()

            return ac_list

        else:
            raise ElectraApiError("Failed to fetch devices %s", resp)

    async def get_last_telemtry(self, ac: ElectraAirConditioner):

        logger.debug("Getting AC %s state", ac.name)

        await self._get_sid()

        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "GET_LAST_TELEMETRY",
            "sid": self._sid,
            "data": {"id": ac.id, "commandName": "OPER,DIAG_L2"},
        }

        resp = await self._send_request(payload=payload)
        if resp[Attributes.STATUS] != STATUS_SUCCESS:
            raise ElectraApiError(f"Failed to get AC operation state: {resp}")
        else:
            ac.update_operation_states(resp[Attributes.DATA])

    async def set_state(self, device: ElectraAirConditioner):
        json_command = device.get_operation_state()
        await self._get_sid()

        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "SEND_COMMAND",
            "sid": self._sid,
            "data": {"id": device.id, "commandJson": json_command},
        }

        return await self._send_request(payload=payload)
