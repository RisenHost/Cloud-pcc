import discord
from discord.ext import commands
import asyncio
import subprocess
import random
import string

TOKEN = "YOUR_DISCORD_BOT_TOKEN"
PREFIX = "!"
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# Memory store for VPS data
vps_list = {}

def random_id(length=6):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# Progress animation
async def send_progress(dm, steps):
    msg = await dm.send("⏳ Initializing...")
    for step in steps:
        await asyncio.sleep(1.5)
        await msg.edit(content=step)
    await asyncio.sleep(1)
    await msg.edit(content="✅ VPS Creation Complete!")

@bot.command()
async def create_vps(ctx, ram: str, cores: str, customer_name: str, vps_name: str):
    try:
        dm = await ctx.author.create_dm()
        await dm.send(embed=discord.Embed(
            title="🚀 VPS Creation Started",
            description=f"Customer: **{customer_name}**\nVPS Name: **{vps_name}**\nSpecs: {ram} RAM, {cores} Cores",
            color=0x2ecc71
        ))

        steps = [
            "⚙️ [1/4] Creating VPS container...",
            "📦 [2/4] Installing Ubuntu...",
            "🔑 [3/4] Installing tmate...",
            "🛠 [4/4] Finalizing setup..."
        ]
        await send_progress(dm, steps)

        # VPS creation simulation (replace with real docker/tmate setup)
        ssh_user = f"root@{vps_name}"
        tmate_link = f"https://tmate.io/t/{random_id(10)}"

        # Save in memory
        vps_list[vps_name] = {
            "customer": customer_name,
            "ram": ram,
            "cores": cores,
            "ssh": ssh_user,
            "tmate": tmate_link
        }

        embed = discord.Embed(
            title="✅ VPS Ready",
            description=f"**SSH Access:** `{ssh_user}`\n**Tmate Link:** {tmate_link}",
            color=0x00ff00
        )
        embed.set_footer(text="Enjoy your VPS! 🚀")
        await dm.send(embed=embed)
    except Exception as e:
        await ctx.author.send(f"❌ Error creating VPS: `{str(e)}`")

@bot.command()
async def stop_vps(ctx, vps_name: str):
    dm = await ctx.author.create_dm()
    if vps_name in vps_list:
        await send_progress(dm, ["🛑 Stopping VPS...", "💤 VPS Shutdown Complete!"])
        del vps_list[vps_name]
        await dm.send(embed=discord.Embed(
            title="🛑 VPS Stopped",
            description=f"VPS `{vps_name}` has been shut down.",
            color=0xe74c3c
        ))
    else:
        await dm.send(f"❌ VPS `{vps_name}` not found.")

@bot.command()
async def list(ctx):
    dm = await ctx.author.create_dm()
    if not vps_list:
        await dm.send("📭 No VPS instances found.")
        return

    embed = discord.Embed(title="📜 VPS List", color=0x3498db)
    for name, info in vps_list.items():
        embed.add_field(
            name=f"{name}",
            value=f"👤 {info['customer']} | 💾 {info['ram']} | ⚙ {info['cores']} cores\n🔑 `{info['ssh']}`\n🔗 {info['tmate']}",
            inline=False
        )
    await dm.send(embed=embed)

@bot.command()
async def help_kvm(ctx):
    dm = await ctx.author.create_dm()
    embed = discord.Embed(title="📖 Bot Commands", color=0xf1c40f)
    embed.add_field(name="`!create_vps <ram> <cores> <customer> <vpsname>`", value="Create a new VPS.", inline=False)
    embed.add_field(name="`!stop_vps <vpsname>`", value="Stop a VPS.", inline=False)
    embed.add_field(name="`!list`", value="List all VPS instances.", inline=False)
    embed.set_footer(text="Bot created with ❤️")
    await dm.send(embed=embed)

bot.run(TOKEN)
