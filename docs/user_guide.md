# Child Welfare Case Manager User Guide

## Overview
This app helps parents fight for reunification in child welfare cases (e.g., CHINS, CPS). It organizes evidence, detects lies, tracks deadlines, and drafts motions for any state. Goal: Get your kids back by proving compliance and countering agency failures.

**Disclaimer**: Not legal advice. Consult an attorney. Evidence organization tool only.

## Quick Start
1. Install: `pip install -r requirements.txt`
2. Run: `python src/case_manager.py`
3. Enter state (e.g., California), API key (Grok/OpenAI), password (encrypts data).

## Features
### 1. Evidence Organization
- Upload audio (e.g., Cube Call Recorder), video, images, documents.
- Categories: Tag as "Therapy Notes", "Call Logs", etc.
- Contacts: Auto-adds names; label messages.

### 2. Timeline & Calendar
- Tracks visits, services, deadlines (e.g., hearing dates).
- Add events: "2025-11-01: Therapy session completed".

### 3. Lie Detection
- Analyzes data for inconsistencies (e.g., agency claims vs. call logs).
- Covers all parties: agency, GAL, foster parent, opposing party, judge.
- Run: "Reports > Detect Lies by All Parties" – PDF output.

### 4. Reports & Search
- Custom reports: Filter by type (visits, messages).
- Search: Keyword/person – export PDF for court.

### 5. Motions & Legal Tools
- Drafts:
  - **Concurrent Plan**: Reunification primary, guardianship secondary.
  - **Oppose Adoption**: Argues reunification priority.
  - **Guardianship**: For fit relatives.
  - **Contempt/Mandamus/Medication**: For agency violations, delays, disputes.
- Run: "Legal Tools > concurrent_plan" – PDF with state-specific citations.
- Fetches state laws, forms via web search.

### 6. Placement Candidates
- Add relatives (e.g., grandparent: stable home).
- Use in guardianship motions.

### 7. Sync & Share
- "Setup > Sync Cloud" – Encrypted Google Drive upload for lawyer sharing.

## Tips
- Gather evidence: Audio of agency calls, therapy notes, call logs.
- Counter agency: Use lie detection for contradictions.
- Reunification: Show compliance (e.g., completed services); propose relative guardianship.
- Legal aid: Search "[Your State] child welfare legal aid" in app.

## Troubleshooting
- API: Get free Grok key (x.ai/api) or OpenAI key (platform.openai.com).
- Media: Ensure clear audio/video for transcription.
- Support: Open GitHub issues.
