# To run this code you need to install the following dependencies:
# pip install google-genai pillow

import base64
import mimetypes
import os
import tempfile
from google import genai
from google.genai import types
from PIL import Image


def save_binary_file(file_name, data):
    f = open(file_name, "wb")
    f.write(data)
    f.close()
    print(f"File saved to: {file_name}")
    return file_name


def edit_image_with_gemini(pillow_image, prompt, output_filename="edited_image"):
    """
    Edit an image using Gemini model with a custom prompt.
    
    Args:
        pillow_image (PIL.Image): A Pillow image object to edit
        prompt (str): The prompt describing the edits to make
        output_filename (str): Base filename for the output (without extension)
        
    Returns:
        str: Path to the saved output image
    """
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )
    
    # Save the Pillow image to a temporary file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
        temp_filename = temp_file.name
        pillow_image.save(temp_filename, format="PNG")
    
    try:
        # Upload the temporary file
        uploaded_file = client.files.upload(file=temp_filename)        
        model = "gemini-2.0-flash-exp-image-generation"
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_uri(
                        file_uri=uploaded_file.uri,
                        mime_type=uploaded_file.mime_type,
                    ),
                    types.Part.from_text(text=prompt),
                ],
            )
        ]
        
        generate_content_config = types.GenerateContentConfig(
            response_modalities=[
                "image",
                "text",
            ],
            response_mime_type="text/plain",
        )
        
        final_filename = None
        
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if (
                chunk.candidates is None
                or chunk.candidates[0].content is None
                or chunk.candidates[0].content.parts is None
            ):
                continue
                
            if chunk.candidates[0].content.parts[0].inline_data:
                inline_data = chunk.candidates[0].content.parts[0].inline_data
                data_buffer = inline_data.data
                file_extension = mimetypes.guess_extension(inline_data.mime_type) or ".png"
                final_filename = save_binary_file(f"{output_filename}{file_extension}", data_buffer)
            else:
                print(chunk.text)
                
    finally:
        # Clean up the temporary file
        os.unlink(temp_filename)
    
    return final_filename

if __name__ == "__main__":
    # Load a sample image with Pillow
    image = Image.open("cover-8.webp")

    # Edit the image with a custom prompt
    result_file = generate(
        pillow_image=image,
        prompt="Replace the brand \"Google\" to \"OpenAI\" and the word \"INDIA\" to \"TAIWAN\"",
        output_filename="modified_brand_image"
    )

    print(f"Edited image saved as: {result_file}")