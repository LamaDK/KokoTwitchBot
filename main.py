import os
import asyncio
import aiohttp
from aiohttp import web
from twitchio.ext import commands

TWITCH_CLIENT_ID = 'fnvi9p6h2df2jbfzir013n14hme1t1'
TWITCH_CLIENT_SECRET = 'o5yaim2b9bu3l51qrpuu3urpwg0e02'
TWITCH_CHANNEL_NAME = 'niikokonut'
WEBHOOK_URL = 'https://kokotwitchbot.onrender.com'
VERIFY_SECRET = 'supersecret'
redeem_queue = []

# === Twitch Bot Class ===
class TwitchBot(commands.Bot):
    def __init__(self):
        print(f"🔧 Initializing TwitchBot for channel: {TWITCH_CHANNEL_NAME}")
        super().__init__(
            token='oauth:i9enlsir7irpzemd364elr5kn1hhj9',  # Replace with your updated token if needed
            prefix='!',
            initial_channels=[TWITCH_CHANNEL_NAME]
        )

    async def event_ready(self):
        print(f"✅ Twitch bot ready: {self.nick}")

    async def event_message(self, message):
        print(f"📩 Received message from {message.author}: {message.content}")
        if not message.author:
            print("⚠️ Skipping message with no author.")
            return
        if message.echo:
            print("🔁 Skipping echo message.")
            return
        await self.handle_commands(message)

    @commands.command(name="que")
    async def que_command(self, ctx):
        print(f"⚙️ Command received: !que from {ctx.author.name}")
        if ctx.author.is_mod or ctx.author.name.lower() == TWITCH_CHANNEL_NAME:
            if redeem_queue:
                msg = '\n'.join(f"{i+1}. {item}" for i, item in enumerate(redeem_queue))
            else:
                msg = "The redeem queue is currently empty."
            await ctx.send(msg)
        else:
            print(f"⛔ Unauthorized attempt to use !que by {ctx.author.name}")

    @commands.command(name="next")
    async def next_command(self, ctx):
        print(f"⚙️ Command received: !next from {ctx.author.name}")
        if ctx.author.is_mod or ctx.author.name.lower() == TWITCH_CHANNEL_NAME:
            if redeem_queue:
                next_item = redeem_queue.pop(0)
                await ctx.send(f"Next up: {next_item}")
            else:
                await ctx.send("The redeem queue is empty.")
        else:
            print(f"⛔ Unauthorized attempt to use !next by {ctx.author.name}")

# === EventSub Webhook Handler ===
async def handle_eventsub(request):
    data = await request.json()
    print(f"📡 Webhook received: {data}")
    if 'challenge' in data:
        return web.Response(text=data['challenge'])

    if data.get('subscription', {}).get('type') == 'channel.channel_points_custom_reward_redemption.add':
        event = data['event']
        user = event['user_name']
        reward = event['reward']['title']
        redeem_queue.append(f"{user} - {reward}")
        print(f"🎁 [Redeem] {user} redeemed: {reward}")
    return web.Response(text="OK")

# === Subscribe to Twitch EventSub ===
async def subscribe_to_eventsub(broadcaster_id, token):
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "type": "channel.channel_points_custom_reward_redemption.add",
        "version": "1",
        "condition": {"broadcaster_user_id": broadcaster_id},
        "transport": {
            "method": "webhook",
            "callback": WEBHOOK_URL,
            "secret": VERIFY_SECRET
        }
    }
    print("📬 Subscribing to EventSub...")
    async with aiohttp.ClientSession() as session:
        resp = await session.post(
            "https://api.twitch.tv/helix/eventsub/subscriptions",
            headers=headers,
            json=payload
        )
        result = await resp.text()
        print(f"📨 Subscription response: {result}")

# === Get Broadcaster Info and Token ===
async def get_broadcaster_id_and_token():
    print("🔑 Getting broadcaster ID and token...")
    async with aiohttp.ClientSession() as session:
        token_resp = await session.post("https://id.twitch.tv/oauth2/token", params={
            "client_id": TWITCH_CLIENT_ID,
            "client_secret": TWITCH_CLIENT_SECRET,
            "grant_type": "client_credentials"
        })
        token_data = await token_resp.json()
        token = token_data['access_token']
        print("✅ Got app token.")

        user_resp = await session.get("https://api.twitch.tv/helix/users", headers={
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}"
        }, params={"login": TWITCH_CHANNEL_NAME})
        user_data = await user_resp.json()
        broadcaster_id = user_data['data'][0]['id']
        print(f"✅ Broadcaster ID: {broadcaster_id}")
        return broadcaster_id, token

# === Main App Launch ===
async def main():
    broadcaster_id, token = await get_broadcaster_id_and_token()
    await subscribe_to_eventsub(broadcaster_id, token)

    app = web.Application()
    app.router.add_post('/webhook', handle_eventsub)
    runner = web.AppRunner(app)
    await runner.setup()
    PORT = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print("🌐 Webhook server running on port", PORT)

    bot = TwitchBot()
    try:
        await bot.start()
    except Exception as e:
        print(f"⚠️ Twitch bot failed to start: {e}")

if __name__ == '__main__':
    asyncio.run(main())
