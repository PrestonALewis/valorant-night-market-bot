import discord
import requests
import asyncio
from dotenv import load_dotenv
import os
from threading import Thread
from flask import Flask, request
from datetime import datetime, timedelta, timezone
import pytz

# Load environment variables
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
USER_ID = os.getenv("USER_ID")

# Hardcoded Twitter user IDs mapped to usernames
TWITTER_USERS = {
    "1230550898616586242": "VALORANT",
    "1267553030788055047": "ValorLeaks",
    "759459947344175104": "ValorantUpdated",
    "1365697129243676672": "VALORANTLeaksEN"
}

MATCH_WINDOW_HOURS = 168  # 7 days

# Track the last seen tweet ID per user
last_seen_ids = {user_id: None for user_id in TWITTER_USERS}
recent_matches = []

headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


def fetch_matching_tweets():
    user_query = " OR ".join(f"from:{TWITTER_USERS[uid]}"
                             for uid in TWITTER_USERS)
    keyword_query = '"night market" OR nightmarket'
    query = f"({keyword_query}) ({user_query})"

    url = (f"https://api.twitter.com/2/tweets/search/recent"
           f"?query={requests.utils.quote(query)}"
           f"&max_results=100&tweet.fields=created_at,author_id")

    res = requests.get(url, headers=headers)
    print(f"[DEBUG] Twitter API status: {res.status_code}")
    if res.status_code != 200:
        return []

    tweets = []
    data = res.json().get("data", [])
    for tweet in data:
        author_id = tweet["author_id"]
        if author_id not in TWITTER_USERS:
            continue
        tweets.append({
            "id": tweet["id"],
            "text": tweet["text"],
            "username": TWITTER_USERS[author_id],
            "timestamp": tweet["created_at"],
            "author_id": author_id
        })
    return tweets


def prune_old_matches():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MATCH_WINDOW_HOURS)
    recent_matches[:] = [
        m for m in recent_matches if datetime.fromisoformat(
            m["timestamp"].replace("Z", "+00:00")) > cutoff
    ]


@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

    channel = client.get_channel(DISCORD_CHANNEL_ID)
    if not channel:
        print(f"❌ Channel with ID {DISCORD_CHANNEL_ID} not found.")
        return

    await channel.send("👋 Bot is online and monitoring Night Market tweets!")

    async def check_twitter():
        while True:
            tweets = fetch_matching_tweets()
            new_matches = []

            for tweet in tweets:
                author_id = tweet["author_id"]
                if tweet["id"] != last_seen_ids[author_id]:
                    last_seen_ids[author_id] = tweet["id"]
                    new_matches.append(tweet)
                    recent_matches.append(tweet)

            prune_old_matches()

            unique_accounts = {m["username"] for m in recent_matches}

            print(f"[DEBUG] Matches this cycle: {len(new_matches)}")
            for match in new_matches:
                print(f"[MATCH] {match['username']}: {match['text'][:80]}...")

            if len(unique_accounts) >= 2:
                print(
                    f"[ALERT] Sending ping — {len(unique_accounts)} unique accounts matched."
                )
                await channel.send(
                    f"🛒 **Valorant Night Market Alert!**\n"
                    f"<@{USER_ID}>\n\n" + "\n\n".join(
                        f"**{m['username']}**: {m['text']}\nhttps://twitter.com/{m['username']}/status/{m['id']}"
                        for m in recent_matches))
                recent_matches.clear()

            await asyncio.sleep(8 * 60 * 60)  # Poll every 8 hours

    client.loop.create_task(check_twitter())


# Flask server for uptime monitoring
app = Flask(__name__)
ping_log = []


@app.route('/')
def home():
    cst = pytz.timezone('US/Central')
    now_cst = datetime.now(cst)
    timestamp = now_cst.strftime("%m-%d-%Y, %-I:%M:%S %p CST")
    ping_log.append(f"✅ {timestamp} from {request.remote_addr}")
    print(f"✅ Ping received: {timestamp} from {request.remote_addr}")
    log_entries = "<br>".join(ping_log)
    return f"<pre>Bot is running!<br>Ping log:<br>{log_entries}</pre>"


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()


keep_alive()
client.run(DISCORD_TOKEN)
