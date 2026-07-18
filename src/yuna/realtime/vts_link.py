"""VTube Studio integration: procedural idle animation, audio-reactive
lip-sync/body bounce, and emotion-driven expression changes via [tags].

Runs a 60fps physics loop over the pyvts websocket API. If the websocket
drops mid-session, the loop attempts to reconnect with backoff instead of
silently going still.
"""

from __future__ import annotations

import asyncio
import math
import random
import time

import pyvts

from yuna.core.config import get_config
from yuna.core.logging import get_logger
from yuna.realtime.emotions import EMOTION_PARAMS, is_neutral, resolve_blueprint

log = get_logger("vts")

_RECONNECT_DELAYS = [2.0, 5.0, 10.0]  # then every 10s
_FAILURE_THRESHOLD = 60  # consecutive inject failures (~1s) before reconnecting


class VTSLink:
    def __init__(self, lip_sync_only: bool = False):
        cfg = get_config()
        cfg.paths.data.mkdir(parents=True, exist_ok=True)
        self.plugin_info = {
            "plugin_name": "Yuna AI Controller",
            "developer": "Yuna Project",
            "authentication_token_path": str(cfg.paths.vts_token),
        }
        self.vts = pyvts.vts(plugin_info=self.plugin_info)
        self.connected = False
        self.physics_task: asyncio.Task | None = None
        self.lip_sync_only = lip_sync_only

        # Emotion state — current lerps toward target each frame
        self.target_emotions: dict[str, float] = {}
        self.current_emotions = {p: 0.0 for p in EMOTION_PARAMS}
        self.physics_speed = 1.0

        # Audio reactivity
        self.audio_level = 0.0  # raw RMS from TTS (0..1)
        self._mouth_smooth = 0.0  # EMA-smoothed for lip-sync (fast)
        self._body_smooth = 0.0  # EMA-smoothed for body bounce (slow)

    # ── Connection ──────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        log.info("Connecting to VTube Studio...")
        try:
            await self.vts.connect()
            await self.vts.request_authenticate_token()
            is_auth = await self.vts.request_authenticate()

            if not is_auth:
                log.warning("Auth failed; deleting old token and retrying")
                token_path = get_config().paths.vts_token
                token_path.unlink(missing_ok=True)
                await self.vts.request_authenticate_token()
                is_auth = await self.vts.request_authenticate()

            if not is_auth:
                log.error("Could not authenticate. Click 'Allow' in VTube Studio.")
                self.connected = False
                return False

            self.connected = True
            log.info("Connected and authenticated")
            if self.physics_task is None or self.physics_task.done():
                self.physics_task = asyncio.create_task(self._physics_loop())
            return True

        except ConnectionRefusedError:
            log.error("Connection refused. Is VTube Studio running with 'Start API' enabled?")
        except Exception as e:
            log.error("Could not connect: %s", e)
        self.connected = False
        return False

    async def _reconnect(self) -> bool:
        """Try to re-establish the websocket after a mid-session drop."""
        try:
            await self.vts.close()
        except Exception:
            pass
        self.vts = pyvts.vts(plugin_info=self.plugin_info)
        for delay in _RECONNECT_DELAYS:
            log.info("Reconnecting to VTube Studio in %.0fs...", delay)
            await asyncio.sleep(delay)
            try:
                await self.vts.connect()
                await self.vts.request_authenticate_token()
                if await self.vts.request_authenticate():
                    log.info("Reconnected to VTube Studio")
                    return True
            except Exception as e:
                log.debug("Reconnect attempt failed: %s", e)
        log.error("Could not reconnect to VTube Studio; avatar link disabled")
        return False

    # ── Parameter injection ─────────────────────────────────────────────────

    async def _inject(self, params: dict) -> bool:
        """Send {param: value} to VTS in one batch. Returns success."""
        try:
            req = self.vts.vts_request.requestSetMultiParameterValue(
                parameters=list(params.keys()),
                values=list(params.values()),
                weight=1,
                face_found=True,
                mode="set",
            )
            await self.vts.request(req)
            return True
        except Exception as e:
            log.debug("Inject failed: %s", e)
            return False

    # ── Physics loop ────────────────────────────────────────────────────────

    async def _physics_loop(self):
        log.info("Physics engine online")

        # Blink state
        last_blink = time.time()
        next_blink_delay = random.uniform(3.0, 6.0)
        blink_phase = -1.0  # <0 means not blinking

        # Eye saccade state — smoothly lerped, not snapped
        eye_x_target, eye_y_target = 0.0, 0.0
        eye_x_current, eye_y_current = 0.0, 0.0
        last_saccade = time.time()
        next_saccade_delay = random.uniform(2.0, 4.0)

        # Micro head impulses (random little pops for a bubbly feel)
        impulse_x, impulse_y, impulse_z = 0.0, 0.0, 0.0
        last_impulse = time.time()
        next_impulse_delay = random.uniform(0.8, 2.5)

        t0 = time.time()
        dt = 1.0 / 60.0
        consecutive_failures = 0

        while self.connected:
            t = time.time() - t0
            now = time.time()
            spd = self.physics_speed

            # ── 1. Audio smoothing ────────────────────────────────────────
            self._mouth_smooth = self._mouth_smooth * 0.5 + self.audio_level * 0.5

            if self.lip_sync_only:
                ok = await self._inject({"MouthOpen": min(1.0, self._mouth_smooth * 1.5)})
                consecutive_failures = 0 if ok else consecutive_failures + 1
                if consecutive_failures >= _FAILURE_THRESHOLD:
                    if not await self._reconnect():
                        self.connected = False
                        return
                    consecutive_failures = 0
                await asyncio.sleep(dt)
                continue

            self._body_smooth = self._body_smooth * 0.8 + self.audio_level * 0.2

            # ── 2. Procedural head sway ───────────────────────────────────
            head_x = math.sin(t * 0.6 * spd) * 5.0 + math.sin(t * 1.1 * spd) * 2.5
            head_y = math.sin(t * 0.5 * spd) * 3.5 + math.sin(t * 0.9 * spd) * 2.0
            head_z = math.sin(t * 0.35 * spd) * 4.0 + math.sin(t * 0.8 * spd) * 2.0

            # Audio bounce on head Y
            head_y += self._body_smooth * 10.0

            # ── 2b. Micro head impulses ───────────────────────────────────
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
                blink_phase += dt / 0.12  # full blink in ~120ms
                if blink_phase < 0.35:
                    blink_val = 1.0 - (blink_phase / 0.35)  # close
                elif blink_phase < 0.45:
                    blink_val = 0.0  # brief hold
                elif blink_phase < 1.0:
                    blink_val = (blink_phase - 0.45) / 0.55  # open
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

            eye_x_current += (eye_x_target - eye_x_current) * 0.15
            eye_y_current += (eye_y_target - eye_y_current) * 0.15

            # ── 5. Lerp emotions toward targets ───────────────────────────
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
                "MouthOpen": min(1.0, self._mouth_smooth * 1.5),
                "EyeLeftX": eye_x_current,
                "EyeLeftY": eye_y_current,
                "EyeRightX": eye_x_current,
                "EyeRightY": eye_y_current,
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
            final.setdefault("EyeOpenLeft", blink_val)
            final.setdefault("EyeOpenRight", blink_val)

            # ── 7. Inject (with reconnect on sustained failure) ───────────
            ok = await self._inject(final)
            consecutive_failures = 0 if ok else consecutive_failures + 1
            if consecutive_failures >= _FAILURE_THRESHOLD:
                if not await self._reconnect():
                    self.connected = False
                    return
                consecutive_failures = 0
            await asyncio.sleep(dt)

    # ── Emotion triggers ────────────────────────────────────────────────────

    def set_emotion(self, tag: str | None):
        if not tag:
            return
        if is_neutral(tag):
            self.reset_emotions()
            return
        blueprint = resolve_blueprint(tag)
        if not blueprint:
            return
        log.info("Emotion: %s", tag)
        self.physics_speed = blueprint.get("speed", 1.0)
        self.target_emotions = {p: blueprint.get(p, 0.0) for p in EMOTION_PARAMS}

    def reset_emotions(self):
        """Smoothly return to neutral."""
        self.physics_speed = 1.0
        self.target_emotions = {p: 0.0 for p in EMOTION_PARAMS}

    # ── Cleanup ─────────────────────────────────────────────────────────────

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


# ── Module-level API (used by tts, chat, studio, playback) ──────────────────

_instance: VTSLink | None = None


async def init_vts(lip_sync_only: bool = False) -> bool:
    """Connect to VTube Studio and start the physics engine."""
    global _instance
    _instance = VTSLink(lip_sync_only=lip_sync_only)
    return await _instance.connect()


async def trigger_expression(tag: str | None, turn_off: bool = False):
    """Called per [tag] segment; turn_off resets to neutral."""
    if _instance is None:
        return
    if turn_off:
        _instance.reset_emotions()
    else:
        _instance.set_emotion(tag)


def set_audio_level(vol: float):
    """Called during audio playback with normalized RMS (0..1)."""
    if _instance:
        _instance.audio_level = max(0.0, min(1.0, vol))


async def close():
    global _instance
    if _instance:
        await _instance.close()
        _instance = None
