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
        self.vts = pyvts.vts(
            plugin_info={
                "plugin_name": "Yuna AI Controller",
                "developer": "Yuna Project",
                "authentication_token_path": os.path.join(os.path.dirname(__file__), "vts_token.txt")
            }
        )
        self.connected = False
        self._lock = asyncio.Lock()
        
        # Keep track of active states so we don't double-toggle and can crossfade!
        self.active_custom_param = None
        self.active_hotkey = None
        self.param_values = {} # Keep track of exact slider values to prevent jumping!
        
        # We define a list of custom slider parameters to inject into VTube Studio
        self.custom_params = [
            "Yuna_Blush",
            "Yuna_Angry",
            "Yuna_Tears",
            "Yuna_Surprise",
            "Yuna_Darkness", # (For the black face/annoyed shadow)
            "Yuna_StarEyes",
            "Yuna_BlankEyes",
            "Yuna_HeartEyes",
            "Yuna_MoneyEyes"
        ]

    async def connect(self):
        print(f"  [VTS] Connecting to VTube Studio...", flush=True)
        try:
            await self.vts.connect()
            
            # Authenticate or request new token
            await self.vts.read_token()
            if not self.vts.authentic_token:
                print("  [VTS] Requesting authorization... Please click 'Allow' inside VTube Studio!")
                await self.vts.request_authenticate_token()
                await self.vts.write_token()
                
            await self.vts.request_authenticate()
            self.connected = True
            print(f"  [VTS] Connected and authenticated!")
            
            # Inject our custom parameters into VTube Studio
            for param in self.custom_params:
                req = self.vts.vts_request.requestCustomParameter(param, min=0, max=1, default_value=0)
                await self.vts.request(req)
                self.param_values[param] = 0.0 # initialize tracking
                
            print(f"  [VTS] Injected {len(self.custom_params)} custom parameters!")
            return True
        except ConnectionRefusedError:
            print("[VTS Warning] Connection refused. Is VTube Studio running and 'Start API' enabled?")
            self.connected = False
            return False
        except Exception as e:
            print(f"[VTS Error] Could not connect: {e}")
            self.connected = False
            return False

    async def set_parameter(self, param_name, value):
        """Smoothly controls a custom VTube Studio parameter slider (0.0 to 1.0)"""
        if not self.connected:
            return
        async with self._lock:
            try:
                req = self.vts.vts_request.requestSetParameterValue(param_name, value)
                await self.vts.request(req)
                self.param_values[param_name] = value # save current state
            except Exception as e:
                print(f"  [VTS ERROR] Failed to set parameter {param_name}: {e}")

    async def animate_parameter(self, param_name, target_value, duration=0.5):
        """Smoothly animate a parameter to a target value over a duration."""
        if not self.connected:
            return
            
        steps = 15
        sleep_time = duration / steps
        start_value = self.param_values.get(param_name, 0.0) # get exact current value so it never jumps!
        
        for i in range(1, steps + 1):
            current_val = start_value + (target_value - start_value) * (i / steps)
            await self.set_parameter(param_name, current_val)
            await asyncio.sleep(sleep_time)
            
        # KEEP-ALIVE LOOP
        # VTube Studio automatically resets custom API parameters to 0 if they don't receive data fast enough.
        # We must continuously ping the parameter to physically hold the emotion on her face!
        if target_value > 0.0:
            import time
            start_time = time.time()
            while self.active_custom_param == param_name:
                await self.set_parameter(param_name, target_value)
                await asyncio.sleep(0.2) # Ping 5 times a second to prevent VTube Studio from decaying it!
                
                # Auto-decay after 6 seconds so she doesn't hold an emotion too long!
                if time.time() - start_time >= 6.0:
                    if self.active_custom_param == param_name:
                        print(f"\033[96m  [VTS] Auto-fading OUT {param_name} (6s timeout)\033[0m")
                        self.active_custom_param = None
                        asyncio.create_task(self.animate_parameter(param_name, 0.0))
                    break

    async def trigger_tag(self, tag, turn_off=False):
        if not self.connected:
            return
            
        clean_tag = "" if not tag else tag.lower().strip(" .!?-[]")
            
        # If specifically turning off (e.g. end of sentence) or the tag implies neutrality
        if turn_off or not clean_tag or clean_tag in ["neutral", "none", "clear", "pauses slightly", "playful tone", "pauses"]:
            if self.active_custom_param:
                print(f"\033[96m  [VTS] Fading OUT custom parameter: {self.active_custom_param}\033[0m")
                asyncio.create_task(self.animate_parameter(self.active_custom_param, 0.0))
                self.active_custom_param = None
            if self.active_hotkey:
                print(f"\033[95m  [VTS] Untoggling hotkey: {self.active_hotkey}\033[0m")
                async with self._lock:
                    req = self.vts.vts_request.requestTriggerHotKey(self.active_hotkey)
                    await self.vts.request(req)
                self.active_hotkey = None
            return
        
        custom_mapping = {
            "flustered": "Yuna_Blush", "embarrassed": "Yuna_Blush", "shy": "Yuna_Blush", "denial": "Yuna_Blush",
            "laughing awkwardly": "Yuna_Blush", "blushing slightly": "Yuna_Blush", "blush": "Yuna_Blush", "blushing": "Yuna_Blush",
            "angry": "Yuna_Angry", "hmph": "Yuna_Angry", "mad": "Yuna_Angry", "competitive": "Yuna_Angry",
            "frustrated": "Yuna_Angry", "pouting": "Yuna_Angry", "pouts": "Yuna_Angry",
            "sad": "Yuna_Tears", "crying": "Yuna_Tears", "concerned": "Yuna_Tears", "tears": "Yuna_Tears", "worried": "Yuna_Tears",
            "surprised": "Yuna_Surprise", "shock": "Yuna_Surprise", "gasp": "Yuna_Surprise", "panic": "Yuna_Surprise", "shocked": "Yuna_Surprise",
            "scoff": "Yuna_Darkness", "annoyed": "Yuna_Darkness", "smug": "Yuna_Darkness", "tease": "Yuna_Darkness", 
            "smirks": "Yuna_Darkness", "pfft": "Yuna_Darkness", "teasingly": "Yuna_Darkness", "rolling eyes": "Yuna_Darkness",
            
            # The new eye expression mappings!
            "happy": "Yuna_StarEyes", "laugh": "Yuna_StarEyes", "excited": "Yuna_StarEyes",
            "laughs": "Yuna_StarEyes", "laughs slightly": "Yuna_StarEyes", "chuckles": "Yuna_StarEyes", 
            "smiles slightly": "Yuna_StarEyes", "giggle": "Yuna_StarEyes", "smiles": "Yuna_StarEyes", "smiling": "Yuna_StarEyes",
            "grins": "Yuna_StarEyes", "cheerful": "Yuna_StarEyes",
            
            "bored": "Yuna_BlankEyes", "tired": "Yuna_BlankEyes", "rolls eyes": "Yuna_BlankEyes",
            "sigh": "Yuna_BlankEyes", "sighs": "Yuna_BlankEyes", "thinking": "Yuna_BlankEyes", "deadpan": "Yuna_BlankEyes",
            
            "love": "Yuna_HeartEyes", "heart": "Yuna_HeartEyes", "cute": "Yuna_HeartEyes", "adores": "Yuna_HeartEyes",
            "money": "Yuna_MoneyEyes", "rich": "Yuna_MoneyEyes", "greedy": "Yuna_MoneyEyes"
        }
        
        # Custom Parameter handling
        if clean_tag in custom_mapping:
            param = custom_mapping[clean_tag]
            if self.active_custom_param == param:
                return # Already active!
                
            # Crossfade out old param if different
            if self.active_custom_param:
                asyncio.create_task(self.animate_parameter(self.active_custom_param, 0.0))
            # Turn off hotkey if active
            if self.active_hotkey:
                async with self._lock:
                    req = self.vts.vts_request.requestTriggerHotKey(self.active_hotkey)
                    await self.vts.request(req)
                self.active_hotkey = None
                
            self.active_custom_param = param
            print(f"\033[96m  [VTS] Fading IN custom parameter: {param} (from tag {clean_tag})\033[0m")
            
            # Cap intensities so they aren't overpowering
            target_value = 1.0
            if param == "Yuna_Darkness":
                target_value = 0.6
            elif param in ["Yuna_BlankEyes", "Yuna_StarEyes"]:
                target_value = 0.5
                
            asyncio.create_task(self.animate_parameter(param, target_value))
            return

        # Hotkey handling
        hotkey_id = TAG_TO_HOTKEY.get(clean_tag)
        if not hotkey_id:
            print(f"\033[90m  [VTS] Unknown tag '{clean_tag}', ignoring.\033[0m")
            return
            
        if self.active_hotkey == hotkey_id:
            return # Already active!
            
        # Clear custom param if active
        if self.active_custom_param:
            asyncio.create_task(self.animate_parameter(self.active_custom_param, 0.0))
            self.active_custom_param = None
        # Untoggle old hotkey
        if self.active_hotkey:
            async with self._lock:
                req = self.vts.vts_request.requestTriggerHotKey(self.active_hotkey)
                await self.vts.request(req)
            
        self.active_hotkey = hotkey_id
        print(f"\033[95m  [VTS] Triggering hotkey expression: {hotkey_id} (from tag {clean_tag})\033[0m")
        try:
            async with self._lock:
                req = self.vts.vts_request.requestTriggerHotKey(hotkey_id)
                await self.vts.request(req)
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

async def trigger_expression(tag, turn_off=False):
    """Trigger a hotkey or animate a parameter based on a parsed text tag"""
    if _vts_instance:
        await _vts_instance.trigger_tag(tag, turn_off=turn_off)
