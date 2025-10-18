# pyElectra

![PyPI](https://img.shields.io/pypi/v/pyelectra?label=pypi%20package)
![PyPI - Downloads](https://img.shields.io/pypi/dm/pyelectra)

Python library to control Electra Smart Air Condtioiner devices


Usage:

```python
import sys
import asyncio

import aiohttp

from electrasmart import api as electra_api
from electrasmart.api import ElectraAPI
from electrasmart.api.utils import generate_imei

import logging


async def main():
    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False), timeout=aiohttp.ClientTimeout(total=10))

    # User phone number
    phone_number = input("Enter your account phone number: ")
    # Generate token
    imei = electra_api.utils.generate_imei()
    api = electra_api.ElectraAPI(session, phone_number=phone_number, imei=imei)
    try:
        resp = await api.generate_new_token()
    except ElectraApiError as e:
        # handle error
        pass

    otp = input("Enter the OTP you recieved via SMS: ")
    # more error handling
    if resp[electra_api.const.Attributes.STATUS] == electra_api.const.STATUS_SUCCESS:
        if resp[electra_api.const.Attributes.DATA][electra_api.const.Attributes.RES] != electra_api.const.STATUS_SUCCESS:
            print("Wrong phone number or unregistered user")
            sys.exit(1)

        resp = await api.validate_one_time_password(otp=otp)
        if resp[electra_api.const.Attributes.DATA][electra_api.const.Attributes.RES] == electra_api.const.STATUS_SUCCESS:
            token = resp[electra_api.const.Attributes.DATA][electra_api.const.Attributes.TOKEN]
        else:
            print("wrong OTP")
            sys.exit(1)

    await api.fetch_devices()
    for ac in api.devices:
        #assert(isinstance(ac, ElectraAirConditioner))
        print(f"AC NAME: {ac.name}")
        print(f"AC STATUS: {ac.status}")
        if ac.name == "Saloon AC":
            ac.turn_on()
            ac.set_mode(OPER_MODE_COOL)
            ac.set_temperature(17)
            ac.set_fan_speed(OPER_FAN_SPEED_HIGH)
            ac.set_vertical_swing(OPER_ON)
            api.set_state(ac)  # This will send the conf to the AC


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('main').info("Started")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
```
