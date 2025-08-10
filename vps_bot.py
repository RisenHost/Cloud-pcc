import discord
from discord.ext import commands
import subprocess

TOKEN = "YOUR_DISCORD_BOT_TOKEN"  # <-- Replace with your token

bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

@bot.command(name="create-vps")
async def create_vps(ctx, ram, cores, disk, storage_type, customer_name, vps_name):
    await ctx.send(f"Creating VPS `{vps_name}` for {customer_name}...")

    subprocess.run([
        "docker", "run", "-d", "--rm",
        "--name", vps_name,
        "--hostname", vps_name,
        "--memory", ram,
        "--cpus", cores,
        "ubuntu-tmate"
    ])

    ssh_output = subprocess.check_output([
        "docker", "exec", vps_name, "bash", "-c",
        "tmate -S /tmp/tmate.sock new-session -d && "
        "tmate -S /tmp/tmate.sock wait tmate-ready && "
        "tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}'"
    ]).decode().strip()

    try:
        dm_channel = await ctx.author.create_dm()
        await dm_channel.send(
            f"Hello {customer_name}, your VPS `{vps_name}` is ready!\n"
            f"Specs: {ram} RAM, {cores} cores, {disk} {storage_type}\n"
            f"SSH: `{ssh_output}`\n"
            f"Prompt will be: root@{vps_name}:~#"
        )
        await ctx.send("✅ VPS info sent to your DM.")
    except discord.Forbidden:
        await ctx.send("⚠️ Could not send DM — please enable DMs from server members.")

@bot.command(name="stop-vps")
async def stop_vps(ctx, vps_name):
    try:
        subprocess.run(["docker", "stop", vps_name], check=True)
        await ctx.send(f"🛑 VPS `{vps_name}` has been stopped and removed.")
    except subprocess.CalledProcessError:
        await ctx.send(f"⚠️ No running VPS found with name `{vps_name}`.")

@bot.command(name="help-kvm")
async def help_kvm(ctx):
    embed = discord.Embed(
        title="📜 Bot Command List",
        description="Here are the available commands and their features:",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="!create-vps `<ram>` `<cores>` `<disk>` `<SSD/HDD>` `<customer_name>` `<vps_name>`",
        value="Creates a Docker-based Ubuntu VPS with given specs and sends tmate SSH info via DM.\n"
              "**Example:** `!create-vps 2G 2 20G SSD JohnDoe myvps`",
        inline=False
    )
    embed.add_field(
        name="!stop-vps `<vps_name>`",
        value="Stops and removes a VPS container by name.\n"
              "**Example:** `!stop-vps myvps`",
        inline=False
    )
    embed.add_field(
        name="!help-kvm",
        value="Shows this help menu with all available commands.",
        inline=False
    )
    embed.set_footer(text="⚡ VPS Bot • Powered by Docker + tmate")
    await ctx.send(embed=embed)

bot.run(TOKEN)
