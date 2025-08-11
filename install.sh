#!/bin/bash
set -e

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

# --- Animated echo ---
function step() {
    echo -e "${CYAN}[*] $1${NC}"
    sleep 0.5
}

function success() {
    echo -e "${GREEN}[✓] $1${NC}"
    sleep 0.3
}

clear
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}      VPS Bot Auto Installer v2         ${NC}"
echo -e "${GREEN}========================================${NC}"
sleep 1

step "Updating system packages..."
sudo apt-get update -y || true
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y \
    -o Dpkg::Options::="--force-confdef" \
    -o Dpkg::Options::="--force-confold" || true
success "System updated."

step "Installing dependencies..."
sudo apt-get install -y \
    python3 python3-pip \
    docker.io docker-compose \
    openssh-server curl tmux tmate || true
success "Dependencies installed."

# Fix git conflict in Codesandbox/GitHub
step "Installing Git (safe mode)..."
sudo apt-get remove -y git || true
sudo apt-get install -y git --fix-missing || true
success "Git installed."

# SSH Config
step "Configuring SSH..."
sudo mkdir -p /var/run/sshd
sudo sed -i 's/#\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sudo sed -i 's/#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
success "SSH configured."

# Docker handling
step "Starting Docker..."
if command -v systemctl &> /dev/null; then
    sudo systemctl enable docker || true
    sudo systemctl start docker || true
elif command -v service &> /dev/null; then
    sudo service docker start || true
else
    sudo dockerd > /dev/null 2>&1 &
fi
success "Docker started."

# SSH restart
if command -v systemctl &> /dev/null; then
    sudo systemctl restart ssh || true
elif command -v service &> /dev/null; then
    sudo service ssh restart || true
fi
success "SSH restarted."

# Python deps
step "Installing Python packages..."
pip3 install --upgrade pip
pip3 install discord.py docker python-dotenv
success "Python packages installed."

# Save bot token
step "Configuring bot token..."
read -p "Enter your Discord Bot Token: " BOT_TOKEN
echo "BOT_TOKEN=\"$BOT_TOKEN\"" > .env
success "Bot token saved."

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${CYAN}Run your bot: python3 vps_bot.py${NC}"
echo -e "${GREEN}========================================${NC}"
