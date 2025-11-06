#!/bin/bash

# Child Welfare Case Manager Installation Script for Ubuntu
# Run: chmod +x install.sh && ./install.sh

# Exit on error
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting installation for Child Welfare Case Manager...${NC}"

# Step 1: Update system and install prerequisites
echo -e "${GREEN}Updating system and installing prerequisites...${NC}"
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv build-essential libssl-dev libffi-dev python3-dev

# Step 2: Install FFmpeg for audio/video processing
echo -e "${GREEN}Installing FFmpeg...${NC}"
sudo apt install -y ffmpeg

# Step 3: Install Tesseract for OCR (text extraction from images)
echo -e "${GREEN}Installing Tesseract-OCR...${NC}"
sudo apt install -y tesseract-ocr libtesseract-dev

# Step 4: Install SQLCipher for encrypted database
echo -e "${GREEN}Installing SQLCipher...${NC}"
sudo apt install -y libsqlcipher-dev

# Step 5: Create and activate virtual environment
echo -e "${GREEN}Setting up Python virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# Step 6: Install Python dependencies
echo -e "${GREEN}Installing Python dependencies from requirements.txt...${NC}"
if [ -f requirements.txt ]; then
    pip install --upgrade pip
    pip install -r requirements.txt
else
    echo -e "${RED}Error: requirements.txt not found! Please ensure it exists in the repository root.${NC}"
    exit 1
fi

# Step 7: Install Kivy dependencies
echo -e "${GREEN}Installing Kivy dependencies...${NC}"
sudo apt install -y libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev

# Step 8: Prompt for Google Drive API credentials
echo -e "${GREEN}Setting up Google Drive API credentials...${NC}"
echo "Please download your Google Drive API 'credentials.json' from https://console.cloud.google.com"
echo "1. Create a project, enable Drive API, and create OAuth 2.0 Client ID (Desktop app)."
echo "2. Download credentials.json and place it in the repository root ($(pwd))."
read -p "Have you placed credentials.json in $(pwd)? (y/n): " answer
if [ "$answer" != "y" ]; then
    echo -e "${RED}Error: Please place credentials.json in $(pwd) and re-run the script.${NC}"
    exit 1
fi

# Step 9: Verify installation
echo -e "${GREEN}Verifying installation...${NC}"
if python3 -c "import kivy, requests, bs4, reportlab, PyPDF2, docx, pytesseract, PIL, dateutil, speech_recognition, googleapiclient, google.auth, pysqlcipher3, dropbox, ffmpeg, moviepy, openai" 2>/dev/null; then
    echo -e "${GREEN}All Python dependencies installed successfully!${NC}"
else
    echo -e "${RED}Error: Some Python dependencies failed to install. Check logs above.${NC}"
    exit 1
fi

# Step 10: Instructions for running the app
echo -e "${GREEN}Installation complete!${NC}"
echo "To run the app:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Run the app: python src/case_manager.py"
echo "3. Enter your state (e.g., California), API key (Grok: x.ai/api, OpenAI: platform.openai.com), and password."
echo "Note: Get free API keys for Grok (x.ai/api) or OpenAI (platform.openai.com) for lie detection and motion drafting."
echo "See docs/user_guide.md for usage instructions."

# Deactivate virtual environment
deactivate

echo -e "${GREEN}Setup complete! Ready to help parents fight for reunification.${NC}"
