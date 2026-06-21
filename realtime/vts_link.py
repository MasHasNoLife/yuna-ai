"""
vts_link.py — VTube Studio integration for Yuna.

Drives the Hiyori model with:
  - Procedural idle animation (breathing, head sway, blinking, eye saccades)
  - Audio-reactive lip-sync and body bounce
  - Emotion-driven expression changes via [tags]

Uses the pyvts high-level API exclusively.
"""
import asyncio
import os
import time
import math
import random
import pyvts

# ── Config ────────────────────────────────────────────────────────────────────

PHYSICS_FPS = 30
PHYSICS_DT  = 1.0 / PHYSICS_FPS

plugin_info = {
    "plugin_name": "Yuna AI Controller",
    "developer": "Yuna Project",
    "authentication_token_path": os.path.join(os.path.dirname(os.path.abspath(__file__)), "vts_token.txt")
}

# ── Verified Default Parameter Names (from vts_diag.py) ──────────────────────
# These are the EXACT names VTube Studio reports for the Hiyori model.
# FaceAngleX/Y/Z  (-30..30)   — Head tilt
# MouthOpen        (0..1)     — Lip sync
# MouthSmile       (0..1)     — Smile
# EyeOpenLeft/Right (0..1)    — Eye openness
# EyeLeftX/Y       (-1..1)    — Eyeball position
# EyeRightX/Y      (-1..1)    — Eyeball position
# BrowLeftY/RightY  (0..1)    — Eyebrow height
# FaceAngry         (0..1)    — Angry expression
# CheekPuff         (0..1)    — Cheek puff

# ── Emotion Blueprints ───────────────────────────────────────────────────────
# Each tag maps to target values for Live2D parameters + a physics speed modifier.
# Parameters not listed default to 0 (neutral).

EMOTION_BLUEPRINTS = {
    # Happy / Laughing
    "happy":           {"speed": 1.5, "MouthSmile": 1.0},
    "laugh":           {"speed": 2.0, "MouthSmile": 1.0, "EyeOpenLeft": 0.2, "EyeOpenRight": 0.2},
    "giggle":          {"speed": 1.8, "MouthSmile": 0.9, "EyeOpenLeft": 0.5, "EyeOpenRight": 0.5},
    "excited":         {"speed": 2.5, "MouthSmile": 1.0, "BrowLeftY": 0.9, "BrowRightY": 0.9},
    "chuckles":        {"speed": 1.3, "MouthSmile": 0.8},
    "smiles slightly": {"speed": 1.0, "MouthSmile": 0.5},

    # Sad / Crying
    "sad":             {"speed": 0.4, "MouthSmile": 0.0, "FaceAngleZ": -10.0, "BrowLeftY": 0.5, "BrowRightY": 0.5},
    "crying":          {"speed": 0.3, "MouthSmile": 0.0, "EyeOpenLeft": 0.3, "EyeOpenRight": 0.3, "FaceAngleZ": -15.0},
    "concerned":       {"speed": 0.7, "BrowLeftY": 0.6, "BrowRightY": 0.6},

    # Angry / Annoyed / Pouty
    "angry":           {"speed": 1.8, "FaceAngry": 1.0, "BrowLeftY": 0.1, "BrowRightY": 0.1},
    "hmph":            {"speed": 1.3, "FaceAngleX": 12.0, "FaceAngry": 0.7},
    "pouty":           {"speed": 1.2, "FaceAngleX": 8.0, "FaceAngry": 0.3, "CheekPuff": 1.0},
    "mad":             {"speed": 2.0, "FaceAngry": 1.0, "BrowLeftY": 0.0, "BrowRightY": 0.0},
    "scoff":           {"speed": 1.3, "FaceAngry": 0.6, "EyeOpenLeft": 0.4, "EyeOpenRight": 0.4},
    "annoyed":         {"speed": 1.2, "FaceAngry": 0.5},
    "smug":            {"speed": 1.2, "MouthSmile": 1.0, "EyeOpenLeft": 0.5, "EyeOpenRight": 0.5},

    # Surprised / Shocked
    "surprised":       {"speed": 1.2, "EyeOpenLeft": 1.0, "EyeOpenRight": 1.0, "BrowLeftY": 0.9, "BrowRightY": 0.9},
    "shock":           {"speed": 1.5, "EyeOpenLeft": 1.0, "EyeOpenRight": 1.0, "BrowLeftY": 1.0, "BrowRightY": 1.0},
    "gasp":            {"speed": 1.5, "EyeOpenLeft": 1.0, "EyeOpenRight": 1.0, "MouthOpen": 0.6},

    # Confused / Thinking
    "confused":        {"speed": 0.8, "BrowLeftY": 0.6, "BrowRightY": 0.3, "FaceAngleZ": 5.0},
    "thinking":        {"speed": 0.5, "EyeOpenLeft": 0.7, "EyeOpenRight": 0.7, "FaceAngleZ": 6.0, "EyeLeftX": 0.4, "EyeRightX": 0.4, "EyeLeftY": 0.3, "EyeRightY": 0.3},
    "curious":         {"speed": 1.0, "FaceAngleZ": 5.0, "BrowLeftY": 0.7, "BrowRightY": 0.7},

    # Flustered / Shy
    "flustered":       {"speed": 2.0, "FaceAngleY": -5.0, "MouthSmile": 0.3},
    "embarrassed":     {"speed": 1.5, "FaceAngleY": -8.0, "MouthSmile": 0.2},
    "shy":             {"speed": 1.0, "FaceAngleY": -8.0, "MouthSmile": 0.3, "EyeOpenLeft": 0.6, "EyeOpenRight": 0.6},
    "tease":           {"speed": 1.2, "MouthSmile": 0.9, "EyeOpenLeft": 0.7, "EyeOpenRight": 0.7},

    # Bored / Tired / Relieved
    "bored":           {"speed": 0.5, "EyeOpenLeft": 0.4, "EyeOpenRight": 0.4},
    "tired":           {"speed": 0.3, "EyeOpenLeft": 0.3, "EyeOpenRight": 0.3},
    "sigh":            {"speed": 0.8, "EyeOpenLeft": 0.3, "EyeOpenRight": 0.3, "FaceAngleY": -3.0},
    "relieved":        {"speed": 0.6, "MouthSmile": 0.4, "EyeOpenLeft": 0.6, "EyeOpenRight": 0.6, "FaceAngleY": -2.0},
}

# All parameter names that emotions can control (for resetting to neutral)
EMOTION_PARAMS = set()
for bp in EMOTION_BLUEPRINTS.values():
    for k in bp:
        if k != "speed":
            EMOTION_PARAMS.add(k)


class VTSLink:
    def __init__(self):
        self.vts = pyvts.vts(plugin_info=plugin_info)
        self.connected = False
        self.physics_task = None

        # Emotion state — we lerp current toward target each frame
        self.target_emotions = {}   # tag -> {param: value}
        self.current_emotions = {p: 0.0 for p in EMOTION_PARAMS}
        self.physics_speed = 1.0

        # Audio reactivity
        self.audio_level = 0.0      # raw RMS from TTS (0..1)
        self._mouth_smooth = 0.0    # EMA-smoothed for lip-sync (fast)
        self._body_smooth  = 0.0    # EMA-smoothed for body bounce (slow)

    # ── Connection ────────────────────────────────────────────────────────────

    async def connect(self):
        print("  [VTS] Connecting to VTube Studio...", flush=True)
        try:
            await self.vts.connect()
            await self.vts.request_authenticate_token()
            is_auth = await self.vts.request_authenticate()

            if not is_auth:
                print("  [VTS] Auth failed. Deleting old token and retrying...")
                token_path = plugin_info["authentication_token_path"]
                if os.path.exists(token_path):
                    os.remove(token_path)
                await self.vts.request_authenticate_token()
                is_auth = await self.vts.request_authenticate()

            if not is_auth:
                print("[VTS Error] Could not authenticate. Click 'Allow' in VTube Studio.")
                self.connected = False
                return False

            self.connected = True
            print("  [VTS] Connected and authenticated!", flush=True)

            # Start the physics engine
            self.physics_task = asyncio.create_task(self._physics_loop())
            return True

        except ConnectionRefusedError:
            print("[VTS Warning] Connection refused. Is VTube Studio running with 'Start API' enabled?")
            self.connected = False
            return False
        except Exception as e:
            print(f"[VTS Error] Could not connect: {e}")
            self.connected = False
            return False

    # ── Parameter Injection ───────────────────────────────────────────────────

    async def _inject(self, params: dict):
        """Send a dict of {param_name: value} to VTS in a single batch."""
        if not self.connected:
            return
        try:
            names = list(params.keys())
            values = list(params.values())
            req = self.vts.vts_request.requestSetMultiParameterValue(
                parameters=names,
                values=values,
                weight=1,
                face_found=True,
                mode="set"
            )
            await self.vts.request(req)
        except Exception:
            pass  # Swallow transient websocket errors

    # ── Physics Loop ──────────────────────────────────────────────────────────

    async def _physics_loop(self):
        print("\033[92m  [VTS] Physics Engine Online!\033[0m", flush=True)

        # Blink state
        last_blink = time.time()
        next_blink_delay = random.uniform(3.0, 6.0)
        blink_phase = -1.0  # <0 means not blinking

        # Eye saccade state — smoothly lerped, not snapped
        eye_x_target, eye_y_target = 0.0, 0.0
        eye_x_current, eye_y_current = 0.0, 0.0
        last_saccade = time.time()
        next_saccade_delay = random.uniform(2.0, 4.0)

        # Micro head impulse state (random little pops for bubbly feel)
        impulse_x, impulse_y, impulse_z = 0.0, 0.0, 0.0
        last_impulse = time.time()
        next_impulse_delay = random.uniform(0.8, 2.5)

        t0 = time.time()
        dt = 1.0 / 60.0  # 60fps for smoother animation

        while self.connected:
            t = time.time() - t0
            now = time.time()
            spd = self.physics_speed

            # ── 1. Audio smoothing ────────────────────────────────────────
            self._mouth_smooth = self._mouth_smooth * 0.5 + self.audio_level * 0.5
            self._body_smooth  = self._body_smooth  * 0.8 + self.audio_level * 0.2

            # ── 2. Procedural head sway ───────────────────────────────────
            head_x = math.sin(t * 0.6 * spd) * 5.0 + math.sin(t * 1.1 * spd) * 2.5
            head_y = math.sin(t * 0.5 * spd) * 3.5 + math.sin(t * 0.9 * spd) * 2.0
            head_z = math.sin(t * 0.35 * spd) * 4.0 + math.sin(t * 0.8 * spd) * 2.0

            # Audio bounce on head Y
            head_y += self._body_smooth * 10.0

            # ── 2b. Micro head impulses (bubbly energy) ───────────────────
            # Random small pops that decay quickly — makes her feel alive
            if now - last_impulse > next_impulse_delay:
                impulse_x = random.uniform(-3.0, 3.0)
                impulse_y = random.uniform(-2.0, 2.0)
                impulse_z = random.uniform(-2.0, 2.0)
                last_impulse = now
                next_impulse_delay = random.uniform(0.8, 2.5)

            # Decay impulses quickly (spring back)
            impulse_x *= 0.92
            impulse_y *= 0.92
            impulse_z *= 0.92

            head_x += impulse_x
            head_y += impulse_y
            head_z += impulse_z

            # ── 3. Blinking ───────────────────────────────────────────────
            blink_val = 1.0  # 1 = eyes open
            if blink_phase < 0:
                if now - last_blink > next_blink_delay:
                    blink_phase = 0.0
            else:
                blink_phase += dt / 0.12  # Full blink in 120ms — visible but quick
                if blink_phase < 0.35:
                    blink_val = 1.0 - (blink_phase / 0.35)   # Close
                elif blink_phase < 0.45:
                    blink_val = 0.0                            # Brief hold
                elif blink_phase < 1.0:
                    blink_val = (blink_phase - 0.45) / 0.55   # Open
                else:
                    blink_phase = -1.0
                    last_blink = now
                    next_blink_delay = random.uniform(3.0, 6.0)
                    blink_val = 1.0

            # ── 4. Eye saccades (smooth lerp, not instant snap) ───────────
            if now - last_saccade > next_saccade_delay:
                eye_x_target = random.uniform(-0.4, 0.4)
                eye_y_target = random.uniform(-0.2, 0.2)
                last_saccade = now
                next_saccade_delay = random.uniform(2.0, 4.0)

            # Smooth lerp toward target (no more twitching!)
            eye_x_current += (eye_x_target - eye_x_current) * 0.15
            eye_y_current += (eye_y_target - eye_y_current) * 0.15

            # ── 5. Lerp emotions toward targets ──────────────────────────
            lerp_speed = 0.12
            for param in EMOTION_PARAMS:
                target = self.target_emotions.get(param, 0.0)
                current = self.current_emotions[param]
                self.current_emotions[param] = current + (target - current) * lerp_speed

            # ── 6. Build final parameter dict ─────────────────────────────
            em = self.current_emotions

            final = {
                "FaceAngleX": head_x,
                "FaceAngleY": head_y,
                "FaceAngleZ": head_z,
                "MouthOpen":  min(1.0, self._mouth_smooth * 1.5),
                "EyeLeftX":   eye_x_current,
                "EyeLeftY":   eye_y_current,
                "EyeRightX":  eye_x_current,
                "EyeRightY":  eye_y_current,
            }

            # Layer emotion overrides
            for param, val in em.items():
                if abs(val) < 0.001:
                    continue

                if param in ("FaceAngleX", "FaceAngleY", "FaceAngleZ"):
                    final[param] = final.get(param, 0.0) + val
                elif param in ("EyeOpenLeft", "EyeOpenRight"):
                    final[param] = min(blink_val, val)
                elif param == "MouthOpen":
                    final[param] = max(final.get(param, 0.0), val)
                else:
                    final[param] = val

            # Eye openness: if emotions didn't set it, use blink value
            if "EyeOpenLeft" not in final:
                final["EyeOpenLeft"] = blink_val
            if "EyeOpenRight" not in final:
                final["EyeOpenRight"] = blink_val

            # ── 7. Inject ─────────────────────────────────────────────────
            await self._inject(final)
            await asyncio.sleep(dt)

    # ── Emotion Triggers ──────────────────────────────────────────────────────

    def set_emotion(self, tag):
        """Set the target emotion from a text tag."""
        if not tag:
            return

        clean = tag.lower().strip(" .!?-[]")

        if clean in ("neutral", "none", "clear", "pauses slightly", "pauses", "playful tone"):
            self._reset_emotions()
            return

        blueprint = EMOTION_BLUEPRINTS.get(clean)
        if not blueprint:
            # Fuzzy match
            for name, bp in EMOTION_BLUEPRINTS.items():
                if name in clean:
                    blueprint = bp
                    break

        if not blueprint:
            return

        print(f"\033[95m  [VTS] Emotion: {clean}\033[0m", flush=True)

        # Set physics speed
        self.physics_speed = blueprint.get("speed", 1.0)

        # Set targets, reset anything not in this blueprint
        new_targets = {}
        for param in EMOTION_PARAMS:
            new_targets[param] = blueprint.get(param, 0.0)
        self.target_emotions = new_targets

    def _reset_emotions(self):
        """Smoothly return to neutral."""
        self.physics_speed = 1.0
        self.target_emotions = {p: 0.0 for p in EMOTION_PARAMS}

    # ── Cleanup ───────────────────────────────────────────────────────────────

    async def close(self):
        self.connected = False
        if self.physics_task:
            self.physics_task.cancel()
            try:
                await self.physics_task
            except asyncio.CancelledError:
                pass
        try:
            await self.vts.close()
        except Exception:
            pass


# ── Module-level API (called by tts.py and yuna.py) ──────────────────────────

_instance: VTSLink | None = None

async def init_vts():
    """Connect to VTube Studio and start the physics engine."""
    global _instance
    _instance = VTSLink()
    ok = await _instance.connect()
    if ok:
        print("\033[92m[VTS] Successfully connected to VTube Studio!\033[0m")
    return ok

async def trigger_expression(tag, turn_off=False):
    """Called by tts.py for each [tag] segment."""
    if _instance is None:
        return
    if turn_off:
        _instance._reset_emotions()
    else:
        _instance.set_emotion(tag)

def set_audio_level(vol: float):
    """Called by tts.py during audio playback."""
    if _instance:
        _instance.audio_level = max(0.0, min(1.0, vol))
