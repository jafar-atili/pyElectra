"""Tests for the Electra cloud API client."""

import asyncio
import builtins
import json
from json import JSONDecodeError

import pytest
from aiohttp import ClientError

from electrasmart.api import ElectraAPI, ElectraApiError
from electrasmart.device import ElectraAirConditioner
from electrasmart.event import ElectraEvent


def _device_record(device_type: str = "A/C") -> dict:
    return {
        "id": "1234123456",
        "name": "Living Room AC",
        "mac": "aa:bb:cc:dd:ee:ff",
        "manufactor": "Electra",
        "deviceTypeName": device_type,
    }


def _device() -> ElectraAirConditioner:
    return ElectraAirConditioner(_device_record())


class _FakeResponse:
    """Stands in for the aiohttp response."""

    def __init__(self, payload=None, json_error: Exception | None = None) -> None:
        self._payload = payload
        self._json_error = json_error

    async def json(self, content_type=None):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


class _FakeSession:
    """Stands in for the aiohttp client session, recording what was sent."""

    def __init__(self, response=None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.requests: list[dict] = []

    async def post(self, url=None, json=None, headers=None):
        self.requests.append({"url": url, "json": json, "headers": headers})
        if self._error is not None:
            raise self._error
        return self._response


def _api_without_sid(monkeypatch) -> ElectraAPI:
    """An API object whose session ID lookup never reaches the network."""
    api = ElectraAPI(  # type: ignore[arg-type]
        websession=None, imei="2b95000012345678", token="a-token"
    )

    async def _get_sid(force: bool = False) -> None:
        return None

    monkeypatch.setattr(api, "_get_sid", _get_sid)
    return api


def _api_returning(monkeypatch, response) -> tuple[ElectraAPI, list]:
    """An API object answering `response`, plus the payloads it sent."""
    api = _api_without_sid(monkeypatch)
    sent: list[dict] = []

    async def _send_request(payload: dict) -> dict:
        sent.append(payload)
        return response

    monkeypatch.setattr(api, "_send_request", _send_request)
    return api, sent


def _api_with_send_request(monkeypatch, response) -> tuple[ElectraAPI, list]:
    """An API object answering `response`, with the real session ID lookup."""
    api = ElectraAPI(  # type: ignore[arg-type]
        websession=None, imei="2b95000012345678", token="a-token"
    )
    sent: list[dict] = []

    async def _send_request(payload: dict) -> dict:
        sent.append(payload)
        return response

    monkeypatch.setattr(api, "_send_request", _send_request)
    return api, sent


def _telemetry(oper: dict[str, str], diag: dict[str, str]) -> dict:
    return {
        "commandJson": {
            "OPER": json.dumps({"OPER": oper}),
            "DIAG_L2": json.dumps({"DIAG_L2": diag}),
        },
        "timeDelta": 5,
    }


def test_send_request_posts_to_the_api_endpoint() -> None:
    session = _FakeSession(
        _FakeResponse({"status": 0, "data": {"sid": "a-session-id"}})
    )
    api = ElectraAPI(websession=session)  # type: ignore[arg-type]

    result = asyncio.run(api._send_request({"cmd": "GET_DEVICES"}))

    assert result == {"status": 0, "data": {"sid": "a-session-id"}}
    assert session.requests == [
        {
            "url": "https://app.ecpiot.co.il/mobile/mobilecommand",
            "json": {"cmd": "GET_DEVICES"},
            "headers": {"user-agent": "Electra Client"},
        }
    ]


def test_send_request_reports_a_timeout_as_an_api_error() -> None:
    session = _FakeSession(error=builtins.TimeoutError("too slow"))
    api = ElectraAPI(websession=session)  # type: ignore[arg-type]

    with pytest.raises(ElectraApiError) as err:
        asyncio.run(api._send_request({"cmd": "GET_DEVICES"}))

    assert "time out" in str(err.value)


def test_send_request_reports_a_client_error_as_an_api_error() -> None:
    session = _FakeSession(error=ClientError("connection reset"))
    api = ElectraAPI(websession=session)  # type: ignore[arg-type]

    with pytest.raises(ElectraApiError) as err:
        asyncio.run(api._send_request({"cmd": "GET_DEVICES"}))

    assert "ClientError" in str(err.value)


def test_send_request_reports_invalid_json_as_an_api_error() -> None:
    session = _FakeSession(
        _FakeResponse(json_error=JSONDecodeError("bad", "<html>", 0))
    )
    api = ElectraAPI(websession=session)  # type: ignore[arg-type]

    with pytest.raises(ElectraApiError) as err:
        asyncio.run(api._send_request({"cmd": "GET_DEVICES"}))

    assert "invalid response" in str(err.value)


def test_generate_new_token_asks_the_api_to_send_a_code() -> None:
    session = _FakeSession(_FakeResponse({"status": 0, "data": {"res": 0}}))
    api = ElectraAPI(websession=session)  # type: ignore[arg-type]

    result = asyncio.run(api.generate_new_token("0501234567", "2b95000012345678"))

    assert result == {"status": 0, "data": {"res": 0}}
    assert session.requests[0]["json"] == {
        "pvdid": 1,
        "id": 99,
        "cmd": "SEND_OTP",
        "data": {"imei": "2b95000012345678", "phone": "0501234567"},
    }


def test_validate_one_time_password_asks_the_api_to_check_the_code() -> None:
    session = _FakeSession(_FakeResponse({"status": 0, "data": {"res": 0}}))
    api = ElectraAPI(websession=session)  # type: ignore[arg-type]

    result = asyncio.run(
        api.validate_one_time_password("1234", "2b95000012345678", "0501234567")
    )

    assert result == {"status": 0, "data": {"res": 0}}
    assert session.requests[0]["json"] == {
        "pvdid": 1,
        "id": 99,
        "cmd": "CHECK_OTP",
        "data": {
            "imei": "2b95000012345678",
            "phone": "0501234567",
            "code": "1234",
            "os": "android",
            "osver": "M4B30Z",
        },
    }


def test_get_sid_without_a_response_raises(monkeypatch) -> None:
    """An answer with no body must not be read as a session ID."""
    api, _ = _api_with_send_request(monkeypatch, None)

    with pytest.raises(ElectraApiError) as err:
        asyncio.run(api._get_sid())

    assert "Failed to retrieve sid" in str(err.value)


def test_fetch_devices_ignores_devices_that_are_not_air_conditioners(
    monkeypatch,
) -> None:
    api, _ = _api_returning(
        monkeypatch,
        {
            "status": 0,
            "data": {
                "devices": [
                    _device_record(),
                    _device_record(device_type="SENSOR"),
                ]
            },
        },
    )

    asyncio.run(api.fetch_devices())

    assert [ac.name for ac in api.devices] == ["Living Room AC"]


def test_fetch_devices_raises_when_the_api_reports_a_failure(monkeypatch) -> None:
    api, _ = _api_returning(monkeypatch, {"status": 1, "data": {}})

    with pytest.raises(ElectraApiError):
        asyncio.run(api.fetch_devices())


def test_fetch_devices_surfaces_a_telemetry_failure(monkeypatch) -> None:
    """A failing telemetry task must reach the caller as an API error.

    The tasks run in a TaskGroup, which wraps whatever they raise in an
    ExceptionGroup; the API error has to survive that wrapping.
    """
    api, _ = _api_returning(
        monkeypatch,
        {"status": 0, "data": {"devices": [_device_record()]}},
    )

    async def _get_last_telemtry(ac) -> None:
        raise ElectraApiError("Failed to get AC operation state")

    monkeypatch.setattr(api, "get_last_telemtry", _get_last_telemtry)

    with pytest.raises(ElectraApiError):
        asyncio.run(api.fetch_devices())


def test_fetch_devices_surfaces_an_unexpected_telemetry_failure(monkeypatch) -> None:
    """Anything that is not an API error is re-raised as it is."""
    api, _ = _api_returning(
        monkeypatch,
        {"status": 0, "data": {"devices": [_device_record()]}},
    )

    async def _get_last_telemtry(ac) -> None:
        raise ValueError("unexpected")

    monkeypatch.setattr(api, "get_last_telemtry", _get_last_telemtry)

    with pytest.raises(ExceptionGroup) as err:
        asyncio.run(api.fetch_devices())

    assert not isinstance(err.value.exceptions[0], ElectraApiError)


def test_get_last_telemetry_raises_when_the_api_reports_a_failure(
    monkeypatch,
) -> None:
    api, _ = _api_returning(monkeypatch, {"status": 1, "data": {}})

    with pytest.raises(ElectraApiError):
        asyncio.run(api.get_last_telemtry(_device()))


def test_get_last_telemetry_updates_the_device(monkeypatch) -> None:
    api, _ = _api_returning(
        monkeypatch,
        {
            "status": 0,
            "data": _telemetry({"AC_MODE": "COOL", "SPT": "22"}, {"I_RAT": "22"}),
        },
    )
    device = _device()

    asyncio.run(api.get_last_telemtry(device))

    assert device.get_mode() == "COOL"
    assert device.get_sensor_temperature() == 22


def test_set_state_sends_the_operation_state(monkeypatch) -> None:
    api, sent = _api_returning(monkeypatch, {"status": 0})
    device = _device()

    result = asyncio.run(api.set_state(device))

    assert result == {"status": 0}
    assert sent[0]["cmd"] == "SEND_COMMAND"
    assert sent[0]["data"] == {
        "id": "1234123456",
        "commandJson": json.dumps({"OPER": {}}),
    }


def _api_answering_each_call(
    monkeypatch, responses: list[dict | None]
) -> tuple[ElectraAPI, list[dict], list[bool]]:
    """An API object answering every call with the next response.

    Returns the API, the payloads it sent, and which session ID lookups were
    forced renewals.
    """
    api = ElectraAPI(  # type: ignore[arg-type]
        websession=None, imei="2b95000012345678", token="a-token"
    )
    sent: list[dict] = []
    renewals: list[bool] = []

    async def _send_request(payload: dict) -> dict:
        sent.append(dict(payload))
        return responses[min(len(sent) - 1, len(responses) - 1)]

    async def _get_sid(force: bool = False) -> None:
        renewals.append(force)
        if force:
            api._sid = "renewed-sid"

    monkeypatch.setattr(api, "_send_request", _send_request)
    monkeypatch.setattr(api, "_get_sid", _get_sid)
    return api, sent, renewals


def test_a_successful_request_does_not_renew_the_session_id(monkeypatch) -> None:
    api, sent, renewals = _api_answering_each_call(
        monkeypatch, [{"status": 0, "data": {"devices": []}}]
    )

    asyncio.run(api.fetch_devices())

    assert len(sent) == 1
    assert renewals == [False]


def test_a_refused_request_is_replayed_with_a_renewed_session_id(monkeypatch) -> None:
    """A session ID the cloud no longer accepts heals itself."""
    api, sent, renewals = _api_answering_each_call(
        monkeypatch,
        [
            {"status": 1, "data": {}},
            {"status": 0, "data": {"devices": [_device_record()]}},
        ],
    )

    asyncio.run(api.fetch_devices())

    assert [payload["cmd"] for payload in sent[:2]] == ["GET_DEVICES", "GET_DEVICES"]
    assert [payload["sid"] for payload in sent[:2]] == [None, "renewed-sid"]
    # One forced renewal for the replay, the rest are ordinary lookups.
    assert renewals == [False, True, False]
    assert [ac.name for ac in api.devices] == ["Living Room AC"]


def test_a_refused_request_that_cannot_be_renewed_reports_the_refusal(
    monkeypatch,
) -> None:
    """The lockout protection refuses a second token validation.

    The original answer is what the caller gets then: a renewal error would
    hide why the request failed in the first place.
    """
    api = ElectraAPI(  # type: ignore[arg-type]
        websession=None, imei="2b95000012345678", token="a-token"
    )
    sent: list[dict] = []

    async def _send_request(payload: dict) -> dict:
        sent.append(dict(payload))
        return {"status": 1, "data": {}}

    async def _get_sid(force: bool = False) -> None:
        if force:
            raise ElectraApiError("a session ID was requested less than 5 minutes ago")

    monkeypatch.setattr(api, "_send_request", _send_request)
    monkeypatch.setattr(api, "_get_sid", _get_sid)

    with pytest.raises(ElectraApiError) as err:
        asyncio.run(api.fetch_devices())

    assert "Failed to fetch devices" in str(err.value)
    assert len(sent) == 1


def test_an_unreadable_body_is_returned_without_a_retry(monkeypatch) -> None:
    """A body this client cannot read is not a stale session ID."""
    api, sent, renewals = _api_answering_each_call(monkeypatch, [None])

    result = asyncio.run(api._send_request_with_sid({"cmd": "GET_DEVICES"}))

    assert result is None
    assert len(sent) == 1
    assert renewals == [False]


def test_set_state_replays_a_refused_command(monkeypatch) -> None:
    api, sent, _ = _api_answering_each_call(monkeypatch, [{"status": 1}, {"status": 0}])

    result = asyncio.run(api.set_state(_device()))

    assert result == {"status": 0}
    assert [payload["sid"] for payload in sent] == [None, "renewed-sid"]


def _events_answer(events, *, res: int = 0, status: int = 0) -> dict:
    """A ``GET_EVENTS`` answer, with the event list stringified as the cloud does."""
    return {
        "status": status,
        "data": {
            "enabled": True,
            "events": events if isinstance(events, str) else json.dumps(events),
            "res": res,
        },
    }


def _timer(event_id: str = "a-timer-id") -> dict:
    return {
        "eventId": event_id,
        "time": "17:58",
        "days": 94,
        "enabled": False,
        "actionsJson": {"TURN_ON_OFF": "ON", "SPT": "21"},
    }


def test_get_events_asks_for_the_device_and_parses_the_timers(monkeypatch) -> None:
    api, sent, _ = _api_answering_each_call(monkeypatch, [_events_answer([_timer()])])

    events = asyncio.run(api.get_events(_device()))

    assert sent[0]["cmd"] == "GET_EVENTS"
    assert sent[0]["data"] == {"deviceId": "1234123456"}
    assert [event.event_id for event in events] == ["a-timer-id"]
    assert events[0].weekdays == (
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "saturday",
    )
    assert events[0].actions == {"TURN_ON_OFF": "ON", "SPT": "21"}


def test_get_events_accepts_an_already_parsed_list(monkeypatch) -> None:
    api, _, _ = _api_answering_each_call(
        monkeypatch,
        [{"status": 0, "data": {"enabled": True, "events": [_timer()], "res": 0}}],
    )

    events = asyncio.run(api.get_events(_device()))

    assert [event.event_id for event in events] == ["a-timer-id"]


def test_get_events_is_empty_when_the_cloud_sends_no_list(monkeypatch) -> None:
    api, _, _ = _api_answering_each_call(monkeypatch, [_events_answer(None)])

    assert asyncio.run(api.get_events(_device())) == []


def test_get_events_raises_when_the_cloud_reports_a_failure(monkeypatch) -> None:
    api, _, _ = _api_answering_each_call(monkeypatch, [_events_answer(None, status=1)])

    with pytest.raises(ElectraApiError, match="Failed to get the events"):
        asyncio.run(api.get_events(_device()))


def test_get_events_raises_when_the_request_was_refused(monkeypatch) -> None:
    """Without a device id the cloud answers res 99 rather than an error."""
    api, _, _ = _api_answering_each_call(monkeypatch, [_events_answer(None, res=99)])

    with pytest.raises(ElectraApiError, match="res 99"):
        asyncio.run(api.get_events(_device()))


def test_create_event_leaves_the_id_out_and_reads_the_new_timer_back(
    monkeypatch,
) -> None:
    api, sent, _ = _api_answering_each_call(
        monkeypatch,
        [
            _events_answer([]),
            {"status": 0, "data": {"res": 0}},
            _events_answer([_timer()]),
        ],
    )
    new = ElectraEvent("", "17:58", 94, False, {"TURN_ON_OFF": "ON"})

    created = asyncio.run(api.create_event(_device(), new))

    set_event = sent[1]
    assert set_event["cmd"] == "SET_EVENT"
    assert set_event["data"]["deviceId"] == "1234123456"
    assert "eventId" not in set_event["data"]["event"]
    assert created.event_id == "a-timer-id"


def test_create_event_checks_the_time_before_calling_the_cloud(monkeypatch) -> None:
    api, sent, _ = _api_answering_each_call(monkeypatch, [])

    with pytest.raises(ValueError, match="HH:MM"):
        asyncio.run(
            api.create_event(_device(), ElectraEvent("", "24:00", 127, True, {}))
        )

    assert sent == []


def test_create_event_raises_when_the_new_timer_does_not_appear(monkeypatch) -> None:
    api, _, _ = _api_answering_each_call(
        monkeypatch,
        [
            _events_answer([]),
            {"status": 0, "data": {"res": 0}},
            _events_answer([]),
        ],
    )

    with pytest.raises(ElectraApiError, match="0 new events"):
        asyncio.run(
            api.create_event(_device(), ElectraEvent("", "17:58", 127, False, {}))
        )


def test_update_event_posts_the_existing_id(monkeypatch) -> None:
    api, sent, _ = _api_answering_each_call(
        monkeypatch, [{"status": 0, "data": {"res": 0}}]
    )

    asyncio.run(
        api.update_event(
            _device(), ElectraEvent("a-timer-id", "06:15", 127, True, {"SPT": "22"})
        )
    )

    assert sent[0]["data"]["event"] == {
        "eventId": "a-timer-id",
        "time": "06:15",
        "days": 127,
        "enabled": True,
        "actionsJson": {"SPT": "22"},
    }


def test_update_event_raises_when_the_save_is_refused(monkeypatch) -> None:
    api, _, _ = _api_answering_each_call(
        monkeypatch, [{"status": 0, "data": {"res": 99}}]
    )

    with pytest.raises(ElectraApiError, match="Failed to save the event"):
        asyncio.run(
            api.update_event(_device(), ElectraEvent("an-id", "06:15", 127, True, {}))
        )


def test_update_event_raises_when_the_cloud_reports_a_failure(monkeypatch) -> None:
    api, _, _ = _api_answering_each_call(
        monkeypatch, [{"status": 1, "data": {"res": 0}}]
    )

    with pytest.raises(ElectraApiError, match="Failed to save the event"):
        asyncio.run(
            api.update_event(_device(), ElectraEvent("an-id", "06:15", 127, True, {}))
        )


def test_delete_event_posts_the_event_id(monkeypatch) -> None:
    api, sent, _ = _api_answering_each_call(
        monkeypatch, [{"status": 0, "data": {"res": 0}}]
    )

    asyncio.run(api.delete_event(_device(), "a-timer-id"))

    assert sent[0]["cmd"] == "DELETE_EVENT"
    assert sent[0]["data"] == {"deviceId": "1234123456", "eventId": "a-timer-id"}


def test_delete_event_raises_when_the_delete_is_refused(monkeypatch) -> None:
    api, _, _ = _api_answering_each_call(
        monkeypatch, [{"status": 0, "data": {"res": 100}}]
    )

    with pytest.raises(ElectraApiError, match="Failed to delete the event"):
        asyncio.run(api.delete_event(_device(), "a-timer-id"))


def test_delete_event_raises_when_the_cloud_reports_a_failure(monkeypatch) -> None:
    api, _, _ = _api_answering_each_call(
        monkeypatch, [{"status": 1, "data": {"res": 0}}]
    )

    with pytest.raises(ElectraApiError, match="Failed to delete the event"):
        asyncio.run(api.delete_event(_device(), "a-timer-id"))
