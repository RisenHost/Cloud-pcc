#!/usr/bin/env python3
import os
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import logging
import discord
from discord.ext import commands

# Load token from .env if present
load_dotenv()
TOKEN = os.getenv("VPS_BOT_TOKEN", "").strip()

# Basic config
IMAGE_NAME = "ubuntu-tmate"
STATE_FILE = "vps_state.json"
DOCKER_START_TIMEOUT = 12
TMATE_WAIT_TIMEOUT = 18

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# State persistence
if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r") as f:
            STATE = json.load(f)
    except Exception:
        STATE = {}
else:
    STATE = {}

def save_state():
    with open(STATE_FILE, "w") as f:
        json.dump(STATE, f, indent=2)

async def run_cmd(*args, timeout=None):
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return 124, "", "timeout"
    return proc.returncode, (stdout.decode().strip() if stdout else ""), (stderr.decode().strip() if stderr else "")

def is_admin_or_owner(ctx):
    if ctx.guild is None:
        return True
    return (ctx.author.guild_permissions.administrator
            or ctx.author.guild_permissions.manage_guild
            or ctx.author == ctx.guild.owner)

@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user} (id: {bot.user.id})")

# create-vps: usage: !create-vps <ram> <cores> <disk> <SSD/HDD> [@user] <vps_name>
@bot.command(name="create-vps")
@commands.guild_only()
async def create_vps(ctx, ram: str, cores: str, disk: str, storage_type: str, target: discord.Member = None, vps_name: str = None):
    await ctx.trigger_typing()
    if vps_name is None:
        await ctx.send("Usage: `!create-vps <ram> <cores> <disk> <SSD/HDD> [@user] <vps_name>`\nExample: `!create-vps 2G 2 20G SSD @User myvps`")
        return

    if vps_name in STATE:
        await ctx.send(f"⚠️ A VPS named `{vps_name}` already exists.")
        return

    if target is None:
        target = ctx.author

    # Start container detached
    create_cmd = ["docker", "run", "-d", "--rm", "--name", vps_name, "--hostname", vps_name, "--memory", ram, "--cpus", cores, IMAGE_NAME]
    rc, out, err = await run_cmd(*create_cmd, timeout=DOCKER_START_TIMEOUT)
    if rc != 0:
        await ctx.send(f"❌ Failed to create container: `{err or out}`")
        return

    container_id = out.strip()
    STATE[vps_name] = {
        "owner_id": target.id,
        "owner_name": str(target),
        "container_id": container_id,
        "ram": ram, "cores": cores, "disk": disk, "storage_type": storage_type,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "tmate_ssh": None
    }
    save_state()

    await ctx.send(f"✅ Container `{vps_name}` created (id `{container_id[:12]}`). I'll DM {target.mention} when ready.")

    async def setup_tmate():
        try:
            rc1, out1, err1 = await run_cmd("docker", "exec", vps_name, "bash", "-lc", "tmate -S /tmp/tmate.sock new-session -d")
            if rc1 != 0:
                try:
                    await target.send(f"⚠️ VPS `{vps_name}` created but tmate failed to start: `{err1 or out1}`")
                except discord.Forbidden:
                    await ctx.send(f"⚠️ Could not DM the target {target.mention}.")
                return

            waited = 0
            ssh_line = ""
            while waited < TMATE_WAIT_TIMEOUT:
                rc2, out2, err2 = await run_cmd("docker", "exec", vps_name, "bash", "-lc", "tmate -S /tmp/tmate.sock wait tmate-ready || true; tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}' || true")
                out2 = out2.strip()
                if out2:
                    ssh_line = out2.splitlines()[-1].strip()
                    break
                await asyncio.sleep(1)
                waited += 1

            if not ssh_line:
                rc_logs, logs, _ = await run_cmd("docker", "logs", vps_name)
                try:
                    await target.send(f"⚠️ tmate did not become ready for `{vps_name}` within {TMATE_WAIT_TIMEOUT}s. Container is running.\nLogs:\n```\n{(logs or '')[:1900]}\n```")
                except discord.Forbidden:
                    await ctx.send(f"⚠️ Could not DM the target {target.mention}.")
                STATE[vps_name]["tmate_ssh"] = None
                save_state()
                return

            STATE[vps_name]["tmate_ssh"] = ssh_line
            save_state()

            dm_text = (
                f"🔔 **Your VPS is ready!**\n"
                f"Name: `{vps_name}`\n"
                f"Specs: {ram} RAM, {cores} cores, {disk} {storage_type}\n"
                f"SSH (tmate): `{ssh_line}`\n"
                f"Prompt: `root@{vps_name}:~#`\n\n"
                f"To stop: `!stop-vps {vps_name}`"
            )
            try:
                await target.send(dm_text)
            except discord.Forbidden:
                await ctx.send(f"⚠️ Could not DM the target {target.mention}.")
        except Exception as e:
            logging.exception("Error in setup_tmate: %s", e)
            try:
                await target.send(f"⚠️ Unexpected error while preparing VPS `{vps_name}`: {e}")
            except:
                pass

    bot.loop.create_task(setup_tmate())

@bot.command(name="stop-vps")
@commands.guild_only()
async def stop_vps(ctx, vps_name: str):
    if vps_name not in STATE:
        await ctx.send(f"⚠️ No VPS named `{vps_name}` found.")
        return
    entry = STATE[vps_name]
    owner_id = entry.get("owner_id")
    if ctx.author.id != owner_id and not is_admin_or_owner(ctx):
        await ctx.send("⛔ You don't have permission to stop this VPS (only owner or server admins).")
        return

    rc, out, err = await run_cmd("docker", "stop", vps_name, timeout=10)
    if rc == 0:
        STATE.pop(vps_name, None)
        save_state()
        await ctx.send(f"🛑 VPS `{vps_name}` stopped and removed.")
    else:
        await ctx.send(f"⚠️ Failed to stop container `{vps_name}`: `{err or out}`")

@bot.command(name="list")
@commands.guild_only()
async def list_vps(ctx, scope: str = "mine"):
    if scope not in ("mine", "all"):
        await ctx.send("Usage: `!list` or `!list all` (admins only)")
        return
    if scope == "all" and not is_admin_or_owner(ctx):
        await ctx.send("⛔ You must be a server admin to use `!list all`.")
        return

    if scope == "all":
        items = STATE.items()
        title = "All VPS"
    else:
        uid = ctx.author.id
        items = [(k, v) for k, v in STATE.items() if v.get("owner_id") == uid]
        title = f"VPS owned by {ctx.author.display_name}"

    if not items:
        await ctx.send("No VPS found.")
        return

    embed = discord.Embed(title=title, color=discord.Color.green(), timestamp=datetime.utcnow())
    for name, info in items:
        owner = info.get("owner_name", "unknown")
        created = info.get("created_at", "unknown")
        tmate = info.get("tmate_ssh") or "pending..."
        value = f"Owner: {owner}\nCreated: {created}\nSpecs: {info.get('ram')} RAM, {info.get('cores')} cores, {info.get('disk')} {info.get('storage_type')}\nSSH: `{tmate}`"
        embed.add_field(name=name, value=value, inline=False)

    await ctx.send(embed=embed)

@bot.command(name="help-kvm")
async def help_kvm(ctx):
    embed = discord.Embed(title="📜 VPS Bot Commands", color=discord.Color.blue())
    embed.add_field(name="!create-vps <ram> <cores> <disk> <SSD/HDD> [@user] <vps_name>", value="Create a container-based VPS and DM the target.", inline=False)
    embed.add_field(name="!stop-vps <vps_name>", value="Stop and remove a VPS (owner or admins only).", inline=False)
    embed.add_field(name="!list [mine|all]", value="List your VPS or all (admins).", inline=False)
    await ctx.send(embed=embed)

if __name__ == "__main__":
    if not TOKEN:
        print("VPS_BOT_TOKEN not set. Create a .env file with VPS_BOT_TOKEN=YOUR_TOKEN or set env var.")
        exit(1)
    bot.run(TOKEN)
