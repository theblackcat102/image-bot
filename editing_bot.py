import os
import json
import discord
import aiohttp
import asyncio
import aiofiles
import io
from datetime import datetime
from PIL import Image
from discord import app_commands
from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
from oai_gpt import edit_image_with_openai
from gemini_editor import edit_image_with_gemini

# Define intents
intents = discord.Intents.default()
intents.message_content = True

# Create a client instance
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Ensure logging directory exists
os.makedirs("logging", exist_ok=True)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    await tree.sync()  # Sync commands with Discord

async def save_conversation(thread_id, author, content):
    """Save conversation to a JSONL file"""
    thread_dir = f"logging/{thread_id}"
    os.makedirs(thread_dir, exist_ok=True)

    log_file = f"{thread_dir}/conversations.jsonl"
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "author": author,
        "content": content
    }

    async with aiofiles.open(log_file, "a") as f:
        await f.write(json.dumps(log_entry) + "\n")

@tree.command(name="ping", description="Replies with Pong!")
async def ping(interaction):
    await interaction.response.send_message("Pong!")


async def save_conversation(thread_id, author, content, message_id=None):
    """Save conversation to a JSONL file"""
    thread_dir = f"logging/{thread_id}"
    os.makedirs(thread_dir, exist_ok=True)

    log_file = f"{thread_dir}/conversations.jsonl"
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "author": author,
        "content": content,
        "message_id": message_id
    }

    async with aiofiles.open(log_file, "a") as f:
        await f.write(json.dumps(log_entry) + "\n")


async def process_image(message, channel, prompt, thread_id=None):
    """Process an image with both OpenAI and Gemini"""
    if thread_id is None:
        thread_id = channel.id

    thread_dir = f"logging/{thread_id}"
    os.makedirs(thread_dir, exist_ok=True)

    for attachment in message.attachments:
        if attachment.content_type.startswith("image/"):
            # Get the image
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as resp:
                    if resp.status == 200:
                        img_data = await resp.read()

                        # Save original image with timestamp
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        original_image_path = f"{thread_dir}/original_image_{timestamp}.png"
                        async with aiofiles.open(original_image_path, "wb") as f:
                            await f.write(img_data)

                        img = Image.open(io.BytesIO(img_data))

                        # Define output filenames
                        openai_output = f"{thread_dir}/edited_image_openai_{timestamp}.png"
                        gemini_output = f"{thread_dir}/edited_image_gemini_{timestamp}"

                        # Process with OpenAI (already async)
                        openai_task = asyncio.create_task(
                            edit_image_with_openai(img, prompt, openai_output)
                        )

                        # Process with Gemini (needs to be run in executor)
                        async def run_gemini():
                            loop = asyncio.get_event_loop()
                            return await loop.run_in_executor(
                                None,
                                lambda: edit_image_with_gemini(img, prompt, gemini_output)
                            )

                        gemini_task = asyncio.create_task(run_gemini())
                        try:
                            gemini_result = await asyncio.wait_for(gemini_task, timeout=60)
                            await channel.send("Gemini processing complete!")
                            file_msg = await channel.send(file=discord.File(gemini_result))
                            await save_conversation(thread_id, 'gemini-editing', gemini_output, file_msg.id)
                            # await save_conversation(thread_id, 'gemini-edting', gemini_output)
                        except Exception as e:
                            error_msg = await channel.send(f"Error with Gemini processing: {str(e)}")
                            await save_conversation(thread_id, 'gemini-error', str(e), error_msg.id)

                        # Wait for both tasks to complete
                        try:
                            openai_result = await asyncio.wait_for(openai_task, timeout=300)
                            await channel.send("OpenAI processing complete!")
                            file_msg = await channel.send(file=discord.File(openai_result))
                            await save_conversation(thread_id, 'openai-editing', openai_output, file_msg.id)
                        except Exception as e:
                            error_msg = await channel.send(f"Error with OpenAI processing: {str(e)}")
                            await save_conversation(thread_id, 'openai-error', str(e), error_msg.id)


                        # Log bot responses
                        complete_msg = await channel.send("Image processing complete")
                        await save_conversation(thread_id, client.user.name, "Image processing complete", complete_msg.id)

                    else:
                        await channel.send(f"Failed to fetch image: HTTP {resp.status}")

            # Only process the first image attachment
            return True

    await channel.send("No valid image attachments found.")
    return False

@client.event
async def on_message(message):
    # Skip messages from bots
    if message.author.bot:
        return

    # Check if the message is in a thread
    if isinstance(message.channel, discord.Thread):
        thread_id = message.channel.id
        # Handle edit command in thread
        if message.content.lower().startswith("!edit") and message.attachments:
            prompt = message.content[5:].strip()

            # Log the request
            await save_conversation(thread_id, message.author.name, message.content, message.id)
            processing_msg = await message.channel.send("Processing your image request...")
            await save_conversation(thread_id, client.user.name, "Processing your image request...", processing_msg.id)

            # Process the image
            await process_image(message, message.channel, prompt, thread_id)
        else:
            await save_conversation(thread_id, message.author.name, message.content, message.id)

    # Handle main channel edit command
    elif message.content.lower().startswith("!edit") and message.attachments:
        prompt = message.content[5:].strip()

        if not prompt:
            response_msg = await message.channel.send("Please provide editing instructions after the !edit command.")
            await save_conversation(message.channel.id, client.user.name, "Please provide editing instructions after the !edit command.", response_msg.id)
            return

        # Create a thread for this request
        thread = await message.create_thread(
            name=f"Image Edit: {prompt[:20]}{'...' if len(prompt) > 20 else ''}",
            auto_archive_duration=60
        )

        thread_id = thread.id

        # Log the request
        await save_conversation(thread_id, message.author.name, message.content, message.id)

        # Send initial response
        initial_msg = await thread.send("Processing your image with both OpenAI and Gemini editors. This may take a moment...")
        await save_conversation(thread_id, client.user.name, "Processing your image with both OpenAI and Gemini editors. This may take a moment...", initial_msg.id)

        # Process the image
        await process_image(message, thread, prompt, thread_id)


# Run the bot
client.run(TOKEN)

# Step 4: Run your bot
# python bot.py