import ollama
import io
from PIL import Image

async def describe_image(image_bytes: bytes) -> str:
    """
    Sends raw image bytes to the lightweight Moondream vision model to generate a text description.
    """
    prompt = "Describe this image in detail. Focus on the main subject, any readable text, the people, and the overall mood or vibe. Be concise but descriptive."
    
    try:
        # Force convert ALL images to JPEG to avoid Ollama WebP/GIF compatibility errors
        try:
            image = Image.open(io.BytesIO(image_bytes))
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                image = image.convert('RGBA')
                bg = Image.new('RGBA', image.size, (255, 255, 255, 255))
                bg.paste(image, mask=image)
                image = bg.convert('RGB')
            else:
                image = image.convert('RGB')
                
            output = io.BytesIO()
            image.save(output, format='JPEG')
            image_bytes = output.getvalue()
        except Exception as e:
            print(f"[\033[93mVISION WARN\033[0m] Failed to process image conversion: {e}")
            pass

        client = ollama.AsyncClient()
        response = await client.generate(
            model="minicpm-v",
            prompt=prompt,
            images=[image_bytes]
        )
        description = response.get('response', '').strip()
        if not description:
            return "Moondream processed the image but couldn't generate a description."
        return description
    except Exception as e:
        print(f"\033[91m[VISION ERROR]\033[0m Failed to analyze image: {e}")
        return "An image was attached, but Yuna was unable to see it due to an error."
