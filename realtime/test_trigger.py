import asyncio
import pyvts
import os

plugin_info = {
    "plugin_name": "Yuna AI Controller",
    "developer": "Yuna Project",
    "authentication_token_path": os.path.join(os.path.dirname(__file__), "vts_token.txt")
}

async def main():
    vts = pyvts.vts(plugin_info=plugin_info)
    await vts.connect()
    await vts.read_token()
    await vts.request_authenticate()
    print("Connected. Triggering...")
    request = vts.vts_request.requestTriggerHotKey("135ec454ec524d8c8d7c90a20bbc915d")
    response = await vts.request(request)
    print("Response:", response)
    await vts.close()

asyncio.run(main())
