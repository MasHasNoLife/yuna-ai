"""Image understanding for the Discord bot via a lightweight local vision model."""

from __future__ import annotations

import io

from PIL import Image

from yuna.core.config import get_config
from yuna.core.logging import get_logger

log = get_logger("discord.vision")

PROMPT = (
    "Describe this image in detail. Focus on the main subject, any readable text, "
    "the people, and the overall mood or vibe. Be concise but descriptive."
)


def _to_jpeg(image_bytes: bytes) -> bytes:
    """Normalize any image (WebP/GIF/PNG with alpha) to JPEG for Ollama."""
    image = Image.open(io.BytesIO(image_bytes))
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        image = image.convert("RGBA")
        bg = Image.new("RGBA", image.size, (255, 255, 255, 255))
        bg.paste(image, mask=image)
        image = bg.convert("RGB")
    else:
        image = image.convert("RGB")
    output = io.BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


async def describe_image(image_bytes: bytes) -> str:
    import ollama

    cfg = get_config()
    try:
        try:
            image_bytes = _to_jpeg(image_bytes)
        except Exception as e:
            log.warning("Image conversion failed, sending raw bytes: %s", e)

        client = ollama.AsyncClient(host=cfg.endpoints.ollama_url)
        response = await client.generate(
            model=cfg.models.vision_discord, prompt=PROMPT, images=[image_bytes]
        )
        description = response.get("response", "").strip()
        return description or "The image was processed but no description was generated."
    except Exception:
        log.exception("Failed to analyze image")
        return "An image was attached, but Yuna was unable to see it due to an error."
