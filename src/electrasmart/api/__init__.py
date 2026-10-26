from __future__ import annotations

import builtins
from asyncio import TaskGroup
from datetime import UTC, datetime
from json import JSONDecodeError, loads
from logging import getLogger
from typing import Any

from aiohttp import ClientError, ClientSession

from electrasmart.device import ElectraAirConditioner
from electrasmart.event import ElectraEvent, validate_time

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

    async def _send_request_with_sid(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a request, replaying it once with a renewed session ID.

        The cloud reports a session ID it no longer accepts as a non-success
        status rather than as an error, which used to surface as a hard failure
        until some later call happened to refresh the SID. One renewal plus one
        replay turns that into a call that heals itself.

        A renewal is skipped when the token cannot be validated again — the
        account's lockout protection refuses a second ``VALIDATE_TOKEN`` inside
        ``DELAY_BETWEEM_SID_REQUESTS``, and an account that is locked out has to
        be signed in again by its owner — so the original answer is returned
        unchanged rather than masked by a second error.
        """
        await self._get_sid()
        payload["sid"] = self._sid

        resp = await self._send_request(payload=payload)
        if not isinstance(resp, dict) or resp.get(Attributes.STATUS) == STATUS_SUCCESS:
            # Nothing to retry: either the call went through or the body is not
            # an answer this client can read at all.
            return resp

        logger.debug("Request was refused, renewing the session id and retrying once")
        try:
            await self._get_sid(force=True)
        except ElectraApiError as ex:
            logger.debug("Could not renew the session id: %s", ex)
            return resp

        payload["sid"] = self._sid
        return await self._send_request(payload=payload)

    async def fetch_devices(self) -> None:
        logger.debug("About to Get Electra AC devices")

        payload = {"pvdid": 1, "id": 99, "cmd": "GET_DEVICES"}

        ac_list: list[ElectraAirConditioner] = []
        resp = await self._send_request_with_sid(payload)
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

        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "GET_LAST_TELEMETRY",
            "data": {"id": ac.id, "commandName": "OPER,DIAG_L2"},
        }

        resp = await self._send_request_with_sid(payload)
        if resp[Attributes.STATUS] != STATUS_SUCCESS:
            raise ElectraApiError(f"Failed to get AC operation state: {resp}")
        else:
            ac.update_operation_states(resp[Attributes.DATA])

    async def set_state(self, device: ElectraAirConditioner) -> dict[str, Any]:
        json_command = device.get_operation_state()

        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "SEND_COMMAND",
            "data": {"id": device.id, "commandJson": json_command},
        }

        return await self._send_request_with_sid(payload)

    async def get_events(self, device: ElectraAirConditioner) -> list[ElectraEvent]:
        """Return the device's server-side timers.

        The cloud answers ``res: 99`` with a null event list when the request
        carries no device id, so that parameter is what makes this readable at
        all - a call without it looks exactly like an account with no timers.
        """
        data = await self._get_events_data(device)

        events = data.get("events")
        if isinstance(events, str):
            events = loads(events)

        return [ElectraEvent.from_api(event) for event in (events or [])]

    async def get_events_enabled(self, device: ElectraAirConditioner) -> bool:
        """Return whether the device's timers are enabled as a whole.

        This is the per-device switch in the Electra app: with it off, no event
        fires however each one is set. The cloud reports the same flag twice, as
        ``enabled`` in the ``GET_EVENTS`` answer and as ``enableEvents`` on the
        device record.
        """
        enabled = (await self._get_events_data(device)).get("enabled")
        if isinstance(enabled, str):
            return enabled.strip().lower() in ("true", "1", "on")
        return bool(enabled)

    async def set_events_enabled(
        self, device: ElectraAirConditioner, enable: bool
    ) -> None:
        """Enable or disable every timer on a device at once.

        The one command here whose request key differs from every name its
        answers use: it is written as ``enable``. Every other candidate key is
        refused outright, so a wrong one cannot land silently.
        """
        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "SET_DEVICE_EVENTS_FLAG",
            "data": {"deviceId": device.id, "enable": enable},
        }

        resp = await self._send_request_with_sid(payload)
        data = resp.get(Attributes.DATA) or {}
        if resp.get(Attributes.STATUS) != STATUS_SUCCESS or (
            data.get(Attributes.RES) != STATUS_SUCCESS
        ):
            raise ElectraApiError(
                f"Failed to set the events flag of {device.name}: {resp}"
            )

    async def create_event(
        self,
        device: ElectraAirConditioner,
        event: ElectraEvent,
    ) -> ElectraEvent:
        """Add a timer and return it as the cloud stored it.

        The id is left out of the request on purpose: the cloud generates one,
        and an id of our own is rejected. The new event is then read back,
        because nothing else reports its id.
        """
        validate_time(event.time)
        known = {existing.event_id for existing in await self.get_events(device)}
        await self._set_event(device, event, include_id=False)

        created = [
            existing
            for existing in await self.get_events(device)
            if existing.event_id not in known
        ]
        if len(created) != 1:
            raise ElectraApiError(
                f"Failed to create the event for {device.name}: the cloud "
                f"answered with {len(created)} new events"
            )

        return created[0]

    async def update_event(
        self,
        device: ElectraAirConditioner,
        event: ElectraEvent,
    ) -> None:
        """Write a changed timer back, e.g. to enable it or move its time."""
        validate_time(event.time)
        await self._set_event(device, event, include_id=True)

    async def delete_event(
        self,
        device: ElectraAirConditioner,
        event_id: str,
    ) -> None:
        """Remove a timer by its event id."""
        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "DELETE_EVENT",
            "data": {"deviceId": device.id, "eventId": event_id},
        }

        resp = await self._send_request_with_sid(payload)
        data = resp.get(Attributes.DATA) or {}
        if resp.get(Attributes.STATUS) != STATUS_SUCCESS or (
            data.get(Attributes.RES) != STATUS_SUCCESS
        ):
            raise ElectraApiError(f"Failed to delete the event {event_id}: {resp}")

    async def _get_events_data(self, device: ElectraAirConditioner) -> dict[str, Any]:
        """Fetch the ``GET_EVENTS`` answer, refusing either kind of failure.

        Both failures matter: a non-zero status is an error, while ``res: 99``
        is the answer to a request the cloud could not use at all.
        """
        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "GET_EVENTS",
            "data": {"deviceId": device.id},
        }

        resp = await self._send_request_with_sid(payload)
        if resp.get(Attributes.STATUS) != STATUS_SUCCESS:
            raise ElectraApiError(f"Failed to get the events of {device.name}: {resp}")

        data = resp.get(Attributes.DATA) or {}
        if data.get(Attributes.RES) != STATUS_SUCCESS:
            raise ElectraApiError(
                f"Failed to get the events of {device.name}: the cloud answered "
                f"res {data.get(Attributes.RES)!r}"
            )

        return data

    async def _set_event(
        self,
        device: ElectraAirConditioner,
        event: ElectraEvent,
        include_id: bool,
    ) -> None:
        """Create or update one event: the single call the cloud offers for both.

        The event has to sit under an ``event`` key; the fields on their own, or
        under any other wrapper, are answered with ``res: 99``.
        """
        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "SET_EVENT",
            "data": {
                "deviceId": device.id,
                "event": event.to_api(include_id=include_id),
            },
        }

        resp = await self._send_request_with_sid(payload)
        data = resp.get(Attributes.DATA) or {}
        if resp.get(Attributes.STATUS) != STATUS_SUCCESS or (
            data.get(Attributes.RES) != STATUS_SUCCESS
        ):
            raise ElectraApiError(
                f"Failed to save the event {event.event_id!r}: {resp}"
            )
