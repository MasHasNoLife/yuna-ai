import asyncio
import ollama
from PIL import Image
import io

async def test():
    # create a dummy webp image
    img = Image.new('RGB', (100, 100), color = 'red')
    output = io.BytesIO()
    img.save(output, format='WEBP')
    image_bytes = output.getvalue()

    try:
        client = ollama.AsyncClient()
        response = await client.generate(
            model="minicpm-v",
            prompt="Describe this",
            images=[image_bytes]
        )
        print(response.get('response', ''))
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())
