#!/bin/bash
clear
echo "🚀 Starting VPS Bot installation..."
sleep 1

# Step 1: System update
echo "📦 [1/4] Updating system..."
sudo apt update -y && sudo apt upgrade -y
sleep 1

# Step 2: Install dependencies
echo "⚙️ [2/4] Installing Python, pip, and git..."
sudo apt install -y python3 python3-pip python3-venv git
sleep 1

# Step 3: Create venv and install Python packages
echo "📥 [3/4] Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install requirements if file exists, otherwise create one
if [ ! -f requirements.txt ]; then
    echo "discord.py==2.3.2" > requirements.txt
fi

pip install --upgrade pip
pip install -r requirements.txt
sleep 1

# Step 4: Ask for bot token & save to .env
echo "🔑 [4/4] Enter your Discord bot token:"
read BOT_TOKEN
echo "TOKEN=\"$BOT_TOKEN\"" > .env

# Done
echo "✅ Installation complete!"
echo "To start the bot, run: ./start.sh"
