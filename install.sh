#!/usr/bin/env bash
set -e
GREEN="\e[32m"; CYAN="\e[36m"; RED="\e[31m"; RESET="\e[0m"

echo -e "${CYAN}🚀 Installing VPS Bot...${RESET}"

# Step 1: Install deps
echo -e "${GREEN}📦 Installing dependencies...${RESET}"
apt-get update -y
apt-get install -y python3 python3-pip python3-venv docker.io

# Step 2: Build VPS Docker image
echo -e "${GREEN}🐳 Building Docker image for VPS containers...${RESET}"
docker build -t ubuntu-22.04-with-tmate .

# Step 3: Python env
echo -e "${GREEN}🐍 Setting up Python virtual environment...${RESET}"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Step 4: Create .env
if [ ! -f .env ]; then
  echo -e "${GREEN}🔑 Enter your Discord bot token:${RESET}"
  read TOKEN
  echo "VPS_BOT_TOKEN=${TOKEN}" > .env
  echo -e "${GREEN}✅ Saved to .env${RESET}"
fi

echo -e "${CYAN}🎉 Installation complete!${RESET}"
echo -e "${GREEN}Run the bot with:${RESET} source venv/bin/activate && python3 bot.py"
