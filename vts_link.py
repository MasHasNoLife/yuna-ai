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
# Map Yuna's prompt tags to the exact UUIDs of the IceGirl Live2D model!
TAG_TO_HOTKEY = {
    # Blush / Flustered (脸红.exp3.json)
    "flustered": "810f894e9bd5475299e2a0333b07696d", 
    "embarrassed": "810f894e9bd5475299e2a0333b07696d",
    "shy": "810f894e9bd5475299e2a0333b07696d",
    "denial": "810f894e9bd5475299e2a0333b07696d",
    
    # Angry (生气.exp3.json)
    "angry": "324d02ce8d734c1ab810d9a13a124590",
    "hmph": "324d02ce8d734c1ab810d9a13a124590",
    "mad": "324d02ce8d734c1ab810d9a13a124590",
    "competitive": "324d02ce8d734c1ab810d9a13a124590",
    
    # Black Face / Annoyed (脸黑.exp3.json)
    "scoff": "0edafccc7efe41df8902903f70610753",
    "annoyed": "0edafccc7efe41df8902903f70610753",
    "smug": "0edafccc7efe41df8902903f70610753",
    "tease": "0edafccc7efe41df8902903f70610753",
    "smirks": "0edafccc7efe41df8902903f70610753",
    "pfft": "0edafccc7efe41df8902903f70610753",
    "teasingly": "0edafccc7efe41df8902903f70610753",
    
    # Surprise / Shock (惊讶.exp3.json)
    "surprised": "1cd021096a5945188ed0c0749e3d7f87",
    "shock": "1cd021096a5945188ed0c0749e3d7f87",
    "gasp": "1cd021096a5945188ed0c0749e3d7f87",
    "panic": "1cd021096a5945188ed0c0749e3d7f87",
    
    # Confused (疑惑.exp3.json)
    "confused": "56b92bacd7c941c8863e7148904ecf36",
    "thinking": "56b92bacd7c941c8863e7148904ecf36",
    "curious": "56b92bacd7c941c8863e7148904ecf36",
    "thoughtfully": "56b92bacd7c941c8863e7148904ecf36",
    "shrugs": "56b92bacd7c941c8863e7148904ecf36",
    
    # Tears / Sad (流泪.exp3.json)
    "sad": "d1a98e5097ce49269bdc6acd352b01ad",
    "crying": "d1a98e5097ce49269bdc6acd352b01ad",
    "concerned": "d1a98e5097ce49269bdc6acd352b01ad",
    
    # Star Eyes (星星眼.exp3.json)
    "happy": "73ec28a4b861488e882374ff7585c219",
    "laugh": "73ec28a4b861488e882374ff7585c219",
    "excited": "73ec28a4b861488e882374ff7585c219",
    "laughs": "73ec28a4b861488e882374ff7585c219",
    "laughs slightly": "73ec28a4b861488e882374ff7585c219",
    "chuckles": "73ec28a4b861488e882374ff7585c219",
    "smiles slightly": "73ec28a4b861488e882374ff7585c219",
    
    # Eyeroll / Blankly (白眼.exp3.json)
    "bored": "0d933e11856c4d93ac3c2b245c130cf1",
    "tired": "0d933e11856c4d93ac3c2b245c130cf1",
    "rolls eyes": "0d933e11856c4d93ac3c2b245c130cf1",
    "sigh": "0d933e11856c4d93ac3c2b245c130cf1",
    "sighs": "0d933e11856c4d93ac3c2b245c130cf1",
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
