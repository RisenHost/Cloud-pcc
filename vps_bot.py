#!/usr/bin/env python3
# Minimal, cleaned VPS bot (prefix commands only).

import os
import json
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

import discord
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv("VPS_BOT_TOKEN", "").strip()

# Config
IMAGE_NAME = "ubuntu-tmate"
STATE_FILE = "vps_state.json"
DOCKER_START_TIMEOUT = 12
TMATE_WAIT_TIMEOUT = 18

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Load / init state
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
        return False
    return (ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.manage_guild or ctx.author == ctx.guild.owner)

@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user} (id: {bot.user.id})")
    print("Bot ready.")

def make_progress_embed(title, lines):
    e = discord.Embed(title=title, color=discord.Color.blurple(), timestamp=datetime.utcnow())
    for i, line in enumerate(lines, 1):
        e.add_field(name=f"Step {i}", value=line, inline=False)
    return e

# ---------- Commands ----------

@bot.command(name="help-kvm")
async def help_kvm(ctx):
    embed = discord.Embed(title="📜 VPS Bot Commands", color=discord.Color.blue())
    embed.add_field(
        name="!create-vps <ram> <cores> <disk> <SSD/HDD> [@user] <vps_name>",
        value="Create a container-based VPS and DM the target when ready.\nExamples:\n"
              "`!create-vps 2G 2 20G SSD myvps` (DMs you)\n"
              "`!create-vps 2G 2 20G SSD @User myvps` (DMs the mentioned user)",
        inline=False
    )
    embed.add_field(
        name="!stop-vps <vps_name>",
        value="Stop & remove a VPS. Only the owner or server admins can stop it.",
        inline=False
    )
    embed.add_field(
        name="!list [mine|all]",
        value="List your VPS (default) or `all` (admins only).",
        inline=False
    )
    await ctx.send(embed=embed)

@bot.command(name="list")
async def list_vps(ctx, scope: str = "mine"):
    # scope: mine or all
    if scope not in ("mine", "all"):
        await ctx.send("Usage: `!list` or `!list all` (admins only).")
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
        value = (f"Owner: {owner}\nCreated: {created}\n"
                 f"Specs: {info.get('ram')} RAM, {info.get('cores')} cores, {info.get('disk')} {info.get('storage_type')}\n"
                 f"SSH: `{tmate}`")
        embed.add_field(name=name, value=value, inline=False)

    await ctx.send(embed=embed)

@bot.command(name="stop-vps")
async def stop_vps(ctx, vps_name: str):
    if vps_name not in STATE:
        await ctx.send(f"⚠️ No VPS named `{vps_name}` found.")
        return
    entry = STATE[vps_name]
    owner_id = entry.get("owner_id")
    # allow stop if author is owner or server admin
    if ctx.author.id != owner_id and not is_admin_or_owner(ctx):
        await ctx.send("⛔ You don't have permission to stop this VPS (only owner or server admins).")
        return

    await ctx.send(f"🛑 Stopping `{vps_name}`...")
    rc, out, err = await run_cmd("docker", "stop", vps_name, timeout=10)
    if rc == 0:
        STATE.pop(vps_name, None)
        save_state()
        await ctx.send(f"✅ VPS `{vps_name}` stopped and removed.")
    else:
        await ctx.send(f"⚠️ Failed to stop `{vps_name}`: `{err or out}`")

@bot.command(name="create-vps")
async def create_vps(ctx, *params):
    """
    Accepts:
    !create-vps ram cores disk storage [@user] vps_name
    or
    !create-vps ram cores disk storage customer_name vps_name
    or
    !create-vps ram cores disk storage vps_name  (DMs author)
    """
    # quick usage check
    try:
        # prepare message + mention detection
        mentions = ctx.message.mentions
        mention_member = mentions[0] if mentions else None

        raw = list(params)
        # remove mention tokens from param list (they look like <@!id> or <@id>)
        filtered = [p for p in raw if not p.startswith("<@")]

        # Now interpret filtered args
        # Supported lengths: 5 or 6 (5 -> ram cores disk storage vps_name; 6 -> ram cores disk storage customer_name vps_name)
        if len(filtered) not in (5, 6):
            await ctx.send("❌ Usage: `!create-vps <ram> <cores> <disk> <SSD/HDD> [@user] <vps_name>`")
            return

        ram = filtered[0]
        cores = filtered[1]
        disk = filtered[2]
        storage_type = filtered[3]
        if len(filtered) == 5:
            vps_name = filtered[4]
            customer_name = None
        else:
            customer_name = filtered[4]
            vps_name = filtered[5]

        # determine target
        if mention_member:
            target = mention_member
        else:
            target = ctx.author

        # prevent duplicate names
        if vps_name in STATE:
            await ctx.send(f"⚠️ A VPS named `{vps_name}` already exists.")
            return

        # ensure docker available
        rc, _, _ = await run_cmd("docker", "--version")
        if rc != 0:
            await ctx.send("❌ Docker not available on this host. VPS creation requires Docker.")
            return

        # send an initial embed and return quickly, do setup in background
        embed = make_progress_embed("Creating VPS", [
            f"Request received by: {ctx.author}",
            f"Target (will be DM'd): {getattr(target, 'mention', str(target))}",
            f"Name: `{vps_name}`",
            f"Specs: {ram} RAM, {cores} cores, {disk} {storage_type}",
            "Status: starting container..."
        ])
        status_msg = await ctx.send(embed=embed)

        # create container
        create_cmd = ["docker", "run", "-d", "--rm", "--name", vps_name, "--hostname", vps_name, "--memory", ram, "--cpus", cores, IMAGE_NAME]
        rc, out, err = await run_cmd(*create_cmd, timeout=DOCKER_START_TIMEOUT)
        if rc != 0:
            await status_msg.edit(embed=make_progress_embed("Create VPS — FAILED", [
                f"Failed to start container: `{err or out}`"
            ]))
            return

        container_id = out.strip()
        # persist minimal state immediately
        STATE[vps_name] = {
            "owner_id": target.id if hasattr(target, "id") else ctx.author.id,
            "owner_name": getattr(target, "name", str(target)),
            "container_id": container_id,
            "ram": ram, "cores": cores, "disk": disk, "storage_type": storage_type,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "tmate_ssh": None
        }
        save_state()

        await status_msg.edit(embed=make_progress_embed("Creating VPS", [
            f"Container started: `{container_id[:12]}`",
            "Status: initialising tmate session (this may take a few seconds)..."
        ]))

        async def setup_tmate_and_notify():
            # start tmate session inside container
            rc1, out1, err1 = await run_cmd("docker", "exec", vps_name, "bash", "-lc", "tmate -S /tmp/tmate.sock new-session -d")
            if rc1 != 0:
                await status_msg.edit(embed=make_progress_embed("Create VPS — tmate failed", [
                    f"Container: `{container_id[:12]}`",
                    f"tmate new-session failed: `{err1 or out1}`"
                ]))
                try:
                    await target.send(f"⚠️ Your VPS `{vps_name}` was created but tmate failed to start: `{err1 or out1}`")
                except discord.Forbidden:
                    await ctx.send(f"⚠️ Could not DM the target {target.mention}.")
                return

            # poll for tmate-ready and gather ssh string
            waited = 0
            ssh_line = ""
            while waited < TMATE_WAIT_TIMEOUT:
                rc2, out2, err2 = await run_cmd("docker", "exec", vps_name, "bash", "-lc", "tmate -S /tmp/tmate.sock wait tmate-ready || true; tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}' || true")
                if out2:
                    ssh_line = out2.strip().splitlines()[-1].strip()
                    break
                await asyncio.sleep(1)
                waited += 1

            if not ssh_line:
                rc_logs, logs, _ = await run_cmd("docker", "logs", vps_name)
                await status_msg.edit(embed=make_progress_embed("Create VPS — tmate timeout", [
                    f"Container `{container_id[:12]}` is running but tmate did not become ready in time.",
                    f"Logs (truncated):\n{(logs or '')[:1500]}"
                ]))
                try:
                    await target.send(f"⚠️ tmate did not become ready for your VPS `{vps_name}` within {TMATE_WAIT_TIMEOUT}s. Container is running.\nLogs:\n```\n{(logs or '')[:1900]}\n```")
                except discord.Forbidden:
                    await ctx.send(f"⚠️ Could not DM the target {target.mention}.")
                STATE[vps_name]["tmate_ssh"] = None
                save_state()
                return

            # success
            STATE[vps_name]["tmate_ssh"] = ssh_line
            save_state()

            # update status message
            await status_msg.edit(embed=make_progress_embed("VPS Ready ✅", [
                f"Name: `{vps_name}`",
                f"Container: `{container_id[:12]}`",
                f"SSH: `{ssh_line}`",
                f"Prompt will be: `root@{vps_name}:~#`"
            ]))

            # DM the target
            dm_embed = discord.Embed(title="🔔 Your VPS is ready", color=discord.Color.green(), timestamp=datetime.utcnow())
            dm_embed.add_field(name="Name", value=f"`{vps_name}`", inline=False)
            dm_embed.add_field(name="Specs", value=f"{ram} RAM, {cores} cores, {disk} {storage_type}", inline=False)
            dm_embed.add_field(name="SSH (tmate)", value=f"`{ssh_line}`", inline=False)
            dm_embed.add_field(name="Prompt", value=f"`root@{vps_name}:~#`", inline=False)
            dm_embed.set_footer(text="VPS Bot • ephemeral container-based VPS")
            try:
                await target.send(embed=dm_embed)
            except discord.Forbidden:
                await ctx.send(f"⚠️ Could not DM the target {target.mention}. They may have DMs closed.")

        # schedule background task (don't await; keep bot responsive)
        bot.loop.create_task(setup_tmate_and_notify())

    except Exception as e:
        logging.exception("create-vps error: %s", e)
        await ctx.send(f"❌ Unexpected error: {e}")

# Run
if __name__ == "__main__":
    if not TOKEN:
        print("VPS_BOT_TOKEN not set. Create a .env file with VPS_BOT_TOKEN=YOUR_TOKEN or set env var.")
        exit(1)
    bot.run(TOKEN)
