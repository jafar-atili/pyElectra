# Changelog

## 1.2.12

- New: the server-side timers are readable and writable. `OPER.TIMER` only says
  that one is set; the schedule itself lives in the account's events, and this
  release exposes them: `get_events(device)` returns `ElectraEvent` objects,
  `create_event(device, event)` adds one, `update_event(device, event)` writes a
  changed one back and `delete_event(device, event_id)` removes one. An event is
  a local `HH:MM` time, a weekday mask, an enabled flag and a partial `OPER` map
  (`actions`) applied when it fires.
  `GET_EVENTS` needs the device id in its data - without it the cloud answers
  `res: 99` with a null event list, which looks exactly like an account with no
  timers. `SET_EVENT` wants the event under an `event` key, and takes an omitted
  `eventId` as "create this" while a supplied one means "update this".
- New: `event.WEEKDAYS` / `weekdays_to_mask()` / `mask_to_weekdays()` for the
  `days` mask, whose bit 0 is Sunday through bit 6 Saturday and `127` every day,
  plus `validate_time()` for the `HH:MM` form the cloud expects.
- New: `get_events_enabled(device)` and `set_events_enabled(device, enable)` for
  the per-device switch that turns every timer off at once, which the Electra app
  offers next to the individual ones. Its request key is `enable` while its two
  answers call the same flag `enabled` and `enableEvents`.
- Fixed: `get_timer_mode()` and `set_timer_mode()` documented `OPER.TIMER` as the
  server-side timer. It is not: enabling or disabling an event, or the per-device
  events flag, leaves that field untouched (verified against the live cloud),
  while writing it is accepted, holds, and moves no other field. It is a
  unit-side indication with no schedule behind it, and the docstrings now say so.

## 1.2.11

- New: `set_ifeel_mode()` / `get_ifeel_mode()`, `set_sleep_mode()` /
  `get_sleep_mode()` and `set_timer_mode()` / `get_timer_mode()` read and write
  the `IFEEL`, `SLEEP` and `TIMER` flags in the `OPER` map — the three
  user-facing flags the other clients of this API already drive and this
  library never touched. iFeel follows the remote's sensor, sleep ramps the
  temperature while the room is asleep, and timer is the server-side schedule
  the Electra app sets. Each `get_` returns `None` for a unit that does not
  report the field and each `set_` leaves such a unit alone, the same rule
  `get_filter_clean_required()` follows.
- Fix: `set_turbo_mode()` and `set_shabat_mode()` wrote their field into the
  `OPER` map even for a unit that does not report it, and `get_turbo_mode()` /
  `get_shabat_mode()` indexed it — so such a unit got a `KeyError` out of the
  getter and carried a field it never sent in every command that followed. Both
  pairs now use the same helpers as the flags above: an absent field reads as
  `None` and the setters leave it alone. `get_shabat_mode()` feeds a preset in
  the Home Assistant integration, which now reads `None` as "no preset" instead
  of failing the poll.
- Fix: a request the cloud refuses is replayed once with a renewed session ID.
  A SID the cloud had stopped accepting came back as a non-success status, so
  the call failed until some later poll happened to refresh the token; one
  renewal plus one replay heals the call instead. The renewal is skipped when
  the token cannot be validated again — the vendor's lockout protection refuses
  a second `VALIDATE_TOKEN` within five minutes — and the original answer is
  returned rather than replaced by a renewal error.

## 1.2.10

- Fix: `get_measurement_temperature(field)` left an encoded negative reading
  as it came in, because only values above the 100 °C threshold were shifted.
  An encoded -1280 is -5 °C, and it is shifted now. This also fixes the room
  temperature, which is read through the same method.
- Change: `get_filter_clean_required()` returns `None` for a unit that does not
  report `CLEAR_FILT` at all, instead of `False`. A caller that creates an
  entity for the reminder can now tell "not reported" from "no reminder".

## 1.2.9

- Change: the `DIAG_L2` telemetry block is no longer discarded. It is kept as
  `ElectraAirConditioner.measurements`, so a caller can surface the fields this
  library does not read itself — the radio signal strength, the coil
  temperatures, the health flags and the bus counters.
- Change: `get_measurement_temperature(field)` returns a telemetry temperature in
  Celsius, applying the same ×256 normalization the room temperature already went
  through. It returns `None` for a unit that does not report the field, or that
  reports something which is not a number, instead of raising.
- Change: the device record's firmware and hardware versions are parsed into
  `fm_version` and `hw_version`, next to the existing `serial_number`.
- Change: `get_filter_clean_required()` reads the `CLEAR_FILT` filter-cleaning
  reminder from `OPER`. A unit that does not report the field reads as having no
  reminder.
- Fix: a non-numeric `I_RAT`/`I_CALC_AT` value no longer raises `ValueError`
  mid-poll; the room temperature keeps the value it already had.
- Tests: coverage for the retained telemetry, the temperature normalization and
  its missing and non-numeric cases, the parsed versions and the filter reminder.

## 1.2.8

- Fix: a rejected request for a session ID did not count as an attempt, so the
  5-minute delay between `VALIDATE_TOKEN` requests never applied while the account
  was locked out — every retry went straight back to the API, forever. The
  timestamp is now recorded before the request rather than on success, and the
  delay raises an `ElectraApiError` instead of returning without a session ID and
  leaving the caller to send a request with `sid: null`.
- Change: an `Intruder lockout` answer now raises `ElectraIntruderLockoutError`, a
  subclass of `ElectraApiError`, so callers can tell the vendor lockout — which
  only signing in again clears — from a transient failure. The check is what the
  previously unused `Attributes.INTRUDER_LOCKOUT` constant was declared for.
- Fix: a `VALIDATE_TOKEN` response without a `data` object no longer raises
  `TypeError`.
- Tests: coverage for the lockout, both delay paths, the session ID cache and
  `force`.

## 1.2.7

- Fix: `fetch_devices()` raised `TypeError: 'NoneType' object is not iterable` when
  the API answered with `status: 0` and a null device list, so Home Assistant
  reported an unhandled traceback instead of a setup failure it could retry.
  The response is now checked, and a missing device list raises
  `ElectraApiError` — which the integration already turns into
  `ConfigEntryNotReady`. An account that legitimately reports an empty list still
  sets up with no devices, as before.
- Tests: coverage for a null device list, a missing data block, an account with no
  devices, and normal device discovery.

## 1.2.6

- Fix: `turn_on()` was a no-op on units that do not report a `TURN_ON_OFF`
  field. Those units encode the power state in `AC_MODE`, which `turn_off()`
  overwrites with `STBY`, so nothing was left to turn back on and the unit
  stayed off. `turn_on()` now restores the mode the unit was last running in,
  taken from the `O_ODU_MODE` telemetry field — which the cloud keeps reporting
  while the unit is off, and which also reflects modes last set from the Electra
  app or the infrared remote rather than by this library.
- Change: `turn_on()` now returns `bool`, `False` when the previous mode is
  unknown so callers can apply their own fallback instead of sending a silent
  no-op. Callers that ignore the return value are unaffected.
- Change: `O_ODU_MODE` is no longer required; a unit that omits it no longer
  raises `KeyError` during a telemetry update.
- Tests: coverage for both unit families, restoring a mode set outside this
  library, and the unknown-mode fallback.

## 1.2.5

- Fix: tolerate device records that omit `deviceToken`; `fetch_devices()` used to
  raise `KeyError: 'deviceToken'` and setup failed entirely (#20).
- Fix: normalize the ×256 left-shifted `I_RAT` / `I_CALC_AT` telemetry back to
  Celsius — current temperature was reported as 5,632 °C instead of 22 °C. Raw
  values that are already plausible room temperatures are left untouched.
- Fix: malformed `ElectraApiError` messages. Two call sites raised with
  `raise ElectraApiError("... %s", value)`, and "Recieved" is now "Received".
- Fix: catch `builtins.TimeoutError` instead of the deprecated `asyncio` alias.
- Change: per-device telemetry is fetched with `asyncio.TaskGroup`, and
  `ElectraApiError` is surfaced to callers instead of a bare `ExceptionGroup`.
- Change: the session ID (an authorization credential) and full device records
  are no longer written to debug logs.
- Change: requires Python >= 3.11.
- Tests: regression coverage for the deviceToken tolerance and both temperature
  paths; CI added (lint, mypy, tests on 3.11-3.13).

## 1.2.4

- Previous release, July 2024.
