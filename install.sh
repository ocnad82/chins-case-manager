#!/bin/bash

# Child Welfare Case Manager Installation Script for Ubuntu
# Run: chmod +x install.sh && ./install.sh
# Fixed: dropbox==12.2.1 (non-existent) to 12.0.2; pysqlcipher3>=1.0.0; supports Ubuntu 20.04/22.04/24.04

# Exit on error
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting installation for Child Welfare Case Manager...${NC}"

# Step 1: Check for requirements.txt
if [ ! -f requirements.txt ]; then
    echo -e "${RED}Error: requirements.txt not found in $(pwd)! Please create it with the correct dependencies.${NC}"
    echo "Expected content includes: dropbox==12.0.2, pysqlcipher3>=1.0.0, kivy==2.3.0, etc. See documentation."
    exit 1
fi

# Step 2: Update system and install prerequisites
echo -e "${GREEN}Updating system and installing prerequisites...${NC}"
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv build-essential libssl-dev libffi-dev python3-dev pkg-config

# Step 3: Install FFmpeg for audio/video processing
echo -e "${GREEN}Installing FFmpeg...${NC}"
sudo apt install -y ffmpeg

# Step 4: Install Tesseract for OCR
echo -e "${GREEN}Installing Tesseract-OCR...${NC}"
sudo apt install -y tesseract-ocr libtesseract-dev

# Step 5: Install SQLCipher for encrypted database
echo -e "${GREEN}Installing SQLCipher...${NC}"
sudo apt install -y libsqlcipher-dev libsqlite3-dev

# Step 6: Clean and create virtual environment
echo -e "${GREEN}Setting up Python virtual environment...${NC}"
if [ -d "venv" ]; then
    echo -e "${YELLOW}Removing existing virtual environment to avoid conflicts...${NC}"
    rm -rf venv
fi
python3 -m venv venv
source venv/bin/activate

# Step 7: Install Python dependencies
echo -e "${GREEN}Installing Python dependencies from requirements.txt...${NC}"
pip install --upgrade pip
if ! pip install -r requirements.txt; then
    echo -e "${YELLOW}Warning: Failed to install some dependencies. Trying pysqlcipher3-binary as fallback...${NC}"
    sed -i 's/pysqlcipher3>=1.0.0/pysqlcipher3-binary>=1.0.0/' requirements.txt
    pip install -r requirements.txt
fi

# Step 8: Install Kivy dependencies
echo -e "${GREEN}Installing Kivy dependencies...${NC}"
sudo apt install -y libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev

# Step 9: Prompt for Google Drive API credentials
echo -e "${GREEN}Setting up Google Drive API credentials...${NC}"
if [ ! -f "credentials.json" ]; then
    echo -e "${YELLOW}Download your Google Drive API 'credentials.json' from https://console.cloud.google.com${NC}"
    echo "1. Create a project, enable Drive API, create OAuth 2.0 Client ID (Desktop app)."
    echo "2. Download credentials.json and place it in $(pwd)."
    read -p "Have you placed credentials.json in $(pwd)? (y/n): " answer
    if [ "$answer" != "y" ]; then
        echo -e "${YELLOW}Warning: No credentials.json – Google Drive sync will be disabled.${NC}"
    else
        echo -e "${GREEN}credentials.json found!${NC}"
    fi
else
    echo -e "${GREEN}credentials.json found!${NC}"
fi

# Step 10: Verify installation
echo -e "${GREEN}Verifying installation...${NC}"
if python3 -c "import kivy, requests, bs4, reportlab, PyPDF2, docx, pytesseract, PIL, dateutil, speech_recognition, googleapiclient, google.auth, pysqlcipher3, dropbox, ffmpeg, moviepy, openai" 2>/dev/null; then
    echo -e "${GREEN}Success! All Python dependencies installed correctly.${NC}"
else
    echo -e "${RED}Error: Some dependencies failed to install. Check logs above or try: pip install pysqlcipher3-binary${NC}"
    echo -e "${YELLOW}Fallback: You can edit src/case_manager.py to use 'import sqlite3' instead of 'pysqlcipher3' (disables encryption).${NC}"
    exit 1
fi

# Step 11: Instructions for running the app
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo -e "${YELLOW}To run the app:${NC}"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Run the app: python src/case_manager.py"
echo "3. Enter your state (e.g., California), API key (Grok: x.ai/api, OpenAI: platform.openai.com), and password."
echo "4. For state-specific laws, ensure internet connection for web searches."
echo ""
echo -e "${YELLOW}Notes:${NC}"
echo "- If issues persist, try: pip install pysqlcipher3-binary or pip install dropbox==12.0.2"
echo "- For mobile packaging (Android/iOS), see docs/mobile_setup.md (if added)."
echo "- Test with: source venv/bin/activate && python src/case_manager.py"
echo ""
echo -e "${GREEN}Setup complete! Ready to help parents organize evidence and fight for reunification.${NC}"

# Deactivate virtual environment
deactivate
