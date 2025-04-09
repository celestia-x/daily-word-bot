import requests
import random
import os
import json
import time
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from bottle import Bottle, request, run
import threading

# ========= Configuration =========
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7673729627:AAEsCmoWYzrqUPkVkY1w8hQddOtWP8mc0Fw")
API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/"
DICTIONARY_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"
CHANNEL_LINK = "t.me/englishwotd"
IMAGE_DIR = "word_images"
FONT_PATH = "C:/Windows/Fonts/georgia.ttf"  # Path to Georgia font; falls back to default if not found
PORT = int(os.getenv("PORT", 8080))  # Render will set the PORT environment variable
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Will be set after deployment

# List of 100 random background colors (RGB tuples)
BACKGROUND_COLORS = [
    (255, 99, 71), (255, 127, 80), (255, 165, 0), (255, 215, 0), (255, 255, 0),
    (240, 230, 140), (245, 245, 220), (220, 220, 220), (211, 211, 211), (192, 192, 192),
    (169, 169, 169), (128, 128, 128), (105, 105, 105), (119, 136, 153), (112, 128, 144),
    (47, 79, 79), (0, 128, 128), (0, 139, 139), (0, 255, 255), (0, 255, 127),
    (0, 250, 154), (0, 255, 0), (127, 255, 0), (173, 255, 47), (50, 205, 50),
    (154, 205, 50), (107, 142, 35), (124, 252, 0), (34, 139, 34), (0, 100, 0),
    (0, 128, 0), (144, 238, 144), (152, 251, 152), (143, 188, 143), (46, 139, 87),
    (60, 179, 113), (32, 178, 170), (64, 224, 208), (72, 209, 204), (175, 238, 238),
    (127, 255, 212), (176, 224, 230), (95, 158, 160), (70, 130, 180), (100, 149, 237),
    (30, 144, 255), (0, 191, 255), (135, 206, 235), (135, 206, 250), (0, 206, 209),
    (0, 255, 255), (224, 255, 255), (240, 255, 255), (240, 255, 240), (245, 255, 250),
    (255, 245, 238), (255, 228, 225), (255, 228, 196), (255, 222, 173), (255, 218, 185),
    (255, 192, 203), (255, 182, 193), (255, 105, 180), (255, 20, 147), (219, 112, 147),
    (199, 21, 133), (238, 130, 238), (218, 112, 214), (221, 160, 221), (186, 85, 211),
    (147, 112, 219), (138, 43, 226), (148, 0, 211), (153, 50, 204), (139, 0, 139),
    (128, 0, 128), (186, 85, 211), (75, 0, 130), (106, 90, 205), (123, 104, 238),
    (72, 61, 139), (25, 25, 112), (0, 0, 128), (0, 0, 139), (0, 0, 205),
    (0, 0, 255), (65, 105, 225), (100, 149, 237), (30, 144, 255), (173, 216, 230),
    (176, 224, 230), (135, 206, 235), (135, 206, 250), (70, 130, 180), (0, 191, 255),
    (240, 248, 255), (245, 245, 220), (255, 250, 240), (255, 245, 238), (245, 245, 245)
]

# Ensure image directory exists
if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# Files for persistent storage
CHAT_IDS_FILE = "chat_ids.txt"
WORD_COUNT_FILE = "word_count.txt"
POSTED_WORDS_FILE = "posted_words.txt"

# ========= Utility Functions =========
def load_chat_ids() -> set:
    """Load stored chat IDs from file."""
    try:
        if os.path.exists(CHAT_IDS_FILE):
            with open(CHAT_IDS_FILE, "r") as f:
                chat_ids = set(json.load(f))
                print(f"Loaded chat IDs: {chat_ids}")
                return chat_ids
        print("No chat IDs file found.")
        return set()
    except Exception as e:
        print(f"Error loading chat IDs: {e}")
        return set()

def save_chat_ids(chat_ids: set) -> None:
    """Save chat IDs to file."""
    try:
        with open(CHAT_IDS_FILE, "w") as f:
            json.dump(list(chat_ids), f)
        print(f"Saved chat IDs: {chat_ids}")
    except Exception as e:
        print(f"Error saving chat IDs: {e}")

def load_word_count() -> int:
    """Load the current word count."""
    try:
        if os.path.exists(WORD_COUNT_FILE):
            with open(WORD_COUNT_FILE, "r") as f:
                return int(f.read().strip())
        return 0
    except Exception as e:
        print(f"Error loading word count: {e}")
        return 0

def save_word_count(count: int) -> None:
    """Save the word count."""
    try:
        with open(WORD_COUNT_FILE, "w") as f:
            f.write(str(count))
    except Exception as e:
        print(f"Error saving word count: {e}")

def load_posted_words() -> list:
    """Load previously posted words."""
    try:
        if os.path.exists(POSTED_WORDS_FILE):
            with open(POSTED_WORDS_FILE, "r") as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error loading posted words: {e}")
        return []

def save_posted_word(word: str, word_number: int) -> None:
    """Save a posted word with its number."""
    posted_words = load_posted_words()
    posted_words.append({"word": word, "number": word_number})
    try:
        with open(POSTED_WORDS_FILE, "w") as f:
            json.dump(posted_words, f)
    except Exception as e:
        print(f"Error saving posted word: {e}")

# ========= Background Color Utility =========
def is_dark_color(color: tuple) -> bool:
    """
    Determine if a color is dark based on its luminance.
    Uses the formula: Y = 0.299R + 0.587G + 0.114B
    Returns True if the color is dark (luminance < 128).
    """
    r, g, b = color
    luminance = (0.299 * r) + (0.587 * g) + (0.114 * b)
    return luminance < 128

# ========= Telegram API Functions =========
def send_message(chat_id: str, text: str) -> None:
    """Send a text message to a chat or channel."""
    params = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        response = requests.get(API_URL + "sendMessage", params=params, timeout=10)
        result = response.json()
        if result.get("ok"):
            print(f"Successfully sent message to chat/channel {chat_id}: {text}")
        else:
            print(f"Failed to send message to chat/channel {chat_id}: {result}")
    except Exception as e:
        print(f"Error sending message to {chat_id}: {e}")

def send_photo(chat_id: str, image_path: str, caption: str) -> None:
    """Send a photo with caption to a chat or channel."""
    if not os.path.exists(image_path):
        print(f"Image file {image_path} does not exist for chat/channel {chat_id}.")
        return
    files = {"photo": open(image_path, "rb")}
    data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
    try:
        response = requests.post(API_URL + "sendPhoto", data=data, files=files, timeout=20)
        result = response.json()
        if result.get("ok"):
            print(f"Successfully sent photo to chat/channel {chat_id}.")
        else:
            print(f"Failed to send photo to chat/channel {chat_id}: {result}")
    except Exception as e:
        print(f"Error sending photo to {chat_id}: {e}")
    finally:
        files["photo"].close()

def set_webhook():
    """Set the webhook for the bot."""
    if not WEBHOOK_URL:
        print("WEBHOOK_URL not set. Cannot set webhook.")
        return
    url = f"{API_URL}setWebhook?url={WEBHOOK_URL}"
    try:
        response = requests.get(url, timeout=10)
        result = response.json()
        if result.get("ok"):
            print(f"Webhook set successfully to {WEBHOOK_URL}")
        else:
            print(f"Failed to set webhook: {result}")
    except Exception as e:
        print(f"Error setting webhook: {e}")

# ========= Word and Definition Fetching =========
def get_random_word() -> str:
    """Fetch a random word from the Random Word API (https://random-word-api.herokuapp.com/word)."""
    try:
        url = "https://random-word-api.herokuapp.com/word"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        words = response.json()
        if words and isinstance(words, list):
            word = words[0]
            print(f"Fetched random word: {word}")
            return word
        print("Failed to fetch a random word.")
        return None
    except Exception as e:
        print(f"Error fetching random word: {e}")
        return None

def get_word_data(word: str) -> dict:
    """Fetch the word's definition and phonetics from the Dictionary API."""
    try:
        url = f"{DICTIONARY_API_URL}{word}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data or not isinstance(data, list):
            print(f"Word '{word}' not found in Dictionary API.")
            return {
                "phonetic": "",
                "definition": "Definition not found."
            }

        # Get phonetic
        phonetic = data[0].get("phonetic", "")
        if not phonetic:
            for phonetic_entry in data[0].get("phonetics", []):
                if phonetic_entry.get("text"):
                    phonetic = phonetic_entry["text"]
                    break

        # Get definition
        definition = "Definition not found."
        if data[0].get("meanings"):
            for meaning in data[0]["meanings"]:
                if meaning.get("definitions"):
                    definition = meaning["definitions"][0]["definition"]
                    break

        print(f"Fetched data for {word}: Phonetic: {phonetic}, Definition: {definition}")
        return {
            "phonetic": phonetic,
            "definition": definition
        }
    except Exception as e:
        print(f"Error fetching data for {word}: {e}")
        return {
            "phonetic": "",
            "definition": "Definition not found."
        }

# ========= Image Generation =========
def generate_word_image(word: str, phonetic: str, word_number: int) -> str:
    """
    Create a clean image (800x400) with a random background color:
    - Word in Georgia font with a shadow effect
    - Channel link and word number at the bottom
    - Text color adjusts based on background brightness
    """
    width, height = 800, 400
    # Select a random background color
    background_color = random.choice(BACKGROUND_COLORS)
    image = Image.new("RGB", (width, height), background_color)
    draw = ImageDraw.Draw(image)

    # Determine text color based on background brightness
    if is_dark_color(background_color):
        text_color = (255, 255, 255)  # White text for dark backgrounds
        shadow_color = (100, 100, 100)
    else:
        text_color = (0, 0, 0)  # Black text for light backgrounds
        shadow_color = (150, 150, 150)

    # Load fonts
    try:
        word_font = ImageFont.truetype(FONT_PATH, 80)
        footer_font = ImageFont.truetype(FONT_PATH, 30)
    except Exception as e:
        print(f"Error loading font: {e}, using default font.")
        word_font = ImageFont.load_default()
        footer_font = ImageFont.load_default()

    # Draw the word with a shadow effect
    word_text = word.capitalize()
    word_bbox = draw.textbbox((0, 0), word_text, font=word_font)
    word_w = word_bbox[2] - word_bbox[0]
    word_h = word_bbox[3] - word_bbox[1]
    word_x = (width - word_w) // 2
    word_y = (height - word_h) // 2 - 20

    # Draw shadow
    shadow_offset = 3
    draw.text((word_x + shadow_offset, word_y + shadow_offset), word_text, fill=shadow_color, font=word_font)
    # Draw main word
    draw.text((word_x, word_y), word_text, fill=text_color, font=word_font)

    # Draw footer with channel link and word number
    footer_text = f"{CHANNEL_LINK} #{word_number}"
    footer_bbox = draw.textbbox((0, 0), footer_text, font=footer_font)
    footer_w = footer_bbox[2] - footer_bbox[0]
    footer_h = footer_bbox[3] - footer_bbox[1]
    footer_x = (width - footer_w) // 2
    footer_y = height - footer_h - 20
    draw.text((footer_x, footer_y), footer_text, fill=text_color, font=footer_font)

    image_path = os.path.join(IMAGE_DIR, f"word_image_{word_number}.png")
    try:
        image.save(image_path)
        print(f"Generated image at {image_path}")
        return image_path
    except Exception as e:
        print(f"Error saving image: {e}")
        return None

# ========= Daily Word Posting =========
def post_daily_word(chat_ids: set) -> None:
    """Fetch a random word, get its data, generate an image, and post it."""
    print("Posting daily word...")
    if not chat_ids:
        print("No chat IDs to post to. Please send /start in a chat or add the bot to a channel.")
        return
    word = get_random_word()
    if not word:
        print("Failed to fetch a random word.")
        return

    word_data = get_word_data(word)
    word_number = load_word_count() + 1
    save_word_count(word_number)
    save_posted_word(word, word_number)

    image_path = generate_word_image(word, word_data["phonetic"], word_number)
    if not image_path:
        print("Failed to generate image.")
        return

    caption = (
        f"📖 *Word of the Day*\n\n"
        f"*{word.capitalize()}*\n"
        f"/{word_data['phonetic']}/\n\n"
        f"*Definition:* {word_data['definition']}\n\n"
        f"#EnglishWord #{word_number}"
    )

    for chat_id in chat_ids:
        print(f"Attempting to post to chat/channel {chat_id}...")
        send_photo(chat_id, image_path, caption)

    try:
        os.remove(image_path)
        print(f"Deleted image file {image_path}")
    except Exception as e:
        print(f"Error deleting image file: {e}")
    print("Daily word posted.")

# ========= Scheduling Function =========
def schedule_daily_post(chat_ids: set) -> None:
    """Schedule the daily word post at exactly 21:00 every day."""
    while True:
        now = datetime.now()
        # Calculate the next 21:00
        next_post = now.replace(hour=21, minute=0, second=0, microsecond=0)
        if now > next_post:
            # If it's already past 21:00 today, schedule for tomorrow
            next_post += timedelta(days=1)

        # Calculate seconds until the next 21:00
        seconds_until_post = (next_post - now).total_seconds()
        print(f"Next post scheduled at {next_post}. Sleeping for {seconds_until_post} seconds...")
        time.sleep(seconds_until_post)

        # Post the daily word at exactly 21:00
        post_daily_word(chat_ids)

# ========= Webhook Handling =========
app = Bottle()

@app.post('/')
def webhook():
    """Handle incoming updates from Telegram."""
    update = request.json
    if "message" in update:
        message = update["message"]
        chat_id = str(message["chat"]["id"])
        text = message.get("text", "")
        print(f"Received message from chat {chat_id}: {text}")
        if text.strip().lower() == "/start":
            if chat_id not in chat_ids:
                chat_ids.add(chat_id)
                print(f"Added new chat ID (via /start): {chat_id}")
                welcome_message = (
                    "🌟 *Welcome to English Word of the Day Bot!*\n\n"
                    "I post a random English word every day at 21:00, along with its definition and phonetics! 📖\n\n"
                    f"Join my channel for daily updates: {CHANNEL_LINK}"
                )
                send_message(chat_id, welcome_message)
            save_chat_ids(chat_ids)
    return "OK"

# ========= Main Function =========
chat_ids = load_chat_ids()

# Start the scheduling in a separate thread
scheduler_thread = threading.Thread(target=schedule_daily_post, args=(chat_ids,))
scheduler_thread.daemon = True
scheduler_thread.start()

# Set the webhook on startup
set_webhook()

# Run the Bottle server
if __name__ == "__main__":
    run(app, host="0.0.0.0", port=PORT)