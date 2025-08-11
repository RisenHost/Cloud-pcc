#!/usr/bin/env python3
"""
vps_bot.py - Docker-based VPS bot with tmate integration.

Commands:
 - !create-vps <ram> <cores> <disk> <SSD/HDD> [@user] <vps_name>
 - !stop-vps <vps_name>
 - !list [mine|all]
 - !help-kvm
"""

import os
import json
import shlex
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

import discord
from discord.ext import commands

# Load .env if present
load_dotenv()

# Config
TOKEN = os.getenv("VPS_BOT_TOKEN") or os.getenv("BOT_TOKEN") or ""
IMAGE_NAME = "ubuntu-tmate"
STATE_FILE = "vps_state.json"
DOCKER_START_TIMEOUT = 12
TMATE_WAIT_TIMEOUT = 18

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Load state
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
    """Run subprocess and return (rc, stdout, stderr)."""
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
    return proc.returncode, stdout.decode().strip(), stderr.decode().strip()

def is_admin_or_owner(ctx):
    if ctx.guild is None:
        return True  # DM context — allow
    return (ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.manage_guild
            or ctx.author == ctx.guild.owner)

@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user} (id: {bot.user.id})")
    logging.info("Ready.")

# ---------------- Commands ----------------

@bot.command(name="create-vps")
@commands.guild_only()
async def create_vps(ctx, ram: str, cores: str, disk: str, storage_type: str, target: discord.Member = None, vps_name: str = None):
    """
    Usage:
    !create-vps <ram> <cores> <disk> <SSD/HDD> [@user] <vps_name>
    Example:
    !create-vps 2G 2 20G SSD @User myvps
    """
    await ctx.trigger_typing()

    # If target is None, treat the last arg as vps_name was provided incorrectly
    if vps_name is None:
        # If user didn't provide mention, discord converter puts target=None and vps_name is None -> bad usage
        await ctx.send("❌ Usage: `!create-vps <ram> <cores> <disk> <SSD/HDD> [@user] <vps_name>`\nExample: `!create-vps 2G 2 20G SSD @User myvps`")
        return

    if vps_name in STATE:
        await ctx.send(f"⚠️ A VPS named `{vps_name}` already exists. Use a different name or stop the existing one.")
        return

    # Default target to command author if none
    if target is None:
        target = ctx.author

    # Quick create container in detached mode (tail keeps it alive)
    create_cmd = ["docker", "run", "-d", "--rm", "--name", vps_name, "--hostname", vps_name, "--memory", ram, "--cpus", cores, IMAGE_NAME]
    # Execute
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

    await ctx.send(f"✅ Container `{vps_name}` created (id `{container_id[:12]}`). I'll DM {target.mention} when tmate is ready.")

    async def setup_tmate():
        try:
            # create detached session
            rc1, out1, err1 = await run_cmd("docker", "exec", vps_name, "bash", "-lc", "tmate -S /tmp/tmate.sock new-session -d")
            if rc1 != 0:
                logging.error("tmate new-session failed: %s %s", out1, err1)
                try:
                    await target.send(f"⚠️ VPS `{vps_name}` created but tmate failed to start: `{err1 or out1}`")
                except discord.Forbidden:
                    await ctx.send(f"⚠️ Could not DM the target {target.mention}.")
                return

            # poll for tmate-ready and get SSH
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
                # fetch logs for debugging
                rc_logs, logs, _ = await run_cmd("docker", "logs", vps_name)
                try:
                    await target.send(f"⚠️ tmate did not become ready for `{vps_name}` within {TMATE_WAIT_TIMEOUT}s. Container is running.\nLogs:\n```\n{logs[:1900]}\n```")
                except discord.Forbidden:
                    await ctx.send(f"⚠️ Could not DM the target {target.mention}.")
                STATE[vps_name]["tmate_ssh"] = None
                save_state()
                return

            # save and DM
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
    embed.add_field(name="!create-vps <ram> <cores> <disk> <SSD/HDD> [@user] <vps_name>", value="Create a container-based VPS and DM the target. Example: `!create-vps 2G 2 20G SSD @User myvps`", inline=False)
    embed.add_field(name="!stop-vps <vps_name>", value="Stop and remove a VPS (owner or admins only).", inline=False)
    embed.add_field(name="!list [mine|all]", value="List your VPS or all (admins).", inline=False)
    await ctx.send(embed=embed)

# Entry point
if __name__ == "__main__":
    if not TOKEN:
        logging.error("VPS_BOT_TOKEN not found. Please set it in .env or env var VPS_BOT_TOKEN.")
        print("Set VPS_BOT_TOKEN in environment or create .env with VPS_BOT_TOKEN=...")
        exit(1)
    bot.run(TOKEN)
