import asyncio
import os
import pyvts

# ── Config ────────────────────────────────────────────────────────────────────

plugin_info = {
    "plugin_name": "Yuna AI Controller",
    "developer": "Yuna Project",
    "authentication_token_path": os.path.join(os.path.dirname(__file__), "vts_token.txt")
}

# ── Emotion Mapping ───────────────────────────────────────────────────────────
# Map Yuna's prompt tags (e.g. [flustered]) to your actual VTube Studio Hotkey IDs
# You will need to change the right side of this dictionary to match your VTS setup!
TAG_TO_HOTKEY = {
    # All animations temporarily disabled to prevent lip-sync interruption!
    "flustered": "", 
    "scoff": "",      
    "scoffs": "",     
    "hmph": "",       
    "hmphs": "",      
    "smug": "",       
    "smirks": "",     
    "denial": "",     
    "happy": "",      
    "laugh": "",      
    "giggle": "",     
    "sigh": "",       
    "sighs": "",      
    "confused": "",   
    "sarcastically": "", 
    "gives a dismissive look": "", 
}

class VTSLink:
    def __init__(self):
        self.vts = pyvts.vts(plugin_info=plugin_info)
        self.connected = False

    async def connect(self):
        try:
            await self.vts.connect()
            self.connected = True
            
            # Authenticate or request new token
            await self.vts.read_token()
            if not self.vts.authentic_token:
                print("[VTS] Requesting authorization... Please click 'Allow' inside VTube Studio!")
                await self.vts.request_authenticate_token()
                await self.vts.write_token()
                
            await self.vts.request_authenticate()
            return True
        except ConnectionRefusedError:
            print("[VTS Warning] Connection refused. Is VTube Studio running and 'Start API' enabled?")
            self.connected = False
            return False
        except Exception as e:
            print(f"[VTS Error] Could not connect: {e}")
            self.connected = False
            return False

    async def trigger_tag(self, tag):
        if not self.connected:
            return
            
        # Clean the tag (remove brackets, periods, spaces)
        clean_tag = tag.lower().strip(" .!?-[]")
        hotkey_id = TAG_TO_HOTKEY.get(clean_tag)
        
        if not hotkey_id:
            print(f"\033[90m  [VTS] Unknown tag '{clean_tag}', ignoring.\033[0m")
            return
            
        print(f"\033[95m  [VTS] Triggering expression: {hotkey_id} (from tag {clean_tag})\033[0m")
        try:
            request = self.vts.vts_request.requestTriggerHotKey(hotkey_id)
            await self.vts.request(request)
        except Exception as e:
            print(f"[VTS Error] Failed to trigger hotkey: {e}")

    async def close(self):
        if self.connected:
            await self.vts.close()

# Global instance
_vts_instance = None

async def init_vts():
    """Initialize connection to VTube Studio"""
    global _vts_instance
    _vts_instance = VTSLink()
    success = await _vts_instance.connect()
    if success:
        print("\033[92m[VTS] Successfully connected to VTube Studio!\033[0m")
    return success

async def trigger_expression(tag):
    """Trigger a hotkey based on a parsed text tag"""
    if _vts_instance:
        await _vts_instance.trigger_tag(tag)
