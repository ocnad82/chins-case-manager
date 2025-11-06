import kivy
kivy.require('2.3.0')
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.filechooser import FileChooserIconView
import sqlite3
import pysqlcipher3.dbapi2 as sqlcipher
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import PyPDF2
from docx import Document
import pytesseract
from PIL import Image
from dateutil.parser import parse
import speech_recognition as sr
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload
import os
import pickle
import datetime
import openai
import ffmpeg
import moviepy.editor as mpe
import json

class CaseManagerApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.conn = None
        self.current_case_id = None
        self.state = None
        self.api_key = None
        self.creds = None

    def init_db(self, password):
        self.conn = sqlcipher.connect('case_manager.db')
        c = self.conn.cursor()
        c.execute(f"PRAGMA key = '{password}'")
        c.execute('''CREATE TABLE IF NOT EXISTS cases (
            case_id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_name TEXT,
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
            file_path TEXT,
            content TEXT,
            doc_date TEXT,
            category TEXT,
            FOREIGN KEY(case_id) REFERENCES cases(case_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS audio_recordings (
            audio_id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER,
            audio_name TEXT,
            file_path TEXT,
            transcription TEXT,
            audio_date TEXT,
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
            event_type TEXT,
            FOREIGN KEY(case_id) REFERENCES cases(case_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS calendar_events (
            cal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER,
            event_date TEXT,
            title TEXT,
            description TEXT,
            FOREIGN KEY(case_id) REFERENCES cases(case_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS pre_case_context (
            context_id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER,
            description TEXT,
            context_date TEXT,
            FOREIGN KEY(case_id) REFERENCES cases(case_id)
        )''')
        self.conn.commit()

    def setup_google_drive(self):
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if os.path.exists('credentials.json'):
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                    creds = flow.run_local_server(port=0)
                else:
                    print("No credentials.json found. Cloud sync disabled.")
                    return None
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        return creds

    def upload_to_drive(self, file_path, file_name):
        if not self.creds:
            self.creds = self.setup_google_drive()
        if not self.creds:
            return
        service = build('drive', 'v3', credentials=self.creds)
        file_metadata = {'name': file_name}
        media = MediaFileUpload(file_path)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"Uploaded {file_name} to Google Drive with ID: {file.get('id')}")

    def build(self):
        self.root = TabbedPanel()
        self.root.default_tab_text = 'Setup'
        setup_tab = TabbedPanelItem(text='Setup')
        setup_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        setup_layout.add_widget(Label(text='Case Name:'))
        self.case_name_input = TextInput(multiline=False)
        setup_layout.add_widget(self.case_name_input)
        setup_layout.add_widget(Label(text='State:'))
        self.state_input = TextInput(multiline=False)
        setup_layout.add_widget(self.state_input)
        setup_layout.add_widget(Label(text='API Key (Grok or OpenAI):'))
        self.api_key_input = TextInput(multiline=False, password=True)
        setup_layout.add_widget(self.api_key_input)
        setup_layout.add_widget(Label(text='Database Password:'))
        self.db_password_input = TextInput(multiline=False, password=True)
        setup_layout.add_widget(self.db_password_input)
        setup_btn = Button(text='Create Case')
        setup_btn.bind(on_press=self.create_case)
        setup_layout.add_widget(setup_btn)
        setup_tab.add_widget(setup_layout)
        self.root.add_widget(setup_tab)

        add_data_tab = TabbedPanelItem(text='Add Data')
        add_data_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        add_data_layout.add_widget(Button(text='Add Document', on_press=self.add_document))
        add_data_layout.add_widget(Button(text='Add Audio', on_press=self.add_audio))
        add_data_layout.add_widget(Button(text='Add Text Message', on_press=self.add_text_message))
        add_data_layout.add_widget(Button(text='Add Email', on_press=self.add_email))
        add_data_layout.add_widget(Button(text='Add Text Message Image', on_press=self.add_text_image))
        add_data_layout.add_widget(Button(text='Add Contact', on_press=self.add_contact))
        add_data_layout.add_widget(Button(text='Add Event', on_press=self.add_event))
        add_data_layout.add_widget(Button(text='Add Pre-Case Context', on_press=self.add_pre_case_context))
        add_data_tab.add_widget(add_data_layout)
        self.root.add_widget(add_data_tab)

        search_tab = TabbedPanelItem(text='Search')
        search_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        search_layout.add_widget(Label(text='Search Query:'))
        self.search_query = TextInput(multiline=False)
        search_layout.add_widget(self.search_query)
        search_btn = Button(text='Search')
        search_btn.bind(on_press=self.search_data)
        search_layout.add_widget(search_btn)
        self.search_results = Label(text='')
        search_scroll = ScrollView()
        search_scroll.add_widget(self.search_results)
        search_layout.add_widget(search_scroll)
        search_tab.add_widget(search_layout)
        self.root.add_widget(search_tab)

        calendar_tab = TabbedPanelItem(text='Calendar')
        calendar_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        calendar_layout.add_widget(Label(text='Event Date (YYYY-MM-DD):'))
        self.event_date_input = TextInput(multiline=False)
        calendar_layout.add_widget(self.event_date_input)
        calendar_layout.add_widget(Label(text='Event Title:'))
        self.event_title_input = TextInput(multiline=False)
        calendar_layout.add_widget(self.event_title_input)
        calendar_layout.add_widget(Label(text='Event Description:'))
        self.event_desc_input = TextInput(multiline=True)
        calendar_layout.add_widget(self.event_desc_input)
        add_event_btn = Button(text='Add Calendar Event')
        add_event_btn.bind(on_press=self.add_calendar_event)
        calendar_layout.add_widget(add_event_btn)
        self.calendar_output = Label(text='')
        calendar_scroll = ScrollView()
        calendar_scroll.add_widget(self.calendar_output)
        calendar_layout.add_widget(calendar_scroll)
        calendar_tab.add_widget(calendar_layout)
        self.root.add_widget(calendar_tab)

        legal_tab = TabbedPanelItem(text='Legal')
        legal_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        legal_layout.add_widget(Label(text='Enter State for Legal Resources:'))
        self.state_input_legal = TextInput(multiline=False)
        legal_layout.add_widget(self.state_input_legal)
        legal_btn = Button(text='Search Legal Resources')
        legal_btn.bind(on_press=self.search_chins_resources)
        legal_layout.add_widget(legal_btn)
        self.legal_output = Label(text='')
        legal_scroll = ScrollView()
        legal_scroll.add_widget(self.legal_output)
        legal_layout.add_widget(legal_scroll)
        legal_tab.add_widget(legal_layout)
        self.root.add_widget(legal_tab)

        reports_tab = TabbedPanelItem(text='Reports')
        reports_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        reports_layout.add_widget(Button(text='Generate Timeline', on_press=self.generate_timeline))
        reports_layout.add_widget(Button(text='Generate Custom Report', on_press=self.generate_custom_report))
        reports_layout.add_widget(Button(text='Detect Lies by All Parties', on_press=self.detect_lies_patterns))
        reports_layout.add_widget(Button(text='Draft Motion', on_press=self.draft_motion))
        self.report_output = Label(text='')
        report_scroll = ScrollView()
        report_scroll.add_widget(self.report_output)
        reports_layout.add_widget(report_scroll)
        reports_tab.add_widget(reports_layout)
        self.root.add_widget(reports_tab)

        about_tab = TabbedPanelItem(text='About')
        about_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        about_layout.add_widget(Label(text='Child Welfare Case Manager\nVersion 1.0\nNot legal advice.\nFor parents fighting for reunification.'))
        about_tab.add_widget(about_layout)
        self.root.add_widget(about_tab)

        return self.root

    def create_case(self, instance):
        case_name = self.case_name_input.text.strip()
        self.state = self.state_input.text.strip()
        self.api_key = self.api_key_input.text.strip()
        password = self.db_password_input.text.strip()
        if not case_name or not self.state or not self.api_key or not password:
            popup = Popup(title='Error', content=Label(text='All fields are required.'), size_hint=(0.8, 0.3))
            popup.open()
            return
        self.init_db(password)
        c = self.conn.cursor()
        c.execute('INSERT INTO cases (case_name, state) VALUES (?, ?)', (case_name, self.state))
        self.current_case_id = c.lastrowid
        self.conn.commit()
        self.creds = self.setup_google_drive()
        popup = Popup(title='Success', content=Label(text='Case created!'), size_hint=(0.8, 0.3))
        popup.open()

    def add_document(self, instance):
        content = BoxLayout(orientation='vertical')
        file_chooser = FileChooserIconView(filters=['*.pdf', '*.docx', '*.txt'])
        content.add_widget(file_chooser)
        doc_name = TextInput(hint_text='Document Name', size_hint_y=None, height=50)
        content.add_widget(doc_name)
        doc_date = TextInput(hint_text='Date (YYYY-MM-DD)', size_hint_y=None, height=50)
        content.add_widget(doc_date)
        category = TextInput(hint_text='Category (e.g., Court Order)', size_hint_y=None, height=50)
        content.add_widget(category)
        btn = Button(text='Add Document', size_hint_y=None, height=50)
        popup = Popup(title='Add Document', content=content, size_hint=(0.9, 0.9))
        btn.bind(on_press=lambda x: self.process_document(file_chooser.selection, doc_name.text, doc_date.text, category.text, popup))
        content.add_widget(btn)
        popup.open()

    def process_document(self, selection, doc_name, doc_date, category, popup):
        if not selection or not doc_name or not doc_date or not category:
            popup = Popup(title='Error', content=Label(text='All fields required.'), size_hint=(0.8, 0.3))
            popup.open()
            return
        file_path = selection[0]
        content = ''
        if file_path.endswith('.pdf'):
            with open(file_path, 'rb') as f:
                pdf = PyPDF2.PdfReader(f)
                content = ' '.join(page.extract_text() for page in pdf.pages)
        elif file_path.endswith('.docx'):
            doc = Document(file_path)
            content = ' '.join(p.text for p in doc.paragraphs)
        elif file_path.endswith('.txt'):
            with open(file_path, 'r') as f:
                content = f.read()
        c = self.conn.cursor()
        c.execute('INSERT INTO documents VALUES (NULL, ?, ?, ?, ?, ?, ?)', 
                  (self.current_case_id, doc_name, file_path, content, doc_date, category))
        c.execute('INSERT INTO events VALUES (NULL, ?, ?, ?, ?)', 
                  (self.current_case_id, doc_date, f"Added document: {doc_name}", 'Document'))
        self.conn.commit()
        self.upload_to_drive(file_path, doc_name)
        popup.dismiss()
        popup = Popup(title='Success', content=Label(text='Document added!'), size_hint=(0.8, 0.3))
        popup.open()

    def add_audio(self, instance):
        content = BoxLayout(orientation='vertical')
        file_chooser = FileChooserIconView(filters=['*.mp3', '*.wav', '*.m4a'])
        content.add_widget(file_chooser)
        audio_name = TextInput(hint_text='Audio Name', size_hint_y=None, height=50)
        content.add_widget(audio_name)
        audio_date = TextInput(hint_text='Date (YYYY-MM-DD)', size_hint_y=None, height=50)
        content.add_widget(audio_date)
        btn = Button(text='Add Audio', size_hint_y=None, height=50)
        popup = Popup(title='Add Audio', content=content, size_hint=(0.9, 0.9))
        btn.bind(on_press=lambda x: self.process_audio(file_chooser.selection, audio_name.text, audio_date.text, popup))
        content.add_widget(btn)
        popup.open()

    def process_audio(self, selection, audio_name, audio_date, popup):
        if not selection or not audio_name or not audio_date:
            popup = Popup(title='Error', content=Label(text='All fields required.'), size_hint=(0.8, 0.3))
            popup.open()
            return
        file_path = selection[0]
        r = sr.Recognizer()
        with sr.AudioFile(file_path) as source:
            audio = r.record(source)
            try:
                transcription = r.recognize_google(audio)
            except:
                transcription = 'Transcription failed.'
        c = self.conn.cursor()
        c.execute('INSERT INTO audio_recordings VALUES (NULL, ?, ?, ?, ?, ?)', 
                  (self.current_case_id, audio_name, file_path, transcription, audio_date))
        c.execute('INSERT INTO events VALUES (NULL, ?, ?, ?, ?)', 
                  (self.current_case_id, audio_date, f"Added audio: {audio_name}", 'Audio'))
        self.conn.commit()
        self.upload_to_drive(file_path, audio_name)
        popup.dismiss()
        popup = Popup(title='Success', content=Label(text='Audio added!'), size_hint=(0.8, 0.3))
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
        c.execute('INSERT INTO events VALUES (NULL, ?, ?, ?, ?)', 
                  (self.current_case_id, msg_date, f"Text message from {sender} to {recipient}", 'Text Message'))
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
        c.execute('INSERT INTO events VALUES (NULL, ?, ?, ?, ?)', 
                  (self.current_case_id, email_date, f"Email from {sender}: {subject}", 'Email'))
        self.conn.commit()
        popup.dismiss()
        popup = Popup(title='Success', content=Label(text='Email added!'), size_hint=(0.8, 0.3))
        popup.open()

    def add_text_image(self, instance):
        content = BoxLayout(orientation='vertical')
        file_chooser = FileChooserIconView(filters=['*.png', '*.jpg', '*.jpeg', '*.bmp', '*.gif', '*.heic'])
        content.add_widget(file_chooser)
        btn = Button(text='Process Image', size_hint_y=None, height=50)
        popup = Popup(title='Add Text Message Image', content=content, size_hint=(0.9, 0.9))
        btn.bind(on_press=lambda x: self.process_text_image(file_chooser.selection, popup))
        content.add_widget(btn)
        popup.open()

    def process_text_image(self, selection, popup):
        if not selection:
            popup = Popup(title='Error', content=Label(text='Please select an image.'), size_hint=(0.8, 0.3))
            popup.open()
            return
        file_path = selection[0]
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
        try:
            lines = text.split('\n')
            msg_date = parse(lines[0], fuzzy=True).strftime('%Y-%m-%d') if lines else 'Unknown'
            sender = lines[1] if len(lines) > 1 else 'Unknown'
            content = ' '.join(lines[2:]) if len(lines) > 2 else 'No content extracted'
        except:
            msg_date, sender, content = 'Unknown', 'Unknown', text
        c = self.conn.cursor()
        c.execute('SELECT contact_id FROM contacts WHERE name=? AND case_id=?', (sender, self.current_case_id))
        sender_id = c.fetchone()
        if not sender_id:
            c.execute('INSERT INTO contacts VALUES (NULL, ?, ?, ?, ?, ?)', (self.current_case_id, sender, '', '', 'Unknown'))
            sender_id = c.lastrowid
        else:
            sender_id = sender_id[0]
        c.execute('INSERT INTO text_messages VALUES (NULL, ?, ?, ?, ?, ?, ?)', 
                  (self.current_case_id, msg_date, sender_id, sender_id, content, 1))
        c.execute('INSERT INTO events VALUES (NULL, ?, ?, ?, ?)', 
                  (self.current_case_id, msg_date, f"Text message image from {sender}", 'Text Message'))
        self.conn.commit()
        self.upload_to_drive(file_path, os.path.basename(file_path))
        popup.dismiss()
        popup = Popup(title='Success', content=Label(text='Image processed!'), size_hint=(0.8, 0.3))
        popup.open()

    def add_contact(self, instance):
        content = BoxLayout(orientation='vertical')
        name = TextInput(hint_text='Name', size_hint_y=None, height=50)
        email = TextInput(hint_text='Email', size_hint_y=None, height=50)
        phone = TextInput(hint_text='Phone', size_hint_y=None, height=50)
        role = TextInput(hint_text='Role (e.g., Case Worker)', size_hint_y=None, height=50)
        btn = Button(text='Add Contact', size_hint_y=None, height=50)
        popup = Popup(title='Add Contact', content=content, size_hint=(0.9, 0.9))
        btn.bind(on_press=lambda x: self.process_contact(name.text, email.text, phone.text, role.text, popup))
        for w in [name, email, phone, role, btn]:
            content.add_widget(w)
        popup.open()

    def process_contact(self, name, email, phone, role, popup):
        if not name:
            popup = Popup(title='Error', content=Label(text='Name is required.'), size_hint=(0.8, 0.3))
            popup.open()
            return
        c = self.conn.cursor()
        c.execute('INSERT INTO contacts VALUES (NULL, ?, ?, ?, ?, ?)', 
                  (self.current_case_id, name, email, phone, role))
        self.conn.commit()
        popup.dismiss()
        popup = Popup(title='Success', content=Label(text='Contact added!'), size_hint=(0.8, 0.3))
        popup.open()

    def add_event(self, instance):
        content = BoxLayout(orientation='vertical')
        event_date = TextInput(hint_text='Date (YYYY-MM-DD)', size_hint_y=None, height=50)
        description = TextInput(hint_text='Description', size_hint_y=None, height=100)
        event_type = TextInput(hint_text='Type (e.g., Court Hearing)', size_hint_y=None, height=50)
        btn = Button(text='Add Event', size_hint_y=None, height=50)
        popup = Popup(title='Add Event', content=content, size_hint=(0.9, 0.9))
        btn.bind(on_press=lambda x: self.process_event(event_date.text, description.text, event_type.text, popup))
        for w in [event_date, description, event_type, btn]:
            content.add_widget(w)
        popup.open()

    def process_event(self, event_date, description, event_type, popup):
        if not event_date or not description or not event_type:
            popup = Popup(title='Error', content=Label(text='All fields required.'), size_hint=(0.8, 0.3))
            popup.open()
            return
        c = self.conn.cursor()
        c.execute('INSERT INTO events VALUES (NULL, ?, ?, ?, ?)', 
                  (self.current_case_id, event_date, description, event_type))
        self.conn.commit()
        popup.dismiss()
        popup = Popup(title='Success', content=Label(text='Event added!'), size_hint=(0.8, 0.3))
        popup.open()

    def add_calendar_event(self, instance):
        event_date = self.event_date_input.text.strip()
        title = self.event_title_input.text.strip()
        description = self.event_desc_input.text.strip()
        if not event_date or not title or not description:
            popup = Popup(title='Error', content=Label(text='All fields required.'), size_hint=(0.8, 0.3))
            popup.open()
            return
        c = self.conn.cursor()
        c.execute('INSERT INTO calendar_events VALUES (NULL, ?, ?, ?, ?)', 
                  (self.current_case_id, event_date, title, description))
        self.conn.commit()
        self.calendar_output.text += f"\n{event_date}: {title} - {description}"
        popup = Popup(title='Success', content=Label(text='Calendar event added!'), size_hint=(0.8, 0.3))
        popup.open()

    def add_pre_case_context(self, instance):
        content = BoxLayout(orientation='vertical')
        context_date = TextInput(hint_text='Date (YYYY-MM-DD)', size_hint_y=None, height=50)
        description = TextInput(hint_text='Context Description', size_hint_y=None, height=100)
        btn = Button(text='Add Context', size_hint_y=None, height=50)
        popup = Popup(title='Add Pre-Case Context', content=content, size_hint=(0.9, 0.9))
        btn.bind(on_press=lambda x: self.process_pre_case_context(context_date.text, description.text, popup))
        for w in [context_date, description, btn]:
            content.add_widget(w)
        popup.open()

    def process_pre_case_context(self, context_date, description, popup):
        if not context_date or not description:
            popup = Popup(title='Error', content=Label(text='All fields required.'), size_hint=(0.8, 0.3))
            popup.open()
            return
        c = self.conn.cursor()
        c.execute('INSERT INTO pre_case_context VALUES (NULL, ?, ?, ?)', 
                  (self.current_case_id, description, context_date))
        self.conn.commit()
        popup.dismiss()
        popup = Popup(title='Success', content=Label(text='Context added!'), size_hint=(0.8, 0.3))
        popup.open()

    def search_data(self, instance):
        query = self.search_query.text.lower()
        if not query:
            popup = Popup(title='Error', content=Label(text='Enter a search query.'), size_hint=(0.8, 0.3))
            popup.open()
            return
        c = self.conn.cursor()
        results = []
        c.execute('SELECT doc_name, content FROM documents WHERE case_id=? AND content LIKE ?', 
                  (self.current_case_id, f'%{query}%'))
        results.extend([f"Document: {row[0]} - {row[1][:50]}..." for row in c.fetchall()])
        c.execute('SELECT msg_date, content FROM text_messages WHERE case_id=? AND content LIKE ?', 
                  (self.current_case_id, f'%{query}%'))
        results.extend([f"Message: {row[0]} - {row[1][:50]}..." for row in c.fetchall()])
        c.execute('SELECT email_date, subject, content FROM emails WHERE case_id=? AND content LIKE ?', 
                  (self.current_case_id, f'%{query}%'))
        results.extend([f"Email: {row[0]} ({row[1]}) - {row[2][:50]}..." for row in c.fetchall()])
        c.execute('SELECT description FROM pre_case_context WHERE case_id=? AND description LIKE ?', 
                  (self.current_case_id, f'%{query}%'))
        results.extend([f"Pre-Case: {row[0]}" for row in c.fetchall()])
        self.search_results.text = '\n'.join(results) if results else "No results found."
        popup = Popup(title='Success', content=Label(text='Results displayed.'), size_hint=(0.8, 0.3))
        popup.open()

    def search_chins_resources(self, instance):
        state = self.state_input_legal.text.strip()
        if not state:
            popup = Popup(title='Error', content=Label(text='Please enter a state.'), size_hint=(0.8, 0.3))
            popup.open()
            return
        try:
            query = f"{state} child welfare laws and forms"
            url = f"https://www.google.com/search?q={quote(query)}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            resources = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/url?q=' in href and 'google' not in href:
                    clean_url = href.split('/url?q=')[1].split('&')[0]
                    resources.append(clean_url)
            # Compute joined resources outside f-string
            resources_text = '\n'.join(resources[:5])  # Limit to top 5 results
            self.legal_output.text += f"\nLegal Resources for {state}:\n{resources_text}"
        except Exception as e:
            popup = Popup(title='Error', content=Label(text=f'Failed to fetch resources: {str(e)}'), size_hint=(0.8, 0.3))
            popup.open()

    def generate_timeline(self, instance):
        c = self.conn.cursor()
        c.execute('SELECT event_date, description, event_type FROM events WHERE case_id=? ORDER BY event_date', 
                  (self.current_case_id,))
        events = c.fetchall()
        timeline = '\n'.join([f"{row[0]}: {row[2]} - {row[1]}" for row in events])
        self.report_output.text = f"Timeline:\n{timeline}"
        c = canvas.Canvas('timeline.pdf', pagesize=letter)
        c.drawString(100, 750, "Case Timeline")
        y = 700
        for line in timeline.split('\n'):
            c.drawString(100, y, line)
            y -= 20
        c.save()
        self.upload_to_drive('timeline.pdf', 'timeline.pdf')
        popup = Popup(title='Success', content=Label(text='Timeline generated as timeline.pdf'), size_hint=(0.8, 0.3))
        popup.open()

    def generate_custom_report(self, instance):
        content = BoxLayout(orientation='vertical')
        report_type = TextInput(hint_text='Report Type (e.g., Visitation Evidence)', size_hint_y=None, height=50)
        content.add_widget(report_type)
        btn = Button(text='Generate Report', size_hint_y=None, height=50)
        popup = Popup(title='Custom Report', content=content, size_hint=(0.9, 0.9))
        btn.bind(on_press=lambda x: self.process_custom_report(report_type.text, popup))
        content.add_widget(btn)
        popup.open()

    def process_custom_report(self, report_type, popup):
        c = self.conn.cursor()
        report_content = []
        if 'document' in report_type.lower():
            c.execute('SELECT doc_name, doc_date, content FROM documents WHERE case_id=?', (self.current_case_id,))
            report_content.extend([f"Document: {row[0]} ({row[1]}): {row[2][:50]}..." for row in c.fetchall()])
        if 'text' in report_type.lower():
            c.execute('SELECT msg_date, content FROM text_messages WHERE case_id=?', (self.current_case_id,))
            report_content.extend([f"Message: {row[0]}: {row[1][:50]}..." for row in c.fetchall()])
        if 'email' in report_type.lower():
            c.execute('SELECT email_date, subject, content FROM emails WHERE case_id=?', (self.current_case_id,))
            report_content.extend([f"Email: {row[0]} ({row[1]}): {row[2][:50]}..." for row in c.fetchall()])
        report_text = '\n'.join(report_content)
        self.report_output.text = f"Custom Report ({report_type}):\n{report_text}"
        c = canvas.Canvas('custom_report.pdf', pagesize=letter)
        c.drawString(100, 750, f"Custom Report: {report_type}")
        y = 700
        for line in report_text.split('\n'):
            c.drawString(100, y, line)
            y -= 20
        c.save()
        self.upload_to_drive('custom_report.pdf', 'custom_report.pdf')
        popup.dismiss()
        popup = Popup(title='Success', content=Label(text='Report generated as custom_report.pdf'), size_hint=(0.8, 0.3))
        popup.open()

    def detect_lies_patterns(self, instance):
        c = self.conn.cursor()
        c.execute('SELECT content FROM documents WHERE case_id=?', (self.current_case_id,))
        docs = [row[0] for row in c.fetchall()]
        c.execute('SELECT content FROM text_messages WHERE case_id=?', (self.current_case_id,))
        texts = [row[0] for row in c.fetchall()]
        c.execute('SELECT content FROM emails WHERE case_id=?', (self.current_case_id,))
        emails = [row[0] for row in c.fetchall()]
        c.execute('SELECT transcription FROM audio_recordings WHERE case_id=?', (self.current_case_id,))
        audios = [row[0] for row in c.fetchall()]
        all_content = docs + texts + emails + audios
        prompt = f"Analyze the following evidence for inconsistencies or lies:\n{'\n'.join(all_content)}\nProvide a report."
        try:
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            report = response.choices[0].message.content
        except Exception as e:
            report = f"Error in lie detection: {str(e)}"
        self.report_output.text = f"Lie Detection Report:\n{report}"
        c = canvas.Canvas('lie_detection.pdf', pagesize=letter)
        c.drawString(100, 750, "Lie Detection Report")
        y = 700
        for line in report.split('\n'):
            c.drawString(100, y, line)
            y -= 20
        c.save()
        self.upload_to_drive('lie_detection.pdf', 'lie_detection.pdf')
        popup = Popup(title='Success', content=Label(text='Lie detection report generated as lie_detection.pdf'), size_hint=(0.8, 0.3))
        popup.open()

    def draft_motion(self, instance):
        content = BoxLayout(orientation='vertical')
        motion_type = TextInput(hint_text='Motion Type (e.g., Motion to Oppose Adoption)', size_hint_y=None, height=50)
        content.add_widget(motion_type)
        btn = Button(text='Draft Motion', size_hint_y=None, height=50)
        popup = Popup(title='Draft Motion', content=content, size_hint=(0.9, 0.9))
        btn.bind(on_press=lambda x: self.process_motion(motion_type.text, popup))
        content.add_widget(btn)
        popup.open()

    def process_motion(self, motion_type, popup):
        c = self.conn.cursor()
        c.execute('SELECT content FROM documents WHERE case_id=?', (self.current_case_id,))
        docs = [row[0] for row in c.fetchall()]
        c.execute('SELECT content FROM text_messages WHERE case_id=?', (self.current_case_id,))
        texts = [row[0] for row in c.fetchall()]
        c.execute('SELECT content FROM emails WHERE case_id=?', (self.current_case_id,))
        emails = [row[0] for row in c.fetchall()]
        c.execute('SELECT description FROM pre_case_context WHERE case_id=?', (self.current_case_id,))
        context = [row[0] for row in c.fetchall()]
        all_content = docs + texts + emails + context
        prompt = f"Draft a legal motion for a child welfare case in {self.state}: {motion_type}\nEvidence:\n{'\n'.join(all_content)}\nInclude relevant legal citations."
        try:
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            motion = response.choices[0].message.content
        except Exception as e:
            motion = f"Error drafting motion: {str(e)}"
        doc = Document()
        doc.add_heading(motion_type, 0)
        doc.add_paragraph(motion)
        doc.save('motion.docx')
        self.upload_to_drive('motion.docx', 'motion.docx')
        self.report_output.text = f"Motion Draft:\n{motion}"
        popup.dismiss()
        popup = Popup(title='Success', content=Label(text='Motion drafted as motion.docx'), size_hint=(0.8, 0.3))
        popup.open()

if __name__ == '__main__':
    CaseManagerApp().run()
