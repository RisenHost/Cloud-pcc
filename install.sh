#!/bin/bash
echo "🚀 Starting installation..."

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install required packages
echo "📦 Installing dependencies..."
pip install discord.py python-dotenv colorama

# Create .env if missing
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    read -p "Enter your bot token: " TOKEN
    echo "DISCORD_TOKEN=$TOKEN" > .env
    echo "✅ Token saved in .env"
else
    echo "ℹ️  .env already exists."
fi

echo "🎉 Installation complete! Run ./start.sh to launch your bot."
