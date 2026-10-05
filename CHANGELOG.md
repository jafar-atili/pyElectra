# Changelog

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
