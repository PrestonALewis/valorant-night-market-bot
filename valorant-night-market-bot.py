import discord
import requests
import asyncio
from dotenv import load_dotenv
import os
from threading import Thread
from flask import Flask, request
from datetime import datetime
import pytz

# Load environment variables
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
USER_ID = os.getenv("USER_ID")

TWITTER_USERNAME = "VALORANT"
QUERY = [
    "night market", "the", "an", "a", "and", "their", "these", "those",
    "these", "that", "this"
]
LAST_SEEN_TWEET_ID = None

headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


def fetch_latest_tweet():
    url = f"https://api.twitter.com/2/tweets/search/recent?query=from:{TWITTER_USERNAME}&max_results=5&tweet.fields=created_at"
    response = requests.get(url, headers=headers)
    data = response.json()

    if "data" in data:
        for tweet in data["data"]:
            if QUERY.lower() in tweet["text"].lower():
                return tweet
    return None


@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

    channel = client.get_channel(DISCORD_CHANNEL_ID)
    if not channel:
        print(f"❌ Channel with ID {DISCORD_CHANNEL_ID} not found.")
        return

    # Send simple startup message
    #await channel.send("👋 Bot is online and ready!")

    async def check_twitter():
        global LAST_SEEN_TWEET_ID
        while True:
            tweet = fetch_latest_tweet()
            if tweet:
                tweet_id = tweet["id"]
                if tweet_id != LAST_SEEN_TWEET_ID:
                    LAST_SEEN_TWEET_ID = tweet_id
                    tweet_text = tweet["text"]
                    tweet_link = f"https://twitter.com/{TWITTER_USERNAME}/status/{tweet_id}"
                    await channel.send(f"🛒 **Valorant Night Market Alert!**\n"
                                       f"<@{USER_ID}>\n"  # This pings the user
                                       f"{tweet_text}\n"
                                       f"{tweet_link}")
            await asyncio.sleep(1800)

    client.loop.create_task(check_twitter())


app = Flask(__name__)

ping_log = []  # Stores all ping timestamps


@app.route('/')
def home():
    # Build the HTML response

    # Set timezone to CST
    cst = pytz.timezone('US/Central')
    now_cst = datetime.now(cst)

    # Format time
    timestamp = now_cst.strftime("%m-%d-%Y, %-I:%M:%S %p CST")

    # Append to log (optional, remove if you don't plan to display history)
    ping_log.append(f"✅{timestamp} from {request.remote_addr}")

    print(f"✅ Ping received: {timestamp} from {request.remote_addr}")

    # Build log output
    log_entries = "<br>".join(ping_log)
    log = f"Bot is running!<br>Ping log:<br>{log_entries}"

    return f"<pre>{log}</pre>"


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()


keep_alive()

client.run(DISCORD_TOKEN)
