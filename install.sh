#!/bin/bash
set -e

echo "[*] Updating system..."
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y \
    -o Dpkg::Options::="--force-confdef" \
    -o Dpkg::Options::="--force-confold"

echo "[*] Installing dependencies..."
sudo apt-get install -y \
    python3 python3-pip \
    docker.io docker-compose \
    openssh-server curl git tmux tmate

echo "[*] Configuring SSH..."
sudo mkdir -p /var/run/sshd
sudo sed -i 's/#\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sudo sed -i 's/#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config || true

# Detect environment and start Docker
echo "[*] Starting Docker..."
if command -v systemctl &> /dev/null; then
    sudo systemctl enable docker || true
    sudo systemctl start docker || true
elif command -v service &> /dev/null; then
    sudo service docker start || true
else
    echo "[!] systemctl/service not found, starting dockerd in background..."
    sudo dockerd > /dev/null 2>&1 &
fi

# Restart SSH only if possible
if command -v systemctl &> /dev/null; then
    sudo systemctl restart ssh || true
elif command -v service &> /dev/null; then
    sudo service ssh restart || true
else
    echo "[!] Cannot restart SSH service in this environment."
fi

echo "[*] Installing Python requirements..."
pip3 install --upgrade pip
pip3 install discord.py docker

# Ask for bot token and save it
read -p "Enter your Discord Bot Token: " BOT_TOKEN
echo "BOT_TOKEN=\"$BOT_TOKEN\"" > .env

echo "[*] Installation complete!"
echo "Run your bot with: python3 vps_bot.py"
