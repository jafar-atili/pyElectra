# Changelog

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
