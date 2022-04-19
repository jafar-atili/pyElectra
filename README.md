# pySwitchbee

Library to control Electra Air Condtioiner IoT devices

Based on: https://github.com/nitaybz/homebridge-electra-smart

Usage:

import electra

async def main():
    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False), timeout=aiohttp.ClientTimeout(total=10))
    api = ElectraAPI('IMEI_KEY', 'TOKEN_KEY', session)
 
    devices = await api.get_devices()
    if (devices):
        for device in devices:
            await api.get_last_telemtry(device)
            assert(isinstance (device, ElectraAC))
            print(device.id)
            if device.id == 93813:
                device.turn_on()
                device.set_fan_speed(OPER_FAN_SPEED_LOW)
                device.set_temp(26)
                await api.set_state(device)
                

    await session.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(main())

