#!/usr/bin/env bash
set -e
echo "=== VPS Bot installer ==="

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root: sudo ./install.sh"
  exit 1
fi

apt-get update -y
apt-get upgrade -y

echo "Installing required packages..."
apt-get install -y python3 python3-pip docker.io

echo "Enabling & starting docker..."
systemctl enable docker
systemctl start docker

echo "Installing python packages..."
pip3 install -r requirements.txt

echo "Building docker image..."
docker build -t ubuntu-tmate .

echo "Done. Edit vps_bot.py to set your bot token (or set env var VPS_BOT_TOKEN) and run: python3 vps_bot.py"
