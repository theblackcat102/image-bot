import base64
import io
import os
import tempfile
import asyncio
import aiofiles
from openai import AsyncOpenAI
from PIL import Image

async def edit_image_with_openai(pillow_image, prompt, output_filename="output.png"):
    """
    Edit an image using OpenAI's image editing API with a custom prompt.
    
    Args:
        pillow_image (PIL.Image): A Pillow image object to edit
        prompt (str): The prompt describing the edits to make
        output_filename (str): Filename for the output image
        
    Returns:
        str: Path to the saved output image
    """
    client = AsyncOpenAI()
    
    # Save the Pillow image to a temporary file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
        temp_filename = temp_file.name
        pillow_image.save(temp_filename, format="PNG")
    
    try:
        # Call OpenAI API with the temporary file
        with open(temp_filename, "rb") as image_file:
            result = await client.images.edit(
                model="gpt-image-1",
                image=image_file,
                prompt=prompt
            )
        
        # Get image data
        image_base64 = result.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)
        
        # Save the image to a file asynchronously
        async with aiofiles.open(output_filename, "wb") as f:
            await f.write(image_bytes)
            
        print(f"File saved to: {output_filename}")
        return output_filename
            
    finally:
        # Clean up the temporary file
        os.unlink(temp_filename)


# Example async usage
async def main():
    # Load a sample image with Pillow
    image = Image.open("cover-8.webp")
    
    # Edit the image with a custom prompt
    result_file = await edit_image_with_openai(
        pillow_image=image,
        prompt="Replace the brand \"Google\" to \"OpenAI\" and the word \"INDIA\" to \"TAIWAN\"",
        output_filename="modified_brand_image.png"
    )
    
    print(f"Edited image saved as: {result_file}")

if __name__ == "__main__":
    asyncio.run(main())