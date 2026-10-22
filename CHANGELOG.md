# Changelog

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
