import discord
from discord.ext import commands
import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = "!"
bot = commands.Bot(command_prefix=PREFIX, intents=discord.Intents.all())

# ✅ Fancy startup animation
@bot.event
async def on_ready():
    print("🚀 Booting up...")
    print("💻 Connecting to Discord...")
    print(f"✅ Logged in as {bot.user}")

# 🆘 Help Command
@bot.command(name="help-kvm")
async def help_kvm(ctx):
    embed = discord.Embed(
        title="⚙ VPS Bot Commands",
        description="Here’s what I can do:",
        color=0x00ff00
    )
    embed.add_field(name="🖥 !create-vps <ram> <cores> <vpsname>", value="Create a new VPS.", inline=False)
    embed.add_field(name="📜 !list", value="List all running VPS containers.", inline=False)
    embed.add_field(name="🛑 !stop-vps <vpsname>", value="Stop a specific VPS.", inline=False)
    embed.set_footer(text="Powered by Docker + Ubuntu + tmate")
    await ctx.send(embed=embed)

# 🖥 Create VPS Command
@bot.command(name="create-vps")
async def create_vps(ctx, ram: str, cores: str, vpsname: str):
    await ctx.send(f"⚙ Creating VPS `{vpsname}` for you... ⏳")

    container_name = f"{vpsname.lower()}"
    hostname = f"root@{vpsname}"

    cmd = [
        "docker", "run", "-d",
        "--name", container_name,
        "--hostname", hostname,
        "--cpus", cores,
        "--memory", ram,
        "ubuntu-tmate"
    ]

    subprocess.run(cmd)

    # Get container SSH info (simulate since tmate is preinstalled)
    ssh_info = f"ssh root@<server-ip>  # VPS: {vpsname}"
    await ctx.author.send(f"✅ Your VPS `{vpsname}` is ready!\n🔑 SSH: `{ssh_info}`")

# 📜 List VPS Command
@bot.command(name="list")
async def list_vps(ctx):
    result = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True)
    vps_list = result.stdout.strip() or "No VPS running."
    await ctx.send(f"📜 **Running VPS:**\n```\n{vps_list}\n```")

# 🛑 Stop VPS Command
@bot.command(name="stop-vps")
async def stop_vps(ctx, vpsname: str):
    subprocess.run(["docker", "stop", vpsname])
    await ctx.send(f"🛑 VPS `{vpsname}` has been stopped.")

bot.run(TOKEN)
