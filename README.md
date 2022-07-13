# pyElectra

![PyPI](https://img.shields.io/pypi/v/pyelectra?label=pypi%20package)
![PyPI - Downloads](https://img.shields.io/pypi/dm/pyelectra)

Python library to control Electra Smart Air Condtioiner devices


Usage:

```python
import asyncio

import aiohttp

from electrasmart import *


async def main():
    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False), timeout=aiohttp.ClientTimeout(total=10))
    api = ElectraAPI(session)

    # User phone number
    phone_number = "0521234567"
    # Generate token
    imei = generate_imei()
    try:
        resp = await api.generate_new_token(phone_number=phone_number, imei=imei)
    except ElectraApiError as e:
        # handle error
        pass

    otp = input("Enter the OTP you recieved via SMS")
    # more error handling
    if resp[electra.ATTR_STATUS] == electra.STATUS_SUCCESS:
        if resp[electra.ATTR_DATA][electra.ATTR_RES] != electra.STATUS_SUCCESS:
            # Wrong phone number or unregistered user
            sys.exit(1)
     
        resp = await api.validate_one_time_password(otp=otp, imei=imei, phone_number=phone_number)
        if resp[electra.ATTR_DATA][electra.ATTR_RES] == electra.STATUS_SUCCESS:
            token = resp[electra.ATTR_DATA][electra.ATTR_TOKEN]
        else:
            # wrong OTP
            sys.exit(1)
    
    ac_devices = api.get_devices()
    for ac in ac_devices:
        assert(ac, ElectraAirConditioner)
        if ac.name == "Saloon AC":
            ac.turn_on()
            ac.set_mode(OPER_MODE_COOL)
            ac.set_temperature(17)
            ac.set_fan_speed(OPER_FAN_SPEED_HIGH)
            ac.set_vertical_swing(OPER_ON)
            api.set_state(ac)  # This will send the conf to the AC


loop = asyncio.get_event_loop()
loop.run_until_complete(main())

```
