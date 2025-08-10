#!/usr/bin/env python3
import discord
from discord.ext import commands
import asyncio
import json
import os
import shlex
from datetime import datetime

# ------------ CONFIG ------------
TOKEN = os.getenv("VPS_BOT_TOKEN", "YOUR_DISCORD_BOT_TOKEN_HERE")
IMAGE_NAME = "ubuntu-tmate"
STATE_FILE = "vps_state.json"
DOCKER_START_TIMEOUT = 10  # seconds to wait for container to be running
TMATE_WAIT_TIMEOUT = 15    # seconds waiting for tmate-ready
# --------------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Load or init state
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        try:
            STATE = json.load(f)
        except:
            STATE = {}
else:
    STATE = {}

def save_state():
    with open(STATE_FILE, "w") as f:
        json.dump(STATE, f, indent=2)

async def run_cmd(*args, capture_output=True, timeout=None):
    """Run a subprocess in non-blocking way and return (returncode, stdout, stderr)."""
    # args are strings
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE if capture_output else None,
        stderr=asyncio.subprocess.PIPE if capture_output else None
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return 124, b"", b"timeout"
    return proc.returncode, stdout.decode().strip() if stdout else "", stderr.decode().strip() if stderr else ""

def is_admin_or_owner(ctx):
    return ctx.author.guild_permissions.manage_guild or ctx.author.guild_permissions.administrator or ctx.author == ctx.guild.owner

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id: {bot.user.id})")
    print("------")

# ---------------- COMMANDS ----------------

@bot.command(name="create-vps")
@commands.guild_only()
async def create_vps(ctx, ram: str, cores: str, disk: str, storage_type: str, target: discord.Member = None, vps_name: str = None):
    """
    Usage:
    !create-vps <ram> <cores> <disk> <SSD/HDD> [@target_member] <vps_name>
    Example:
    !create-vps 2G 2 20G SSD @User myvps
    If no @target_member provided, the command author will receive the DM.
    """
    await ctx.trigger_typing()

    # Determine target and vps_name if mention omitted
    # If user passed mention in place of target, discord converter will put it. If they didn't, target is None.
    if target is None:
        # If they didn't mention, maybe they provided vps_name as 5th param and omitted mention
        # In that case vps_name variable will actually be provided already (since discord will map args)
        # So ensure target defaults to author and vps_name present
        target = ctx.author
        if vps_name is None:
            await ctx.send("❌ Usage: `!create-vps <ram> <cores> <disk> <SSD/HDD> [@user] <vps_name>`\nExample: `!create-vps 2G 2 20G SSD @User myvps`")
            return

    if vps_name is None:
        await ctx.send("❌ Please provide a `vps_name` (last argument).")
        return

    # Prevent name collisions
    if vps_name in STATE:
        await ctx.send(f"⚠️ A VPS with name `{vps_name}` already exists. Choose a different vps_name or stop the old one first.")
        return

    # Start container quickly (detached), using tail -f to keep alive
    # Use memory and cpus flags if provided (they are passed as strings directly)
    create_cmd = [
        "docker", "run", "-d", "--rm",
        "--name", vps_name,
        "--hostname", vps_name,
        "--memory", ram,
        "--cpus", cores,
        IMAGE_NAME,
        "tail", "-f", "/dev/null"
    ]

    # Start container in background thread (non-blocking)
    rc, out, err = await run_cmd(*create_cmd, timeout=DOCKER_START_TIMEOUT)
    if rc != 0:
        await ctx.send(f"❌ Failed to start container: `{err or out}`")
        return

    container_id = out.strip()
    # Store minimal state immediately to allow listing while tmate session is being created
    STATE[vps_name] = {
        "owner_id": target.id,
        "owner_name": str(target),
        "container_id": container_id,
        "ram": ram,
        "cores": cores,
        "disk": disk,
        "storage_type": storage_type,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "tmate_ssh": None
    }
    save_state()

    await ctx.send(f"✅ Container `{vps_name}` created (id `{container_id[:12]}`). Attempting to start tmate and generate SSH link — I'll DM {target.mention} when ready.")

    # Run tmate commands inside container, non-blocking
    async def setup_tmate_and_dm():
        try:
            # create detached session
            cmd_new = ["docker", "exec", vps_name, "bash", "-c", "tmate -S /tmp/tmate.sock new-session -d"]
            rc, out, err = await run_cmd(*cmd_new)
            if rc != 0:
                STATE[vps_name]["tmate_ssh"] = None
                save_state()
                # notify
                try:
                    await target.send(f"⚠️ Your VPS `{vps_name}` was created but failed to start tmate session: `{err or out}`")
                except discord.Forbidden:
                    await ctx.send(f"⚠️ Could not DM the target {target.mention}.")
                return

            # wait for tmate-ready by polling
            waited = 0
            ssh_line = ""
            while waited < TMATE_WAIT_TIMEOUT:
                # check if ready
                cmd_wait = ["docker", "exec", vps_name, "bash", "-c", "tmate -S /tmp/tmate.sock wait tmate-ready || true; tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}' || true"]
                rc2, out2, err2 = await run_cmd(*cmd_wait)
                out2 = out2.strip()
                if out2:
                    ssh_line = out2.splitlines()[-1].strip()
                    break
                await asyncio.sleep(1)
                waited += 1

            if not ssh_line:
                # give one more try to gather logs for debugging
                _, logs, _ = await run_cmd("docker", "logs", vps_name)
                STATE[vps_name]["tmate_ssh"] = None
                save_state()
                try:
                    await target.send(f"⚠️ tmate did not become ready within {TMATE_WAIT_TIMEOUT}s for VPS `{vps_name}`. Container is running. Logs:\n```\n{logs[:1900]}\n```")
                except discord.Forbidden:
                    await ctx.send(f"⚠️ Could not DM the target {target.mention}.")
                return

            # Success
            STATE[vps_name]["tmate_ssh"] = ssh_line
            save_state()

            # DM the target the details
            dm_text = (
                f"🔔 **Your VPS is ready!**\n"
                f"Name: `{vps_name}`\n"
                f"Specs: {ram} RAM, {cores} cores, {disk} {storage_type}\n"
                f"SSH (via tmate): `{ssh_line}`\n"
                f"SSH prompt will be: `root@{vps_name}:~#`\n\n"
                f"To stop the VPS: use the server command `!stop-vps {vps_name}` (or ask an admin)."
            )
            try:
                await target.send(dm_text)
            except discord.Forbidden:
                await ctx.send(f"⚠️ Could not DM the target {target.mention}. They may have DMs closed.")
        except Exception as e:
            # catch-all to avoid unhandled exceptions
            STATE[vps_name]["tmate_ssh"] = None
            save_state()
            try:
                await target.send(f"⚠️ Unexpected error while preparing VPS `{vps_name}`: {e}")
            except:
                pass

    # Schedule task but don't await (so the command returns quickly)
    bot.loop.create_task(setup_tmate_and_dm())

@bot.command(name="stop-vps")
@commands.guild_only()
async def stop_vps(ctx, vps_name: str):
    """Stops and removes VPS by name. Only owner or server admin can stop."""
    if vps_name not in STATE:
        await ctx.send(f"⚠️ No VPS with name `{vps_name}` found.")
        return

    entry = STATE[vps_name]
    owner_id = entry.get("owner_id")
    # allow stop if command author is owner or has manage_guild/admin perms
    if ctx.author.id != owner_id and not is_admin_or_owner(ctx):
        await ctx.send("⛔ You don't have permission to stop this VPS (only the owner or server admins can).")
        return

    # Stop container
    rc, out, err = await run_cmd("docker", "stop", vps_name, timeout=10)
    if rc == 0:
        # remove state
        STATE.pop(vps_name, None)
        save_state()
        await ctx.send(f"🛑 VPS `{vps_name}` stopped and removed.")
    else:
        await ctx.send(f"⚠️ Failed to stop container `{vps_name}`: `{err or out}`")

@bot.command(name="list")
@commands.guild_only()
async def list_vps(ctx, scope: str = "mine"):
    """
    !list          -> shows VPS created by the command user (default 'mine')
    !list all      -> shows all VPS (admins)
    !list mine     -> same as default
    """
    if scope not in ("mine", "all"):
        await ctx.send("Usage: `!list` or `!list all` (admins only)")
        return

    if scope == "all":
        if not is_admin_or_owner(ctx):
            await ctx.send("⛔ You must be a server admin to use `!list all`.")
            return
        entries = STATE.items()
        title = "All VPS (server-wide)"
    else:
        # mine
        uid = ctx.author.id
        entries = [(k, v) for k, v in STATE.items() if v.get("owner_id") == uid]
        title = f"VPS owned by {ctx.author.display_name}"

    if not entries:
        await ctx.send("No VPS found for that scope.")
        return

    embed = discord.Embed(title=title, color=discord.Color.green(), timestamp=datetime.utcnow())
    for name, info in entries:
        owner_name = info.get("owner_name", "unknown")
        created = info.get("created_at", "unknown")
        tmate = info.get("tmate_ssh") or "pending..."
        value = (
            f"Owner: {owner_name}\n"
            f"Created: {created}\n"
            f"Specs: {info.get('ram')} RAM, {info.get('cores')} cores, {info.get('disk')} {info.get('storage_type')}\n"
            f"SSH: `{tmate}`\n"
            f"Container: `{info.get('container_id')[:12]}`"
        )
        embed.add_field(name=name, value=value, inline=False)

    await ctx.send(embed=embed)

@bot.command(name="help-kvm")
async def help_kvm(ctx):
    embed = discord.Embed(title="📜 VPS Bot Commands", color=discord.Color.blue())
    embed.add_field(
        name="!create-vps <ram> <cores> <disk> <SSD/HDD> [@user] <vps_name>",
        value="Create a container-based VPS and DM the target when ready. Example: `!create-vps 2G 2 20G SSD @User myvps`",
        inline=False
    )
    embed.add_field(
        name="!stop-vps <vps_name>",
        value="Stop and remove a VPS. Only owner or admins can stop.",
        inline=False
    )
    embed.add_field(
        name="!list [mine|all]",
        value="List VPS you created (default) or `all` (admins only).",
        inline=False
    )
    await ctx.send(embed=embed)

# Run
if __name__ == "__main__":
    if TOKEN == "YOUR_DISCORD_BOT_TOKEN_HERE":
        print("⚠️ Please set your bot token in the TOKEN variable or set env var VPS_BOT_TOKEN.")
    bot.run(TOKEN)
