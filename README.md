# pyElectra

![PyPI](https://img.shields.io/pypi/v/pyelectra?label=pypi%20package)
![PyPI - Downloads](https://img.shields.io/pypi/dm/pyelectra)
![Python](https://img.shields.io/pypi/pyversions/pyelectra)

Python library to control Electra Smart air conditioners.

It is the client library behind the [`electrasmart`](https://www.home-assistant.io/integrations/electrasmart)
Home Assistant integration.

## Install

```sh
pip install pyElectra
```

Requires Python 3.11 or newer.

## Usage

```python
import asyncio

import aiohttp

from electrasmart.api import ElectraAPI, ElectraApiError
from electrasmart.api.utils import generate_imei
from electrasmart.device.const import OperationMode


async def main() -> None:
    session = aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False),
        timeout=aiohttp.ClientTimeout(total=10),
    )

    # 1. Register your phone number. The IMEI identifies this "device" to
    #    Electra, so generate it once and store it.
    api = ElectraAPI(session)
    imei = generate_imei()
    await api.generate_new_token(phone_number="0521234567", imei=imei)

    # 2. Confirm the OTP that was sent by SMS.
    resp = await api.validate_one_time_password(
        otp="123456", imei=imei, phone_number="0521234567"
    )
    token = resp["data"]["token"]

    # 3. Connect with the token and enumerate devices. The token is long-lived,
    #    so steps 1-2 only need to happen once.
    api = ElectraAPI(session, imei=imei, token=token)
    await api.fetch_devices()

    for ac in api.devices:
        print(ac.name, ac.get_temperature(), ac.get_sensor_temperature())

        ac.turn_on()
        ac.set_mode(OperationMode.MODE_COOL)
        ac.set_temperature(22)
        ac.set_fan_speed(OperationMode.FAN_SPEED_HIGH)
        await api.set_state(ac)  # push the new state to the A/C


asyncio.run(main())
```

Network failures and API-level errors raise `ElectraApiError`. An account the
vendor has locked out raises `ElectraIntruderLockoutError`, a subclass of it,
which nothing but signing in again will clear.

## Changelog

See [CHANGELOG.md](CHANGELOG.md). Notable in 1.2.5:

- The `KeyError: 'deviceToken'` setup crash on device records that omit that field.
- Current temperature reported as the raw ×256 left-shifted telemetry value
  (5,632 °C instead of 22 °C).

## Development

```sh
pip install -e . pytest ruff mypy

pytest                       # tests
ruff format --check .        # formatting
ruff check .                 # lint
mypy --config-file mypy.ini src/electrasmart
```

CI runs lint, type checks and the test suite on Python 3.11, 3.12 and 3.13.

## License

Apache-2.0
