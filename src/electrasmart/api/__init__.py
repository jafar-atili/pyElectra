from __future__ import annotations

import builtins
from asyncio import TaskGroup
from datetime import UTC, datetime
from json import JSONDecodeError
from logging import getLogger
from typing import Any

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


class ElectraIntruderLockoutError(ElectraApiError):
    """The account is locked out by the vendor.

    The cloud refuses to hand out a session ID until the account signs in
    again, which only the one-time-password flow does. Retrying cannot clear
    it, so callers should surface this as an authentication problem instead.
    """


class ElectraAPI:
    def __init__(
        self,
        websession: ClientSession,
        imei: str | None = None,
        token: str | None = None,
    ) -> None:
        self._base_url = "https://app.ecpiot.co.il/mobile/mobilecommand"
        self._sid = None
        self._imei = imei
        self._token = token
        self._sid_expiration = 0
        self._last_sid_request_ts = 0
        self._session = websession
        self._phone_number = None
        self._devices: list[ElectraAirConditioner] = []

        logger.debug("Initialized Electra API object")

    @property
    def devices(self) -> list[ElectraAirConditioner]:
        return self._devices

    async def _send_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = await self._session.post(
                url=self._base_url,
                json=payload,
                headers={"user-agent": "Electra Client"},
            )
            json_resp: dict[str, Any] = await resp.json(content_type=None)
        except builtins.TimeoutError as ex:
            raise ElectraApiError(
                f"Failed to communicate with Electra API due to time out: ({ex!s})"
            )
        except ClientError as ex:
            raise ElectraApiError(
                f"Failed to communicate with Electra API due to ClientError: ({ex!s})"
            )
        except JSONDecodeError as ex:
            raise ElectraApiError(f"Received invalid response from Electra API: {ex!s}")

        return json_resp

    async def generate_new_token(self, phone_number: str, imei: str) -> dict[str, Any]:
        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "SEND_OTP",
            "data": {"imei": imei, "phone": phone_number},
        }

        return await self._send_request(payload=payload)

    async def validate_one_time_password(
        self, otp: str, imei: str, phone_number: str
    ) -> dict[str, Any]:
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
        current_time = int(datetime.now(tz=UTC).timestamp())
        refresh_in = self._sid_expiration - current_time
        if refresh_in > 0:
            logger.debug("Should refresh in %s minutes", round(refresh_in / 60))

        if current_time < self._sid_expiration:
            return False
        else:
            self._sid = None
            return True

    async def _get_sid(self, force: bool = False) -> None:
        current_ts = int(datetime.now(tz=UTC).timestamp())
        if not force and not self._sid_expired():
            logger.debug("Found valid sid in cache, using it")
            return

        if self._last_sid_request_ts and current_ts < (
            self._last_sid_request_ts + DELAY_BETWEEM_SID_REQUESTS
        ):
            logger.debug(
                "Session ID was requested less than %s minutes ago! waiting in "
                'order to prevent "intruder lockdown"...',
                DELAY_BETWEEM_SID_REQUESTS // 60,
            )
            raise ElectraApiError(
                "Failed to retrieve SID: a session ID was requested less than "
                f"{DELAY_BETWEEM_SID_REQUESTS // 60} minutes ago, waiting in order "
                'to prevent an "intruder lockdown"'
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

        # Recorded before the request: a rejected attempt counts against the
        # account's lockout just like an accepted one.
        self._last_sid_request_ts = current_ts

        resp = await self._send_request(payload=payload)

        if resp is None:
            raise ElectraApiError("Failed to retrieve sid")

        data = resp.get(Attributes.DATA) or {}
        if not data.get(Attributes.SID):
            description = data.get(Attributes.DESC)
            if description == Attributes.INTRUDER_LOCKOUT:
                raise ElectraIntruderLockoutError(
                    "Failed to retrieve SID due to Intruder lockout"
                )

            raise ElectraApiError(f"Failed to retrieve SID due to {description}")

        self._sid = data[Attributes.SID]
        self._sid_expiration = current_ts + SID_EXPIRATION
        logger.debug("Successfully acquired session id")

    async def fetch_devices(self) -> None:
        logger.debug("About to Get Electra AC devices")
        await self._get_sid()

        payload = {"pvdid": 1, "id": 99, "cmd": "GET_DEVICES", "sid": self._sid}

        ac_list: list[ElectraAirConditioner] = []
        resp = await self._send_request(payload=payload)
        if resp[Attributes.STATUS] == STATUS_SUCCESS:
            devices = (resp.get(Attributes.DATA) or {}).get(Attributes.DEVICES)
            if devices is None:
                raise ElectraApiError(
                    "Failed to fetch devices: the Electra API returned no device list"
                )

            for ac in devices:
                if ac["deviceTypeName"] == "A/C":
                    electra_ac: ElectraAirConditioner = ElectraAirConditioner(ac)
                    logger.debug("Discovered A/C device %s", electra_ac.name)
                    ac_list.append(electra_ac)
                else:
                    logger.debug(
                        "Discovered non-AC device of type %s",
                        ac.get("deviceTypeName"),
                    )

            try:
                async with TaskGroup() as tg:
                    for ac in ac_list:
                        tg.create_task(self.get_last_telemtry(ac))
            except ExceptionGroup as exg:
                # TaskGroup wraps task failures in an ExceptionGroup; surface
                # the underlying API error so callers can catch ElectraApiError.
                for exc in exg.exceptions:
                    if isinstance(exc, ElectraApiError):
                        raise exc from exg
                raise

            for ac in ac_list:
                ac.update_features()

            self._devices = ac_list

        else:
            raise ElectraApiError(f"Failed to fetch devices {resp}")

    async def get_last_telemtry(self, ac: ElectraAirConditioner) -> None:
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

    async def set_state(self, device: ElectraAirConditioner) -> dict[str, Any]:
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
