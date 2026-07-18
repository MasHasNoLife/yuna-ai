"""
vts_diag.py — Diagnostic tool to query VTube Studio's actual parameter names.

Run this while VTube Studio is open with your model loaded:
    python scripts/vts_diag.py
"""
import asyncio
import os

import pyvts

plugin_info = {
    "plugin_name": "Yuna AI Controller",
    "developer": "Yuna Project",
    "authentication_token_path": os.path.join(os.path.dirname(os.path.abspath(__file__)), "vts_token.txt")
}

async def main():
    vts = pyvts.vts(plugin_info=plugin_info)
    
    print("Connecting to VTube Studio...")
    await vts.connect()
    
    print("Authenticating...")
    await vts.request_authenticate_token()
    is_auth = await vts.request_authenticate()
    if not is_auth:
        print("Authentication failed!")
        return
    print("Authenticated!\n")
    
    # Query all parameters
    req = vts.vts_request.requestTrackingParameterList()
    response = await vts.request(req)
    data = response.get("data", {})
    
    print(f"Model: {data.get('modelName', 'Unknown')}")
    print(f"Model ID: {data.get('modelID', 'Unknown')}")
    print(f"Model Loaded: {data.get('modelLoaded', False)}\n")
    
    # Default parameters (the ones we want to inject into)
    default_params = data.get("defaultParameters", [])
    print(f"═══ DEFAULT PARAMETERS ({len(default_params)}) ═══")
    print(f"{'Name':<30} {'Min':>8} {'Max':>8} {'Default':>8} {'Current':>8}")
    print("─" * 70)
    for p in default_params:
        print(f"{p['name']:<30} {p['min']:>8.1f} {p['max']:>8.1f} {p['defaultValue']:>8.1f} {p['value']:>8.2f}")
    
    # Input parameters
    input_params = data.get("inputParameters", [])
    if input_params:
        print(f"\n═══ INPUT PARAMETERS ({len(input_params)}) ═══")
        print(f"{'Name':<30} {'Min':>8} {'Max':>8} {'Default':>8} {'Current':>8}")
        print("─" * 70)
        for p in input_params:
            print(f"{p['name']:<30} {p['min']:>8.1f} {p['max']:>8.1f} {p['defaultValue']:>8.1f} {p['value']:>8.2f}")
    
    # Custom parameters
    custom_params = data.get("customParameters", [])
    if custom_params:
        print(f"\n═══ CUSTOM PARAMETERS ({len(custom_params)}) ═══")
        print(f"{'Name':<30} {'Min':>8} {'Max':>8} {'Default':>8} {'Current':>8}")
        print("─" * 70)
        for p in custom_params:
            print(f"{p['name']:<30} {p['min']:>8.1f} {p['max']:>8.1f} {p['defaultValue']:>8.1f} {p['value']:>8.2f}")
    
    # Quick injection test
    print("\n═══ INJECTION TEST ═══")
    print("Injecting ParamAngleX = 15.0 for 2 seconds...")
    for _ in range(60):
        req = vts.vts_request.requestSetParameterValue(
            parameter="ParamAngleX",
            value=15.0,
            weight=1,
            face_found=True
        )
        await vts.request(req)
        await asyncio.sleep(0.033)
    
    print("Resetting ParamAngleX = 0.0...")
    for _ in range(30):
        req = vts.vts_request.requestSetParameterValue(
            parameter="ParamAngleX",
            value=0.0,
            weight=1,
            face_found=True
        )
        await vts.request(req)
        await asyncio.sleep(0.033)
    
    print("Done! Did the model tilt its head to the right for 2 seconds?")
    
    await vts.close()

if __name__ == "__main__":
    asyncio.run(main())
