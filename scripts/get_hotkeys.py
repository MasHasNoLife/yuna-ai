import asyncio
import os

import pyvts

plugin_info = {
    "plugin_name": "Yuna AI Controller",
    "developer": "Yuna Project",
    "authentication_token_path": os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "vts_token.txt"
    ),
}


async def main():
    print("Connecting to VTube Studio...")
    vts = pyvts.vts(plugin_info=plugin_info)
    try:
        await vts.connect()
        await vts.read_token()
        if not vts.authentic_token:
            print("Requesting authorization... Please click 'Allow' inside VTube Studio!")
            await vts.request_authenticate_token()
            await vts.write_token()
        await vts.request_authenticate()
    except Exception as e:
        print(
            f"Could not connect! Make sure VTube Studio is running and 'Start API' is ON. Error: {e}"
        )
        return

    print("Connected! Fetching hotkeys for your current model...\n")

    try:
        request = vts.vts_request.requestHotKeyList()
        response = await vts.request(request)
        hotkeys = response.get("data", {}).get("availableHotkeys", [])

        if not hotkeys:
            print(
                "No hotkeys found! You need to set them up in VTube Studio first (the clapperboard 🎬 icon)."
            )
        else:
            print("Here are your Hotkey IDs! Copy the long IDs into your vts_link.py file:\n")
            for hk in hotkeys:
                name = hk.get("name", "Unnamed")
                hk_id = hk.get("hotkeyID", "")
                print(f"Name: {name}")
                print(f"ID:   {hk_id}")
                print("-" * 40)
    except Exception as e:
        print(f"Failed to fetch hotkeys: {e}")

    await vts.close()


if __name__ == "__main__":
    asyncio.run(main())
