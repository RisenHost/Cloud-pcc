#!/usr/bin/env bash
set -e
# Minimal installer: creates venv, installs requirements, prompts token -> writes .env

if [ "$(id -u)" -ne 0 ]; then
  SUDO=sudo
else
  SUDO=
fi

echo "Updating package lists (best-effort)..."
$SUDO apt-get update -y || true

echo "Installing python3, pip and git (best-effort)..."
$SUDO apt-get install -y python3 python3-venv python3-pip git || true

echo "Creating python virtualenv 'venv'..."
python3 -m venv venv

echo "Activating venv and installing Python packages..."
. venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# create .env if missing
if [ -f .env ]; then
  echo ".env already exists - skipping token prompt."
else
  read -p "Enter your Discord Bot Token (kept in .env): " TOKEN
  echo "VPS_BOT_TOKEN=${TOKEN}" > .env
  echo ".env created."
fi

echo "Build docker image (optional) if Docker is available..."
if command -v docker &> /dev/null; then
  docker build -t ubuntu-tmate . || true
fi

echo "Installation finished. To run the bot:"
echo "  source venv/bin/activate"
echo "  python3 vps_bot.py"
