# Child Welfare Case Manager

Open-source app to help parents reunify with children in child welfare cases (e.g., CHINS, CPS). Organize evidence, detect lies, draft motions, track deadlines for any state.

## Quick Start
1. Install: `pip install -r requirements.txt`
2. Install FFmpeg: Windows (ffmpeg.org), Linux (`sudo apt install ffmpeg`), macOS (`brew install ffmpeg`).
3. Install Tesseract: Windows (github.com/UB-Mannheim/tesseract), Linux (`sudo apt install tesseract-ocr`), macOS (`brew install tesseract`).
4. Install SQLCipher: Windows (DLL), Linux (`sudo apt install libsqlcipher-dev`), macOS (`brew install sqlcipher`).
5. Get Google Drive `credentials.json` (console.cloud.google.com, Drive API).
6. Run: `python src/case_manager.py`
7. Enter state, API key (Grok/OpenAI), password.

## Features
- Evidence: Audio (Cube Call Recorder), video, images, documents.
- Lie Detection: Agency, GAL, foster parents, judge inconsistencies.
- Motions: Concurrent plans, guardianship, oppose adoption.
- Calendar: Tracks deadlines.
- Sync: Google Drive for lawyer sharing.
- State-Agnostic: Enter your state for tailored laws.

## License
MIT – Free to use/fork.

## Disclaimer
Not legal advice; consult an attorney. For child welfare cases only.
