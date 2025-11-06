import sqlite3
import os
import re
from datetime import datetime, timedelta
import kivy
kivy.require('2.3.0')
from kivy.app import App
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.camera import Camera
from kivy.uix.spinner import Spinner
from kivy.utils import platform
from dateutil import parser
import pysqlcipher3.dbapi2 as sqlcipher
import PyPDF2
from docx import Document
import pytesseract
from PIL import Image
import requests
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import json
import zipfile
import shutil
import speech_recognition as sr
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload
import csv
import ffmpeg
import moviepy.editor as mp
from openai import OpenAI

# Config
CONFIG_FILE = 'config.json'
SCOPES = ['https://www.googleapis.com/auth/drive.file']
MEDIA_FORMATS = {
    'audio': ['.mp3', '.wav', '.aac', '.m4a', '.amr', '.ogg', '.flac'],
    'video': ['.mp4', '.avi', '.mov', '.wmv', '.mkv', '.flv'],
    'image': ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.heic']
}

# Initialize Config
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {'api_key': '', 'api_type': 'grok', 'state': ''}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

# API Client
def get_api_client():
    config = load_config()
    api_key = config.get('api_key')
    api_type = config.get('api_type', 'grok')
    if not api_key:
        return None
    if api_type == 'grok':
        return OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
    return OpenAI(api_key=api_key)

def call_grok_api(client, prompt):
    if not client:
        return "API key missing. Configure in Settings."
    try:
        response = client.chat.completions.create(
            model="grok-beta" if client.base_url == "https://api.x.ai/v1" else "gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"API error: {e}"

# Encrypted DB
def init_db(password):
    conn = sqlcipher.connect('case_manager.db')
    c = conn.cursor()
    c.execute(f"PRAGMA key = '{password}'")
    c.execute('''CREATE TABLE IF NOT EXISTS cases (
        case_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_number TEXT,
        case_type TEXT,
        description TEXT,
        state TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS contacts (
        contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER,
        name TEXT,
        email TEXT,
        phone TEXT,
        role TEXT,
        FOREIGN KEY(case_id) REFERENCES cases(case_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS documents (
        doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER,
        doc_name TEXT,
        content TEXT,
        file_path TEXT,
        upload_date TEXT,
        is_transcript INTEGER,
        is_dcs_report INTEGER,
        is_image INTEGER,
        is_therapy_note INTEGER,
        is_medical INTEGER,
        is_police_report INTEGER,
        is_audio INTEGER,
        is_video INTEGER,
        category TEXT,
        FOREIGN KEY(case_id) REFERENCES cases(case_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS call_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER,
        call_date TEXT,
        caller TEXT,
        callee TEXT,
        duration TEXT,
        type TEXT,
        FOREIGN KEY(case_id) REFERENCES cases(case_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS services (
        service_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER,
        service_type TEXT,
        start_date TEXT,
        end_date TEXT,
        provider TEXT,
        status TEXT,
        notes TEXT,
        FOREIGN KEY(case_id) REFERENCES cases(case_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS text_messages (
        msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER,
        msg_date TEXT,
        sender_id INTEGER,
        recipient_id INTEGER,
        content TEXT,
        is_image INTEGER,
        FOREIGN KEY(case_id) REFERENCES cases(case_id),
        FOREIGN KEY(sender_id) REFERENCES contacts(contact_id),
        FOREIGN KEY(recipient_id) REFERENCES contacts(contact_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS emails (
        email_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER,
        email_date TEXT,
        sender_id INTEGER,
        recipient_id INTEGER,
        subject TEXT,
        content TEXT,
        is_image INTEGER,
        FOREIGN KEY(case_id) REFERENCES cases(case_id),
        FOREIGN KEY(sender_id) REFERENCES contacts(contact_id),
        FOREIGN KEY(recipient_id) REFERENCES contacts(contact_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER,
        event_date TEXT,
        description TEXT,
        source_type TEXT,
        source_id INTEGER,
        FOREIGN KEY(case_id) REFERENCES cases(case_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS inconsistencies (
        inc_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER,
        description TEXT,
        detected_date TEXT,
        party TEXT,
        FOREIGN KEY(case_id) REFERENCES cases(case_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS legal_strategies (
        strat_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER,
        strategy_type TEXT,
        content TEXT,
        source TEXT,
        fetch_date TEXT,
        FOREIGN KEY(case_id) REFERENCES cases(case_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS calendar_events (
        cal_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER,
        event_date TEXT,
        event_type TEXT,
        description TEXT,
        is_deadline INTEGER,
        FOREIGN KEY(case_id) REFERENCES cases(case_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS pre_case_context (
        context_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER,
        event_date TEXT,
        description TEXT,
        file_path TEXT,
        file_type TEXT,
        FOREIGN KEY(case_id) REFERENCES cases(case_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS placement_candidates (
        candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER,
        name TEXT,
        relationship TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        suitability_notes TEXT,
        FOREIGN KEY(case_id) REFERENCES cases(case_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS concurrent_plans (
        plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER,
        primary_plan TEXT,
        secondary_plan TEXT,
        candidate_id INTEGER,
        notes TEXT,
        FOREIGN KEY(case_id) REFERENCES cases(case_id),
        FOREIGN KEY(candidate_id) REFERENCES placement_candidates(candidate_id)
    )''')
    conn.commit()
    return conn

# Security
def authenticate_user():
    if platform in ['android', 'ios']:
        # Placeholder: Implement biometric/PIN via Pyjnius (Android) or Pyobjus (iOS)
        return True
    else:
        # Desktop password prompt (replace with GUI popup)
        return True  # Replace with secure password check

# Cloud Sync
def sync_to_cloud(conn, password, folder_id=None):
    if not os.path.exists('token.json'):
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    service = build('drive', 'v3', credentials=creds)
    conn.execute(f"PRAGMA key = '{password}'")
    conn.backup(sqlcipher.connect('temp_encrypted.db'))
    file_metadata = {'name': 'case_manager.db', 'parents': [folder_id] if folder_id else []}
    media = MediaFileUpload('temp_encrypted.db', mimetype='application/octet-stream')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    os.remove('temp_encrypted.db')
    return file.get('id')

# Media Extraction
def extract_text(file_path, is_image=False, is_audio=False, is_video=False):
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if is_image:
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img)
            return text if text.strip() else "OCR failed: No text detected."
        if is_audio or is_video:
            output_wav = 'temp_audio.wav'
            if is_video:
                clip = mp.VideoFileClip(file_path)
                clip.audio.write_audiofile(output_wav)
                clip.close()
            else:
                stream = ffmpeg.input(file_path)
                stream = ffmpeg.output(stream, output_wav, acodec='pcm_s16le', ar=16000)
                ffmpeg.run(stream)
            recognizer = sr.Recognizer()
            with sr.AudioFile(output_wav) as source:
                audio = recognizer.record(source)
                text = recognizer.recognize_google(audio)
            os.remove(output_wav)
            return text if text.strip() else "Transcription failed: No text detected."
        if ext == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        elif ext == '.pdf':
            with open(file_path, 'rb') as f:
                pdf = PyPDF2.PdfReader(f)
                return ' '.join(page.extract_text() for page in pdf.pages if page.extract_text())
        elif ext == '.docx':
            doc = Document(file_path)
            return ' '.join(p.text for p in doc.paragraphs)
        return None
    except Exception as e:
        return f"Error processing {file_path}: {e}"

# Call Log Parsing
def parse_call_log(file_path):
    logs = []
    if file_path.endswith('.csv'):
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                logs.append({
                    'date': row['date'],
                    'caller': row['caller'],
                    'callee': row['callee'],
                    'duration': row['duration'],
                    'type': row['type']
                })
    else:
        content = extract_text(file_path, is_image=True)
        for line in content.split('\n'):
            match = re.match(r'(\d{4}-\d{2}-\d{2}) (Incoming|Outgoing|Missed): (\S+) to (\S+), duration (\d+)min', line)
            if match:
                logs.append({
                    'date': match.group(1),
                    'type': match.group(2),
                    'caller': match.group(3),
                    'callee': match.group(4),
                    'duration': match.group(5)
                })
    return logs

def add_call_log(conn, case_id, logs):
    c = conn.cursor()
    for log in logs:
        c.execute('INSERT INTO call_logs VALUES (NULL, ?, ?, ?, ?, ?, ?)',
                  (case_id, log['date'], log['caller'], log['callee'], log['duration'], log['type']))
    conn.commit()

# Auto-Add Contacts
def auto_add_contacts(conn, case_id, content):
    c = conn.cursor()
    names = re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', content)
    emails = re.findall(r'\b[\w\.-]+@[\w\.-]+\.\w+\b', content)
    phones = re.findall(r'\b\d{3}-\d{3}-\d{4}\b', content)
    for name in names:
        c.execute('INSERT OR IGNORE INTO contacts VALUES (NULL, ?, ?, ?, ?, ?)',
                  (case_id, name, '', '', 'Unknown'))
    for email in emails:
        c.execute('INSERT OR IGNORE INTO contacts VALUES (NULL, ?, ?, ?, ?)',
                  (case_id, 'Unknown', email, '', 'Unknown'))
    for phone in phones:
        c.execute('INSERT OR IGNORE INTO contacts VALUES (NULL, ?, ?, ?, ?)',
                  (case_id, 'Unknown', '', phone, 'Unknown'))
    conn.commit()

# Parse Content
def parse_content(content, is_transcript=False, is_dcs_report=False, is_audio=False, is_video=False):
    dates = re.findall(r'\d{4}-\d{2}-\d{2}', content)
    ai_analysis = None
    if load_config().get('api_key'):
        prompt = f"Analyze child welfare case evidence for inconsistencies and patterns (e.g., agency lies, visitation issues): {content[:1000]}"
        ai_analysis = call_grok_api(get_api_client(), prompt)
    return dates, ai_analysis

# Add Document
def add_document(conn, case_id, file_path, is_transcript=False, is_dcs_report=False, is_image=False, is_therapy_note=False, is_medical=False, is_police_report=False, is_audio=False, is_video=False, category=None):
    content = extract_text(file_path, is_image, is_audio, is_video)
    if not content or content.startswith(("Error", "OCR failed", "Transcription failed")):
        return content
    upload_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c = conn.cursor()
    c.execute('''INSERT INTO documents (case_id, doc_name, content, file_path, upload_date, is_transcript, is_dcs_report, is_image, is_therapy_note, is_medical, is_police_report, is_audio, is_video, category)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (case_id, os.path.basename(file_path), content, file_path, upload_date, int(is_transcript), int(is_dcs_report), int(is_image), int(is_therapy_note), int(is_medical), int(is_police_report), int(is_audio), int(is_video), category))
    doc_id = c.lastrowid
    auto_add_contacts(conn, case_id, content)
    dates, ai_analysis = parse_content(content, is_transcript, is_dcs_report, is_audio, is_video)
    for date in dates:
        desc = f"{'Transcript' if is_transcript else 'Agency Report' if is_dcs_report else 'Therapy Note' if is_therapy_note else 'Medical' if is_medical else 'Police Report' if is_police_report else 'Audio' if is_audio else 'Video' if is_video else 'Document'}: {os.path.basename(file_path)}"
        c.execute('INSERT INTO events VALUES (NULL, ?, ?, ?, ?, ?)',
                  (case_id, date, desc, 'document', doc_id))
        c.execute('INSERT INTO calendar_events VALUES (NULL, ?, ?, ?, ?, ?)',
                  (case_id, date, 'document', desc, 0))
    if ai_analysis:
        c.execute('INSERT INTO inconsistencies VALUES (NULL, ?, ?, ?, ?)',
                  (case_id, ai_analysis, upload_date, 'Unknown'))
    conn.commit()
    return "Added successfully"

# Lie Detection
def detect_lies_patterns(conn, case_id):
    data = get_case_data(conn, case_id)
    c = conn.cursor()
    c.execute('SELECT contact_id, name, role FROM contacts WHERE case_id=?', (case_id,))
    parties = c.fetchall()
    results = []
    for contact_id, name, role in parties + [(0, 'Judge', 'Judge'), (0, 'Opposing Party', 'Opposing Party')]:
        prompt = (
            f"Analyze child welfare case data for lies/inconsistencies by {name} ({role}): {data}. "
            f"Cross-reference audio transcripts, videos, call logs, messages, emails, documents, therapy notes, police reports, and pre-case context. "
            f"Highlight contradictions (e.g., agency claims vs. call logs, foster parent interference vs. visit notes)."
        )
        analysis = call_grok_api(get_api_client(), prompt)
        if analysis and not analysis.startswith("API error"):
            c.execute('INSERT INTO inconsistencies VALUES (NULL, ?, ?, ?, ?)',
                      (case_id, analysis, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), name))
            results.append(f"{name} ({role}): {analysis}")
    conn.commit()
    return "\n\n".join(results) if results else "No inconsistencies detected."

# Web Search for Legal Resources
def search_chins_resources(state):
    try:
        query = f"{state} child welfare case law, agency policies, guardianship forms, parenting plan templates, concurrent planning, fit and willing relative"
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        resources = []
        for link in soup.find_all('a')[:5]:
            href = link.get('href')
            if href and 'url?q=' in href:
                clean_url = href.split('url?q=')[1].split('&')[0]
                if any(x in clean_url for x in ['gov', 'courts', 'law.justia.com', 'findlaw.com']):
                    resources.append(clean_url)
        return resources
    except Exception as e:
        return f"Web search error: {e}"

# Motion Drafting
def draft_motion(conn, case_id, motion_type, candidate_id=None):
    data = get_case_data(conn, case_id)
    c = conn.cursor()
    c.execute('SELECT case_number, state FROM cases WHERE case_id=?', (case_id,))
    case = c.fetchone()
    state = case[1] if case else ''
    candidate_info = ''
    if candidate_id:
        c.execute('SELECT name, relationship, suitability_notes FROM placement_candidates WHERE candidate_id=?', (candidate_id,))
        candidate = c.fetchone()
        if candidate:
            candidate_info = f"Candidate: {candidate[0]} ({candidate[1]}), Suitability: {candidate[2]}"
    motion_types = {
        'concurrent_plan': (
            f"Draft a motion to establish a concurrent plan for child welfare case in {state}, "
            f"prioritizing reunification with secondary plan of guardianship with a fit and willing relative ({candidate_info}). "
            f"Use evidence of parental progress (e.g., therapy, visits) and agency failures: {data}"
        ),
        'oppose_adoption': (
            f"Draft a motion to oppose agency's adoption plan in child welfare case in {state}, "
            f"arguing reunification priority and relative guardianship ({candidate_info}) with evidence: {data}"
        ),
        'guardianship': (
            f"Draft a motion for guardianship with a fit and willing relative ({candidate_info}) in child welfare case in {state}, "
            f"using evidence of parental progress and relative suitability: {data}"
        ),
        'contempt': (
            f"Draft a contempt motion for child welfare case in {state}, citing agency or foster parent violations "
            f"(e.g., visitation interference, failure to provide services) with evidence: {data}"
        ),
        'mandamus': (
            f"Draft a writ of mandamus for child welfare case in {state}, compelling agency or court to act "
            f"(e.g., delayed services, hearings) with evidence: {data}"
        ),
        'medication': (
            f"Draft a motion to address medication disputes in child welfare case in {state}, "
            f"using medical records, therapy notes, and parent concerns: {data}"
        )
    }
    prompt = motion_types.get(motion_type, f"Draft a motion for child welfare case in {state} addressing {motion_type}: {data}")
    motion = call_grok_api(get_api_client(), prompt)
    create_pdf(f'motion_{motion_type}_{case_id}_{datetime.now().strftime("%Y%m%d")}.pdf', motion)
    return motion

# PDF Generation
def create_pdf(filename, content):
    c = canvas.Canvas(filename, pagesize=letter)
    c.drawString(100, 750, "CHINS Case Manager Report")
    text = c.beginText(100, 700)
    for line in content.split('\n'):
        text.textLine(line[:100])
    c.drawText(text)
    c.save()

# Get Case Data
def get_case_data(conn, case_id):
    c = conn.cursor()
    data = []
    c.execute('SELECT content FROM documents WHERE case_id=?', (case_id,))
    data.extend([row[0] for row in c.fetchall()])
    c.execute('SELECT content FROM text_messages WHERE case_id=?', (case_id,))
    data.extend([row[0] for row in c.fetchall()])
    c.execute('SELECT content FROM emails WHERE case_id=?', (case_id,))
    data.extend([row[0] for row in c.fetchall()])
    c.execute('SELECT description FROM pre_case_context WHERE case_id=?', (case_id,))
    data.extend([row[0] for row in c.fetchall()])
    return ' '.join([d for d in data if d])

# Report Generation
def generate_custom_report(conn, case_id, data_types=None, include_pre_case=False):
    c = conn.cursor()
    c.execute('SELECT case_number, state FROM cases WHERE case_id=?', (case_id,))
    case = c.fetchone()
    if not case:
        return "Case not found."
    case_number, state = case
    report = f"Custom Report - Case {case_number} (State: {state})\n\n"
    
    data_types = data_types or ['services', 'documents', 'text_messages', 'emails', 'call_logs', 'calendar_events']
    if 'services' in data_types:
        c.execute('SELECT service_type, start_date, status, notes FROM services WHERE case_id=?', (case_id,))
        report += "Services:\n"
        for row in c.fetchall():
            report += f"- {row[0]} ({row[1]}): {row[2]}, {row[3]}\n"
    if 'documents' in data_types:
        c.execute('SELECT doc_name, upload_date, category FROM documents WHERE case_id=?', (case_id,))
        report += "\nDocuments:\n"
        for row in c.fetchall():
            report += f"- {row[0]} ({row[1]}): {row[2]}\n"
    if 'text_messages' in data_types:
        c.execute('SELECT msg_date, content FROM text_messages WHERE case_id=?', (case_id,))
        report += "\nText Messages:\n"
        for row in c.fetchall():
            report += f"- {row[0]}: {row[1][:50]}...\n"
    if 'emails' in data_types:
        c.execute('SELECT email_date, subject, content FROM emails WHERE case_id=?', (case_id,))
        report += "\nEmails:\n"
        for row in c.fetchall():
            report += f"- {row[0]} ({row[1]}): {row[2][:50]}...\n"
    if 'call_logs' in data_types:
        c.execute('SELECT call_date, caller, callee, duration, type FROM call_logs WHERE case_id=?', (case_id,))
        report += "\nCall Logs:\n"
        for row in c.fetchall():
            report += f"- {row[0]}: {row[1]} to {row[2]}, {row[3]}min ({row[4]})\n"
    if 'calendar_events' in data_types:
        c.execute('SELECT event_date, description, is_deadline FROM calendar_events WHERE case_id=?', (case_id,))
        report += "\nCalendar Events:\n"
        for row in c.fetchall():
            report += f"- {row[0]}: {row[1]} {'(Deadline)' if row[2] else ''}\n"
    if include_pre_case:
        c.execute('SELECT event_date, description FROM pre_case_context WHERE case_id=?', (case_id,))
        report += "\nPre-Case Context:\n"
        for row in c.fetchall():
            report += f"- {row[0]}: {row[1]}\n"
    c.execute('SELECT party, description FROM inconsistencies WHERE case_id=?', (case_id,))
    report += "\nLie Detection / Inconsistencies by Party:\n"
    for row in c.fetchall():
        report += f"- {row[0]}: {row[1][:100]}...\n"
    
    if load_config().get('api_key'):
        prompt = f"Enhance child welfare report for court, emphasizing child's best interest, agency failures, and lies by all parties in {state}: {report}"
        report = call_grok_api(get_api_client(), prompt)
    
    return report

# Kivy App
class CaseManagerApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not authenticate_user():
            raise ValueError("Authentication failed")
        self.password = "user_password"  # Replace with GUI/input
        self.conn = init_db(self.password)
        self.current_case_id = None

    def build(self):
        root = TabbedPanel(do_default_tab=False)
        
        # Disclaimer Tab
        disclaimer_tab = TabbedPanelItem(text='About')
        disclaimer_layout = BoxLayout(orientation='vertical', padding=10)
        disclaimer_layout.add_widget(Label(
            text="CHINS Case Manager is not legal advice. Consult an attorney. "
                 "This app organizes evidence for child welfare cases. "
                 "Data is encrypted and private. See GitHub for source.",
            halign='center', valign='middle', text_size=(None, None)
        ))
        root.add_widget(disclaimer_tab)
        
        # Setup Tab
        setup_tab = TabbedPanelItem(text='Setup')
        setup_layout = BoxLayout(orientation='vertical', padding=10)
        self.state_input = TextInput(hint_text='Enter State (e.g., California)', size_hint_y=None, height=50)
        self.api_type = Spinner(values=['grok', 'openai'], text='Select AI: Grok', size_hint_y=None, height=50)
        self.api_key_input = TextInput(hint_text='Enter Grok/OpenAI API Key', size_hint_y=None, height=50)
        self.cloud_folder = TextInput(hint_text='Google Drive Folder ID (optional)', size_hint_y=None, height=50)
        btn_save = Button(text='Save Config', size_hint_y=None, height=50)
        btn_save.bind(on_press=self.save_config)
        btn_sync = Button(text='Sync to Cloud', size_hint_y=None, height=50)
        btn_sync.bind(on_press=self.sync_to_cloud)
        for w in [self.state_input, self.api_type, self.api_key_input, self.cloud_folder, btn_save, btn_sync]:
            setup_layout.add_widget(w)
        setup_tab.add_widget(setup_layout)
        root.add_widget(setup_tab)
        
        # New Case Tab
        case_tab = TabbedPanelItem(text='New Case')
        case_layout = BoxLayout(orientation='vertical', padding=10)
        self.case_number = TextInput(hint_text='Case Number', size_hint_y=None, height=50)
        self.case_type = TextInput(hint_text='Case Type (e.g., CHINS)', size_hint_y=None, height=50)
        self.case_desc = TextInput(hint_text='Description', size_hint_y=None, height=100)
        btn_case = Button(text='Create Case', size_hint_y=None, height=50)
        btn_case.bind(on_press=self.new_case)
        self.case_list = Spinner(values=['Select Case'], text='Select Case', size_hint_y=None, height=50)
        for w in [self.case_number, self.case_type, self.case_desc, btn_case, self.case_list]:
            case_layout.add_widget(w)
        case_tab.add_widget(case_layout)
        root.add_widget(case_tab)
        
        # Contacts Tab
        contacts_tab = TabbedPanelItem(text='Contacts')
        contacts_layout = BoxLayout(orientation='vertical', padding=10)
        self.contact_name = TextInput(hint_text='Name', size_hint_y=None, height=50)
        self.contact_email = TextInput(hint_text='Email', size_hint_y=None, height=50)
        self.contact_phone = TextInput(hint_text='Phone', size_hint_y=None, height=50)
        self.contact_role = TextInput(hint_text='Role (e.g., Case Worker)', size_hint_y=None, height=50)
        btn_contact = Button(text='Add Contact', size_hint_y=None, height=50)
        btn_contact.bind(on_press=self.add_contact)
        self.contacts_list = Label(text='', halign='left', valign='top', text_size=(None, None))
        scroll = ScrollView()
        scroll.add_widget(self.contacts_list)
        for w in [self.contact_name, self.contact_email, self.contact_phone, self.contact_role, btn_contact, scroll]:
            contacts_layout.add_widget(w)
        contacts_tab.add_widget(contacts_layout)
        root.add_widget(contacts_tab)
        
        # Placement Candidates Tab
        placement_tab = TabbedPanelItem(text='Placement Candidates')
        placement_layout = BoxLayout(orientation='vertical', padding=10)
        self.placement_name = TextInput(hint_text='Name', size_hint_y=None, height=50)
        self.placement_rel = TextInput(hint_text='Relationship (e.g., Grandparent)', size_hint_y=None, height=50)
        self.placement_phone = TextInput(hint_text='Phone', size_hint_y=None, height=50)
        self.placement_email = TextInput(hint_text='Email', size_hint_y=None, height=50)
        self.placement_address = TextInput(hint_text='Address', size_hint_y=None, height=50)
        self.placement_notes = TextInput(hint_text='Suitability Notes (e.g., stable home)', size_hint_y=None, height=100)
        btn_add = Button(text='Add Candidate', size_hint_y=None, height=50)
        btn_add.bind(on_press=self.add_placement_candidate)
        btn_concurrent = Button(text='Add Concurrent Plan', size_hint_y=None, height=50)
        btn_concurrent.bind(on_press=self.add_concurrent_plan)
        self.placement_list = Label(text='', halign='left', valign='top', text_size=(None, None))
        scroll = ScrollView()
        scroll.add_widget(self.placement_list)
        for w in [self.placement_name, self.placement_rel, self.placement_phone, self.placement_email, self.placement_address, self.placement_notes, btn_add, btn_concurrent, scroll]:
            placement_layout.add_widget(w)
        placement_tab.add_widget(placement_layout)
        root.add_widget(placement_tab)
        
        # Add Data Tab
        add_tab = TabbedPanelItem(text='Add Data')
        add_layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        add_layout.bind(minimum_height=add_layout.setter('height'))
        scroll = ScrollView()
        actions = [
            ('new_case', 'New Case'),
            ('add_doc', 'Add Document'),
            ('add_transcript', 'Add Court Transcript'),
            ('add_dcs_report', 'Add Agency Report'),
            ('add_therapy_note', 'Add Therapy Note'),
            ('add_medical', 'Add Medical Record'),
            ('add_police_report', 'Add Police Report'),
            ('add_audio', 'Add Audio (MP3, WAV, etc.)'),
            ('add_video', 'Add Video (MP4, MOV, etc.)'),
            ('add_service', 'Add Service'),
            ('add_text_message', 'Add Text Message'),
            ('add_email', 'Add Email'),
            ('add_text_image', 'Add Text Message Image'),
            ('capture_doc', 'Capture Document Photo'),
            ('add_call_log', 'Add Call Log'),
            ('add_calendar_event', 'Add Calendar Event'),
            ('add_pre_case_context', 'Add Pre-Case Context')
        ]
        for action, text in actions:
            btn = Button(text=text, size_hint_y=None, height=50)
            btn.bind(on_press=getattr(self, action))
            add_layout.add_widget(btn)
        scroll.add_widget(add_layout)
        add_tab.add_widget(scroll)
        root.add_widget(add_tab)
        
        # Calendar Tab
        calendar_tab = TabbedPanelItem(text='Calendar')
        calendar_layout = BoxLayout(orientation='vertical', padding=10)
        self.calendar_date = TextInput(hint_text='Event Date (YYYY-MM-DD)', size_hint_y=None, height=50)
        self.calendar_desc = TextInput(hint_text='Description', size_hint_y=None, height=50)
        self.calendar_deadline = Button(text='Is Deadline: No', size_hint_y=None, height=50)
        self.calendar_deadline.bind(on_press=self.toggle_deadline)
        btn_calendar = Button(text='Add Event', size_hint_y=None, height=50)
        btn_calendar.bind(on_press=self.add_calendar_event)
        self.calendar_list = Label(text='', halign='left', valign='top', text_size=(None, None))
        scroll = ScrollView()
        scroll.add_widget(self.calendar_list)
        for w in [self.calendar_date, self.calendar_desc, self.calendar_deadline, btn_calendar, scroll]:
            calendar_layout.add_widget(w)
        calendar_tab.add_widget(calendar_layout)
        root.add_widget(calendar_tab)
        
        # Search Tab
        search_tab = TabbedPanelItem(text='Search')
        search_layout = BoxLayout(orientation='vertical', padding=10)
        self.search_query = TextInput(hint_text='Search (e.g., keyword, person)', size_hint_y=None, height=50)
        btn_search = Button(text='Search', size_hint_y=None, height=50)
        btn_search.bind(on_press=self.search_data)
        self.search_results = Label(text='', halign='left', valign='top', text_size=(None, None))
        scroll = ScrollView()
        scroll.add_widget(self.search_results)
        for w in [self.search_query, btn_search, scroll]:
            search_layout.add_widget(w)
        search_tab.add_widget(search_layout)
        root.add_widget(search_tab)
        
        # Reports Tab
        report_tab = TabbedPanelItem(text='Reports')
        report_layout = BoxLayout(orientation='vertical', padding=10)
        self.report_text = Label(text='Generate report below.', halign='left', valign='top', text_size=(None, None))
        self.report_types = Spinner(values=['All', 'Services', 'Documents', 'Text Messages', 'Emails', 'Call Logs', 'Calendar Events'], text='All', size_hint_y=None, height=50)
        self.include_pre_case = Button(text='Include Pre-Case Context: No', size_hint_y=None, height=50)
        self.include_pre_case.bind(on_press=self.toggle_pre_case)
        btn_report = Button(text='Generate Custom Report', size_hint_y=None, height=50)
        btn_report.bind(on_press=self.gen_custom_report)
        btn_lies = Button(text='Detect Lies by All Parties', size_hint_y=None, height=50)
        btn_lies.bind(on_press=self.detect_lies)
        btn_share = Button(text='Share with Lawyer', size_hint_y=None, height=50)
        btn_share.bind(on_press=self.share_with_lawyer)
        scroll = ScrollView()
        scroll.add_widget(self.report_text)
        for w in [self.report_types, self.include_pre_case, btn_report, btn_lies, btn_share, scroll]:
            report_layout.add_widget(w)
        report_tab.add_widget(report_layout)
        root.add_widget(report_tab)
        
        # Legal Tools Tab
        legal_tab = TabbedPanelItem(text='Legal Tools')
        legal_layout = BoxLayout(orientation='vertical', padding=10)
        self.motion_type = Spinner(values=['concurrent_plan', 'oppose_adoption', 'guardianship', 'contempt', 'mandamus', 'medication', 'other'], text='Select Motion', size_hint_y=None, height=50)
        self.candidate_select = Spinner(values=['None'], text='Select Candidate for Motion', size_hint_y=None, height=50)
        btn_draft = Button(text='Draft Motion', size_hint_y=None, height=50)
        btn_draft.bind(on_press=self.draft_motion)
        btn_resources = Button(text='Fetch Legal Resources', size_hint_y=None, height=50)
        btn_resources.bind(on_press=self.fetch_resources)
        self.legal_output = Label(text='', halign='left', valign='top', text_size=(None, None))
        scroll = ScrollView()
        scroll.add_widget(self.legal_output)
        for w in [self.motion_type, self.candidate_select, btn_draft, btn_resources, scroll]:
            legal_layout.add_widget(w)
        legal_tab.add_widget(legal_layout)
        root.add_widget(legal_tab)
        
        self.update_case_list()
        self.update_candidate_spinner()
        return root

    def save_config(self, instance):
        config = load_config()
        config.update({
            'api_key': self.api_key_input.text,
            'api_type': self.api_type.text,
            'state': self.state_input.text
        })
        save_config(config)
        popup = Popup(title='Success', content=Label(text='Configuration saved!'), size_hint=(0.8, 0.3))
        popup.open()

    def sync_to_cloud(self, instance):
        folder_id = self.cloud_folder.text if self.cloud_folder.text else None
        try:
            file_id = sync_to_cloud(self.conn, self.password, folder_id)
            popup = Popup(title='Success', content=Label(text=f'Synced to Google Drive (File ID: {file_id})'), size_hint=(0.8, 0.3))
        except Exception as e:
            popup = Popup(title='Error', content=Label(text=f'Sync failed: {e}'), size_hint=(0.8, 0.3))
        popup.open()

    def new_case(self, instance):
        if not self.current_case_id:
            self.current_case_id = 1
        c = self.conn.cursor()
        c.execute('INSERT INTO cases VALUES (NULL, ?, ?, ?, ?)',
                  (self.case_number.text, self.case_type.text, self.case_desc.text, self.state_input.text))
        self.conn.commit()
        c.execute('SELECT case_id FROM cases WHERE case_number=?', (self.case_number.text,))
        self.current_case_id = c.fetchone()[0]
        self.update_case_list()
        popup = Popup(title='Success', content=Label(text='Case created!'), size_hint=(0.8, 0.3))
        popup.open()

    def update_case_list(self):
        c = self.conn.cursor()
        c.execute('SELECT case_id, case_number FROM cases')
        cases = c.fetchall()
        self.case_list.values = ['Select Case'] + [f"{case[1]} (ID: {case[0]})" for case in cases]
        self.case_list.bind(text=self.on_case_select)

    def on_case_select(self, instance, value):
        if value != 'Select Case':
            self.current_case_id = int(value.split('ID: ')[1].strip(')'))
            self.update_candidate_spinner()

    def add_contact(self, instance):
        c = self.conn.cursor()
        c.execute('INSERT INTO contacts VALUES (NULL, ?, ?, ?, ?, ?)',
                  (self.current_case_id, self.contact_name.text, self.contact_email.text, self.contact_phone.text, self.contact_role.text))
        self.conn.commit()
        self.contacts_list.text += f"\n{self.contact_name.text} ({self.contact_role.text})"
        popup = Popup(title='Success', content=Label(text='Contact added!'), size_hint=(0.8, 0.3))
        popup.open()

    def add_placement_candidate(self, instance):
        c = self.conn.cursor()
        c.execute('''INSERT INTO placement_candidates VALUES (NULL, ?, ?, ?, ?, ?, ?)''',
                  (self.current_case_id, self.placement_name.text, self.placement_rel.text,
                   self.placement_phone.text, self.placement_email.text, self.placement_address.text,
                   self.placement_notes.text))
        self.conn.commit()
        c.execute('INSERT INTO contacts VALUES (NULL, ?, ?, ?, ?, ?)',
                  (self.current_case_id, self.placement_name.text, self.placement_email.text,
                   self.placement_phone.text, self.placement_rel.text))
        self.conn.commit()
        self.placement_list.text += f"\n{self.placement_name.text} ({self.placement_rel.text})"
        self.update_candidate_spinner()
        popup = Popup(title='Success', content=Label(text='Candidate added!'), size_hint=(0.8, 0.3))
        popup.open()

    def add_concurrent_plan(self, instance):
        c = self.conn.cursor()
        c.execute('SELECT candidate_id, name FROM placement_candidates WHERE case_id=?', (self.current_case_id,))
        candidates = c.fetchall()
        if not candidates:
            popup = Popup(title='Error', content=Label(text='Add a placement candidate first!'), size_hint=(0.8, 0.3))
            popup.open()
            return
        candidate_id = candidates[0][0]
        c.execute('INSERT INTO concurrent_plans VALUES (NULL, ?, ?, ?, ?, ?)',
                  (self.current_case_id, 'Reunification', 'Guardianship', candidate_id, 'Primary: Reunification; Secondary: Guardianship with relative'))
        self.conn.commit()
        popup = Popup(title='Success', content=Label(text='Concurrent plan added!'), size_hint=(0.8, 0.3))
        popup.open()

    def update_candidate_spinner(self):
        c = self.conn.cursor()
        c.execute('SELECT candidate_id, name FROM placement_candidates WHERE case_id=?', (self.current_case_id,))
        candidates = c.fetchall()
        self.candidate_select.values = ['None'] + [f"{name} (ID: {cid})" for cid, name in candidates]

    def add_doc(self, instance, is_transcript=False, is_dcs_report=False, is_image=False, is_therapy_note=False, is_medical=False, is_police_report=False, is_audio=False, is_video=False):
        chooser = FileChooserListView(filters=['*.pdf', '*.txt', '*.docx'] + MEDIA_FORMATS['image'] + MEDIA_FORMATS['audio'] + MEDIA_FORMATS['video'])
        content = BoxLayout(orientation='vertical')
        content.add_widget(chooser)
        self.doc_category = TextInput(hint_text='Custom Category (e.g., Call Log, Evidence)', size_hint_y=None, height=50)
        content.add_widget(self.doc_category)
        btn = Button(text='Select', size_hint_y=None, height=50)
        popup = Popup(title='Select File', content=content, size_hint=(0.9, 0.9))
        chooser.bind(on_submit=lambda x, y, z: self.process_doc(y[0], is_transcript, is_dcs_report, is_image, is_therapy_note, is_medical, is_police_report, is_audio, is_video, self.doc_category.text, popup))
        content.add_widget(btn)
        btn.bind(on_press=popup.dismiss)
        popup.open()

    def process_doc(self, path, is_transcript, is_dcs_report, is_image, is_therapy_note, is_medical, is_police_report, is_audio, is_video, category, popup):
        is_image = path.lower().endswith(tuple(MEDIA_FORMATS['image']))
        is_audio = path.lower().endswith(tuple(MEDIA_FORMATS['audio']))
        is_video = path.lower().endswith(tuple(MEDIA_FORMATS['video']))
        result = add_document(self.conn, self.current_case_id, path, is_transcript, is_dcs_report, is_image, is_therapy_note, is_medical, is_police_report, is_audio, is_video, category)
        popup = Popup(title='Result', content=Label(text=result), size_hint=(0.8, 0.3))
        popup.open()

    def add_transcript(self, instance):
        self.add_doc(instance, is_transcript=True)

    def add_dcs_report(self, instance):
        self.add_doc(instance, is_dcs_report=True)

    def add_therapy_note(self, instance):
        self.add_doc(instance, is_therapy_note=True)

    def add_medical(self, instance):
        self.add_doc(instance, is_medical=True)

    def add_police_report(self, instance):
        self.add_doc(instance, is_police_report=True)

    def add_audio(self, instance):
        self.add_doc(instance, is_audio=True)

    def add_video(self, instance):
        self.add_doc(instance, is_video=True)

    def add_text_image(self, instance):
        self.add_doc(instance, is_image=True)

    def capture_doc(self, instance):
        content = BoxLayout(orientation='vertical')
        camera = Camera(play=True)
        btn_capture = Button(text='Capture', size_hint_y=None, height=50)
        popup = Popup(title='Capture Document', content=content, size_hint=(0.9, 0.9))
        btn_capture.bind(on_press=lambda x: self.save_photo(camera, popup))
        content.add_widget(camera)
        content.add_widget(btn_capture)
        popup.open()

    def save_photo(self, camera, popup):
        file_path = f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        camera.export_to_png(file_path)
        result = add_document(self.conn, self.current_case_id, file_path, is_image=True, category='Captured Photo')
        popup.dismiss()
        popup = Popup(title='Result', content=Label(text=result), size_hint=(0.8, 0.3))
        popup.open()

    def add_service(self, instance):
        content = BoxLayout(orientation='vertical')
        service_type = TextInput(hint_text='Service Type (e.g., Therapy)', size_hint_y=None, height=50)
        start_date = TextInput(hint_text='Start Date (YYYY-MM-DD)', size_hint_y=None, height=50)
        end_date = TextInput(hint_text='End Date (YYYY-MM-DD)', size_hint_y=None, height=50)
        provider = TextInput(hint_text='Provider', size_hint_y=None, height=50)
        status = TextInput(hint_text='Status', size_hint_y=None, height=50)
        notes = TextInput(hint_text='Notes', size_hint_y=None, height=100)
        btn = Button(text='Add Service', size_hint_y=None, height=50)
        popup = Popup(title='Add Service', content=content, size_hint=(0.9, 0.9))
        btn.bind(on_press=lambda x: self.process_service(service_type.text, start_date.text, end_date.text, provider.text, status.text, notes.text, popup))
        for w in [service_type, start_date, end_date, provider, status, notes, btn]:
            content.add_widget(w)
        popup.open()

    def process_service(self, service_type, start_date, end_date, provider, status, notes, popup):
        c = self.conn.cursor()
        c.execute('INSERT INTO services VALUES (NULL, ?, ?, ?, ?, ?, ?, ?)',
                  (self.current_case_id, service_type, start_date, end_date, provider, status, notes))
        self.conn.commit()
        c.execute('INSERT INTO events VALUES (NULL, ?, ?, ?, ?, ?)',
                  (self.current_case_id, start_date, f"Service: {service_type}", 'service', c.lastrowid))
        c.execute('INSERT INTO calendar_events VALUES (NULL, ?, ?, ?, ?, ?)',
                  (self.current_case_id, start_date, 'service', f"Service: {service_type}", 0))
        self.conn.commit()
        popup.dismiss()
        popup = Popup(title='Success', content=Label(text='Service added!'), size_hint=(0.8, 0.3))
        popup.open()

    def add_text_message(self, instance):
        content = BoxLayout(orientation='vertical')
        msg_date = TextInput(hint_text='Date (YYYY-MM-DD)', size_hint_y=None, height=50)
        sender = TextInput(hint_text='Sender', size_hint_y=None, height=50)
        recipient = TextInput(hint_text='Recipient', size_hint_y=None, height=50)
        msg_content = TextInput(hint_text='Content', size_hint_y=None, height=100)
        btn = Button(text='Add Message', size_hint_y=None, height=50)
        popup = Popup(title='Add Text Message', content=content, size_hint=(0.9, 0.9))
        btn.bind(on_press=lambda x: self.process_text_message(msg_date.text, sender.text, recipient.text, msg_content.text, popup))
        for w in [msg_date, sender, recipient, msg_content, btn]:
            content.add_widget(w)
        popup.open()

    def process_text_message(self, msg_date, sender, recipient, content, popup):
        c = self.conn.cursor()
        c.execute('SELECT contact_id FROM contacts WHERE name=? AND case_id=?', (sender, self.current_case_id))
        sender_id = c.fetchone()
        if not sender_id:
            c.execute('INSERT INTO contacts VALUES (NULL, ?, ?, ?, ?, ?)', (self.current_case_id, sender, '', '', 'Unknown'))
            sender_id = c.lastrowid
        else:
            sender_id = sender_id[0]
        c.execute('SELECT contact_id FROM contacts WHERE name=? AND case_id=?', (recipient, self.current_case_id))
        recipient_id = c.fetchone()
        if not recipient_id:
            c.execute('INSERT INTO contacts VALUES (NULL, ?, ?, ?, ?, ?)', (self.current_case_id, recipient, '', '', 'Unknown'))
            recipient_id = c.lastrowid
        else:
            recipient_id = recipient_id[0]
        c.execute('INSERT INTO text_messages VALUES (NULL, ?, ?, ?, ?, ?, ?)',
                  (self.current_case_id, msg_date, sender_id, recipient_id, content, 0))
        self.conn.commit()
        popup.dismiss()
        popup = Popup(title='Success', content=Label(text='Message added!'), size_hint=(0.8, 0.3))
        popup.open()

    def add_email(self, instance):
        content = BoxLayout(orientation='vertical')
        email_date = TextInput(hint_text='Date (YYYY-MM-DD)', size_hint_y=None, height=50)
        sender = TextInput(hint_text='Sender', size_hint_y=None, height=50)
        recipient = TextInput(hint_text='Recipient', size_hint_y=None, height=50)
        subject = TextInput(hint_text='Subject', size_hint_y=None, height=50)
        email_content = TextInput(hint_text='Content', size_hint_y=None, height=100)
        btn = Button(text='Add Email', size_hint_y=None, height=50)
        popup = Popup(title='Add Email', content=content, size_hint=(0.9, 0.9))
        btn.bind(on_press=lambda x: self.process_email(email_date.text, sender.text, recipient.text, subject.text, email_content.text, popup))
        for w in [email_date, sender, recipient, subject, email_content, btn]:
            content.add_widget(w)
        popup.open()

    def process_email(self, email_date, sender, recipient, subject, content, popup):
        c = self.conn.cursor()
        c.execute('SELECT contact_id FROM contacts WHERE name=? AND case_id=?', (sender, self.current_case_id))
        sender_id = c.fetchone()
        if not sender_id:
            c.execute('INSERT INTO contacts VALUES (NULL, ?, ?, ?, ?, ?)', (self.current_case_id, sender, '', '', 'Unknown'))
            sender_id = c.lastrowid
        else:
            sender_id = sender_id[0]
        c.execute('SELECT contact_id FROM contacts WHERE name=? AND case_id=?', (recipient, self.current_case_id))
        recipient_id = c.fetchone()
        if not recipient_id:
            c.execute('INSERT INTO contacts VALUES (NULL, ?, ?, ?, ?, ?)', (self.current_case_id, recipient, '', '', 'Unknown'))
            recipient_id = c.lastrowid
        else:
            recipient_id = recipient_id[0]
        c.execute('INSERT INTO emails VALUES (NULL, ?, ?, ?, ?, ?, ?, ?)',
                  (self.current_case_id, email_date, sender_id, recipient_id, subject, content, 0))
        self.conn.commit()
        popup.dismiss()
        popup = Popup(title='Success', content=Label(text='Email added!'), size_hint=(0.8, 0.3))
        popup.open()

    def add_call_log(self, instance):
        chooser = FileChooserListView(filters=['*.csv', '*.txt'] + MEDIA_FORMATS['image'])
        content = BoxLayout(orientation='vertical')
        content.add_widget(chooser)
        btn = Button(text='Select', size_hint_y=None, height=50)
        popup = Popup(title='Select Call Log', content=content, size_hint=(0.9, 0.9))
        chooser.bind(on_submit=lambda x, y, z: self.process_call_log(y[0], popup))
        content.add_widget(btn)
        btn.bind(on_press=popup.dismiss)
        popup.open()

    def process_call_log(self, path, popup):
        logs = parse_call_log(path)
        add_call_log(self.conn, self.current_case_id, logs)
        popup.dismiss()
        popup = Popup(title='Success', content=Label(text='Call log added!'), size_hint=(0.8, 0.3))
        popup.open()

    def toggle_deadline(self, instance):
        instance.text = 'Is Deadline: Yes' if 'No' in instance.text else 'Is Deadline: No'

    def add_calendar_event(self, instance):
        c = self.conn.cursor()
        is_deadline = 1 if 'Yes' in self.calendar_deadline.text else 0
        c.execute('INSERT INTO calendar_events VALUES (NULL, ?, ?, ?, ?, ?)',
                  (self.current_case_id, self.calendar_date.text, 'custom', self.calendar_desc.text, is_deadline))
        self.conn.commit()
        self.calendar_list.text += f"\n{self.calendar_date.text}: {self.calendar_desc.text} {'(Deadline)' if is_deadline else ''}"
        popup = Popup(title='Success', content=Label(text='Event added!'), size_hint=(0.8, 0.3))
        popup.open()

    def add_pre_case_context(self, instance):
        content = BoxLayout(orientation='vertical')
        context_date = TextInput(hint_text='Date (YYYY-MM-DD)', size_hint_y=None, height=50)
        context_desc = TextInput(hint_text='Description', size_hint_y=None, height=100)
        chooser = FileChooserListView(filters=['*.pdf', '*.txt', '*.docx'] + MEDIA_FORMATS['image'] + MEDIA_FORMATS['audio'] + MEDIA_FORMATS['video'])
        btn = Button(text='Add Context', size_hint_y=None, height=50)
        popup = Popup(title='Add Pre-Case Context', content=content, size_hint=(0.9, 0.9))
        btn.bind(on_press=lambda x: self.process_pre_case_context(context_date.text, context_desc.text, chooser.selection[0] if chooser.selection else None, popup))
        for w in [context_date, context_desc, chooser, btn]:
            content.add_widget(w)
        popup.open()

    def process_pre_case_context(self, context_date, context_desc, file_path, popup):
        c = self.conn.cursor()
        file_type = os.path.splitext(file_path)[1].lower() if file_path else None
        c.execute('INSERT INTO pre_case_context VALUES (NULL, ?, ?, ?, ?, ?)',
                  (self.current_case_id, context_date, context_desc, file_path, file_type))
        self.conn.commit()
        popup.dismiss()
        popup = Popup(title='Success', content=Label(text='Pre-case context added!'), size_hint=(0.8, 0.3))
        popup.open()

    def search_data(self, instance):
        query = self.search_query.text.lower()
        c = self.conn.cursor()
        results = []
        c.execute('SELECT doc_name, content FROM documents WHERE case_id=? AND content LIKE ?', (self.current_case_id, f'%{query}%'))
        results.extend([f"Document: {row[0]} - {row[1][:50]}..." for row in c.fetchall()])
        c.execute('SELECT msg_date, content FROM text_messages WHERE case_id=? AND content LIKE ?', (self.current_case_id, f'%{query}%'))
        results.extend([f"Message: {row[0]} - {row[1][:50]}..." for row in c.fetchall()])
        c.execute('SELECT email_date, subject, content FROM emails WHERE case_id=? AND content LIKE ?', (self.current_case_id, f'%{query}%'))
        results.extend([f"Email: {row[0]} ({row[1]}) - {row[2][:50]}..." for row in c.fetchall()])
        c.execute('SELECT description FROM pre_case_context WHERE case_id=? AND description LIKE ?', (self.current_case_id, f'%{query}%'))
        results.extend([f"Pre-Case: {row[0]}" for row in c.fetchall()])
        self.search_results.text = '\n'.join(results) if results else "No results found."
        popup = Popup(title='Search Results', content=Label(text='Results displayed.'), size_hint=(0.8, 0.3))
        popup.open()

    def toggle_pre_case(self, instance):
        instance.text = 'Include Pre-Case Context: Yes' if 'No' in instance.text else 'Include Pre-Case Context: No'

    def gen_custom_report(self, instance):
        data_types = [self.report_types.text.lower()] if self.report_types.text != 'All' else None
        include_pre_case = 'Yes' in self.include_pre_case.text
        report = generate_custom_report(self.conn, self.current_case_id, data_types, include_pre_case)
        self.report_text.text = report
        create_pdf(f'report_{self.current_case_id}_{datetime.now().strftime("%Y%m%d")}.pdf', report)
        popup = Popup(title='Success', content=Label(text='Report generated and saved as PDF!'), size_hint=(0.8, 0.3))
        popup.open()

    def detect_lies(self, instance):
        analysis = detect_lies_patterns(self.conn, self.current_case_id)
        self.report_text.text += f"\nLie Detection Report:\n{analysis}"
        create_pdf(f'lie_detection_{self.current_case_id}_{datetime.now().strftime("%Y%m%d")}.pdf', analysis)
        popup = Popup(title='Success', content=Label(text='Lie detection complete! Saved as PDF.'), size_hint=(0.8, 0.3))
        popup.open()

    def draft_motion(self, instance):
        candidate_id = None
        if self.candidate_select.text != 'None':
            candidate_id = int(self.candidate_select.text.split('ID: ')[1].strip(')'))
        motion = draft_motion(self.conn, self.current_case_id, self.motion_type.text, candidate_id)
        self.legal_output.text += f"\nMotion ({self.motion_type.text}):\n{motion}"
        popup = Popup(title='Success', content=Label(text='Motion drafted and saved as PDF!'), size_hint=(0.8, 0.3))
        popup.open()

    def fetch_resources(self, instance):
        state = load_config().get('state', '')
        resources = search_chins_resources(state)
        self.legal_output.text += f"\nLegal Resources for {state}:\n{'\n'.join(resources)}"
        popup = Popup(title='Success', content=Label(text='Resources fetched!'), size_hint=(0.8, 0.3))
        popup.open()

    def share_with_lawyer(self, instance):
        file_id = sync_to_cloud(self.conn, self.password, self.cloud_folder.text if self.cloud_folder.text else None)
        self.report_text.text += f"\nShared with Lawyer: Google Drive File ID {file_id}"
        popup = Popup(title='Success', content=Label(text='Data shared via Google Drive!'), size_hint=(0.8, 0.3))
        popup.open()

if __name__ == '__main__':
    CaseManagerApp().run()
