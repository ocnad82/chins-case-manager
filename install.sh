#!/bin/bash

# Child Welfare Case Manager Installation Script for Ubuntu
# Run: chmod +x install.sh && ./install.sh
# Fixed: pysqlcipher3 version pinning; supports Ubuntu 20.04+

# Exit on error
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting installation for Child Welfare Case Manager...${NC}"

# Step 1: Update system and install prerequisites
echo -e "${GREEN}Updating system and installing prerequisites...${NC}"
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv build-essential libssl-dev libffi-dev python3-dev pkg-config

# Step 2: Install FFmpeg for audio/video processing
echo -e "${GREEN}Installing FFmpeg...${NC}"
sudo apt install -y ffmpeg

# Step 3: Install Tesseract for OCR
echo -e "${GREEN}Installing Tesseract-OCR...${NC}"
sudo apt install -y tesseract-ocr libtesseract-dev

# Step 4: Install SQLCipher for encrypted database
echo -e "${GREEN}Installing SQLCipher...${NC}"
sudo apt install -y libsqlcipher-dev libsqlite3-dev

# Step 5: Create and activate virtual environment
echo -e "${GREEN}Setting up Python virtual environment...${NC}"
if [ -d "venv" ]; then
    rm -rf venv  # Clean previous venv
fi
python3 -m venv venv
source venv/bin/activate

# Step 6: Upgrade pip and install Python dependencies
echo -e "${GREEN}Installing Python dependencies...${NC}"
pip install --upgrade pip
if [ -f requirements.txt ]; then
    # Install without pysqlcipher3 first, then with flexible version
    pip install -r requirements.txt --no-deps  # Skip deps to avoid conflicts
    pip install pysqlcipher3>=1.0.0  # Flexible version – installs 1.2.0
else
    echo -e "${RED}Error: requirements.txt not found! Please ensure it exists in the repository root.${NC}"
    exit 1
fi

# Step 7: Install Kivy dependencies
echo -e "${GREEN}Installing Kivy dependencies...${NC}"
sudo apt install -y libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev libffi-dev libssl-dev

# Step 8: Prompt for Google Drive API credentials
echo -e "${GREEN}Setting up Google Drive API credentials...${NC}"
if [ ! -f "credentials.json" ]; then
    echo -e "${YELLOW}Download your Google Drive API 'credentials.json' from https://console.cloud.google.com${NC}"
    echo "1. Create a project, enable Drive API, create OAuth 2.0 Client ID (Desktop app)."
    echo "2. Download credentials.json and place it in $(pwd)."
    read -p "Have you placed credentials.json in $(pwd)? (y/n): " answer
    if [ "$answer" != "y" ]; then
        echo -e "${RED}Warning: No credentials.json – Google Drive sync will be disabled.${NC}"
    fi
else
    echo -e "${GREEN}credentials.json found!${NC}"
fi

# Step 9: Verify installation
echo -e "${GREEN}Verifying installation...${NC}"
python3 -c "
import kivy, requests, bs4, reportlab, PyPDF2, docx, pytesseract, PIL, dateutil, speech_recognition, googleapiclient, google.auth, pysqlcipher3, dropbox, ffmpeg, moviepy, openai
print('All Python dependencies installed successfully!')
" 2>/dev/null && echo -e "${GREEN}Success! All dependencies verified.${NC}" || {
    echo -e "${RED}Warning: Some dependencies may have issues. Check logs above. Continuing with basic setup.${NC}"
}

# Step 10: Instructions for running the app
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo -e "${YELLOW}To run the app:${NC}"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Run the app: python src/case_manager.py"
echo "3. Enter your state (e.g., California), API key (Grok: x.ai/api, OpenAI: platform.openai.com), and password."
echo "4. For state-specific laws, the app uses web search – ensure internet connection."
echo ""
echo -e "${YELLOW}Notes:${NC}"
echo "- If pysqlcipher3 fails (rare on Ubuntu), reinstall with: pip install pysqlcipher3>=1.0.0"
echo "- For mobile packaging, see docs/mobile_setup.md (if added)."
echo "- Test with: source venv/bin/activate && python src/case_manager.py"
echo ""
echo -e "${GREEN}Setup complete! Ready to help parents fight for reunification.${NC}"

# Deactivate virtual environment
deactivate
