#!/bin/bash
clear
echo "🚀 VPS Bot Installer"
sleep 1

# Update system
echo "📦 Updating system..."
sudo apt-get update -y && sudo apt-get upgrade -y

# Install dependencies
echo "⚙ Installing dependencies..."
sudo apt-get install -y python3 python3-pip docker.io git

# Install Python packages
echo "🐍 Installing Python packages..."
pip3 install -r requirements.txt

# Create .env
echo "🔑 Enter your Discord bot token:"
read token
echo "DISCORD_TOKEN=$token" > .env

# Start Docker
echo "🐳 Starting Docker..."
sudo systemctl enable docker
sudo systemctl start docker

# Build Docker image
echo "🏗 Building VPS container image..."
sudo docker build -t ubuntu-tmate .

echo "✅ Installation complete!"
echo "➡ Run: python3 vps_bot.py"
