import ollama
import io
from PIL import Image

async def describe_image(image_bytes: bytes) -> str:
    """
    Sends raw image bytes to the lightweight Moondream vision model to generate a text description.
    """
    prompt = "Describe this image in exactly one short sentence. Focus on the main subject and vibe. Be extremely concise."
    
    try:
        # Fix transparent backgrounds by compositing over white
        try:
            image = Image.open(io.BytesIO(image_bytes))
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                image = image.convert('RGBA')
                bg = Image.new('RGBA', image.size, (255, 255, 255, 255))
                bg.paste(image, mask=image)
                bg = bg.convert('RGB')
                output = io.BytesIO()
                bg.save(output, format='JPEG')
                image_bytes = output.getvalue()
        except Exception as e:
            print(f"[\033[93mVISION WARN\033[0m] Failed to process transparency: {e}")
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
