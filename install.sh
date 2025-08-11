#!/bin/bash

# Colors
GREEN="\e[32m"
YELLOW="\e[33m"
CYAN="\e[36m"
RED="\e[31m"
RESET="\e[0m"

clear
echo -e "${CYAN}===================================================="
echo -e "   🚀 Discord VPS Bot Installer"
echo -e "====================================================${RESET}"

# Spinner animation function
spinner() {
    local pid=$!
    local delay=0.1
    local spinstr='|/-\'
    while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

# Update & install dependencies
echo -e "${YELLOW}📦 Updating system & installing dependencies...${RESET}"
sudo apt update -y &> /dev/null && sudo apt upgrade -y &> /dev/null &
spinner
sudo apt install -y python3 python3-pip python3-venv git &> /dev/null &
spinner

# Optional Docker install (if VPS bot uses it)
echo -e "${YELLOW}🐳 Installing Docker...${RESET}"
sudo apt install -y docker.io docker-compose &> /dev/null &
spinner
sudo systemctl enable docker &> /dev/null
sudo systemctl start docker &> /dev/null

# Create Python virtual environment
echo -e "${YELLOW}📂 Setting up Python environment...${RESET}"
python3 -m venv venv &> /dev/null &
spinner
source venv/bin/activate
pip install -r requirements.txt &> /dev/null &
spinner

# Ask for bot token
echo -ne "${GREEN}🔑 Enter your Discord bot token: ${RESET}"
read TOKEN

# Save .env file
echo -e "${YELLOW}💾 Creating .env file...${RESET}"
cat <<EOL > .env
DISCORD_TOKEN=$TOKEN
EOL

# Create start.sh
echo -e "${YELLOW}⚙ Creating start.sh...${RESET}"
cat <<EOL > start.sh
#!/bin/bash
source venv/bin/activate
python3 vps_bot.py
EOL
chmod +x start.sh

# Done
echo -e "${GREEN}✅ Installation complete!"
echo -e "   Run the bot with: ${CYAN}./start.sh${RESET}"
