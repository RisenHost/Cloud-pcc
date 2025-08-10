#!/bin/bash
clear
echo "===================================="
echo "  Discord VPS Bot Installer"
echo "  Powered by Docker + tmate"
echo "===================================="

if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (sudo bash install.sh)"
    exit
fi

echo "📦 Updating system..."
apt-get update -y
apt-get upgrade -y

echo "📦 Installing dependencies..."
apt-get install -y python3 python3-pip docker.io git

systemctl enable docker
systemctl start docker

pip3 install discord.py

echo "🐳 Building ubuntu-tmate Docker image..."
docker build -t ubuntu-tmate .

echo "✅ Installation complete!"
echo "💡 To run your bot: python3 vps_bot.py"
