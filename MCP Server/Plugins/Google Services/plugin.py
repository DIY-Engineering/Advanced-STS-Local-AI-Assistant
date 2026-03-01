"""
Google Services Plugin - SIMPLIFIED VERSION
User-friendly: Only OAuth authentication required!
API Keys are hardcoded (admin will replace them)
"""

import os
import json
import requests
import webbrowser
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# Google Auth imports
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

# ============ HARDCODED API CREDENTIALS ============
# In Your Google Cloud Console Under Your Project Name Activate: "Custom Search API", "Gmail API", "People API",  "Google Calendar API", "YouTube Data API v3"
# You have to create a custom search engine and also create an OAuth authentication file in .JSON format
# Admin: Replace these with your actual Google API credentials
GOOGLE_API_KEY = "dummy"
GOOGLE_CSE_ID = "dummy"


class GoogleServicesPlugin(BasePlugin):
    """Google Services with simplified GUI - OAuth only!"""
    
    GOOGLE_SCOPES = [
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/youtube',
        'https://www.googleapis.com/auth/userinfo.profile',  # For real name
    ]
    
    def __init__(self, plugin_dir, config_manager):
        super().__init__(plugin_dir, config_manager)
        
        # Services
        self.gmail_service = None
        self.calendar_service = None
        self.youtube_service = None
        self.people_service = None
        self.creds = None
        
        # Paths
        base_dir = os.path.dirname(os.path.dirname(plugin_dir))
        self.credentials_file = os.path.join(base_dir, "Plugins", "Google Services", "Credentials.json")
        self.token_file = os.path.join(base_dir, "Plugins", "Google Services", "Token.json")
        
        # GUI elements
        self.google_status_label = None
        self.google_action_btn = None
    
    def activate(self):
        self.log("Activating...")
        
        if not GOOGLE_LIBS_AVAILABLE:
            self.log("Google libraries not available", "warning")
        
        if self.get_config("authenticated", False):
            self._load_oauth_services()
        
        self.log("Activated", "info")
        return True
    
    def deactivate(self):
        self.gmail_service = None
        self.calendar_service = None
        self.youtube_service = None
        self.people_service = None
        self.creds = None
        return True
    
    # ============ GUI METHODS ============
    
    def get_frame_size(self):
        """Google Services - standard 380x80 frame"""
        return (380, 80)
    
    def create_gui_frame(self, parent, x, y):
        """Create Google Services GUI frame - SIMPLIFIED!"""
        from PyQt5.QtWidgets import QGroupBox, QLabel, QPushButton
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtCore import Qt
        
        # Styles
        GROUP_STYLE = """
            QGroupBox {
                background-color: #191919;
                border: 2px solid #FFFFFF;
                border-radius: 10px;
                margin-top: 0px;
                font-weight: bold;
                color: #FFFFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #FFFFFF;
                left: 6px;
                top: 8px;
                background-color: #191919;
            }
        """
        
        LABEL_STYLE = "color: #FFFFFF; border: none;"

        TEXT_EDIT_STYLE = """
            QTextEdit {
                background-color: #111111;
                color: #FFFFFF;
                border: 1px solid #FFFFFF;
                border-radius: 5px;
                font-family: 'Courier New';
                font-size: 10pt;
            }
        """

        # Create frame
        frame = QGroupBox("Google Services", parent)
        frame.setGeometry(x, y, 380, 80)
        frame.setStyleSheet(GROUP_STYLE)
        
        # Single Google logo
        google_logo = QLabel(frame)
        google_logo.setGeometry(8, 38, 32, 32)
        self._load_image(google_logo, "Google.png", "🔍")

        # Google Services Label
        services_label = QLabel("=====  Search  Mail  Calendar  Agenda  YouTube  =====", frame)
        services_label.setGeometry(48, 24, 320, 20)
        services_label.setStyleSheet(LABEL_STYLE)

        
        # Status label (dynamic: "Not Connected" or "User Name")
        authenticated = self.get_config("authenticated", False)
        user_name = self.get_config("user_name", "")
        
        if authenticated and user_name:
            status_text = user_name
            status_color = "#00FF00"  # Green
        else:
            status_text = "Not Connected"
            status_color = "#FF6666"  # Red
        
        self.google_status_label = QLabel(status_text, frame)
        self.google_status_label.setGeometry(80, 50, 160, 20)
        self.google_status_label.setStyleSheet(f"color: {status_color}; border: none; font-weight: bold;")
        
        # Dual-function button (Authenticate / Disconnect)
        if authenticated:
            button_text = "Disconnect"
            button_style = """
                QPushButton {
                    background-color: #FF0000;
                    color: #FFFFFF;
                    border-radius: 10px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #CC0000; }
            """
            button_action = self._on_disconnect_clicked
        else:
            button_text = "Authenticate"
            button_style = """
                QPushButton {
                    background-color: #00FF00;
                    color: #000000;
                    border-radius: 10px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #00CC00; }
            """
            button_action = self._on_authenticate_clicked
        
        self.google_action_btn = QPushButton(button_text, frame)
        self.google_action_btn.setGeometry(212, 50, 160, 20)
        self.google_action_btn.setStyleSheet(button_style)
        self.google_action_btn.clicked.connect(button_action)
        
        return frame
    
    def _load_image(self, label, filename, fallback):
        """Load image with fallback emoji"""
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtCore import Qt
        
        # Try plugin graphics
        plugin_graphics = os.path.join(self.plugin_dir, "Graphics", filename)
        
        if os.path.exists(plugin_graphics):
            pixmap = QPixmap(plugin_graphics)
            label.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            label.setText(fallback)
            label.setStyleSheet("color: #FFFFFF; border: none; font-size: 16pt;")
    
    def _on_authenticate_clicked(self):
        """OAuth authenticate button handler"""
        from PyQt5.QtWidgets import QMessageBox
        
        self.log("🔐 Starting OAuth...")
        
        try:
            success, result = self.authenticate()
            
            if success:
                self.log(f"✅ Authenticated: {result}")
                
                # Update status label
                if hasattr(self, 'google_status_label'):
                    self.google_status_label.setText(result)
                    self.google_status_label.setStyleSheet("color: #00FF00; border: none; font-weight: bold;")
                
                # Update button to Disconnect
                if hasattr(self, 'google_action_btn'):
                    self.google_action_btn.setText("Disconnect")
                    self.google_action_btn.setStyleSheet("""
                        QPushButton {
                            background-color: #FF0000;
                            color: #FFFFFF;
                            border-radius: 10px;
                            font-weight: bold;
                        }
                        QPushButton:hover { background-color: #CC0000; }
                    """)
                    # Reconnect to disconnect handler
                    self.google_action_btn.clicked.disconnect()
                    self.google_action_btn.clicked.connect(self._on_disconnect_clicked)
                
                QMessageBox.information(None, "Success", f"Authenticated as:\n{result}")
            else:
                self.log(f"❌ Failed: {result}")
                QMessageBox.warning(None, "Failed", str(result))
        except Exception as e:
            self.log(f"❌ Error: {e}")
            QMessageBox.critical(None, "Error", str(e))
    
    def _on_disconnect_clicked(self):
        """Disconnect button handler"""
        from PyQt5.QtWidgets import QMessageBox
        
        try:
            success, message = self.disconnect()
            
            if success:
                self.log("✅ Disconnected")
                
                # Update status label
                if hasattr(self, 'google_status_label'):
                    self.google_status_label.setText("Not Connected")
                    self.google_status_label.setStyleSheet("color: #FF6666; border: none; font-weight: bold;")
                
                # Update button to Authenticate
                if hasattr(self, 'google_action_btn'):
                    self.google_action_btn.setText("Authenticate")
                    self.google_action_btn.setStyleSheet("""
                        QPushButton {
                            background-color: #00FF00;
                            color: #000000;
                            border-radius: 10px;
                            font-weight: bold;
                        }
                        QPushButton:hover { background-color: #00CC00; }
                    """)
                    # Reconnect to authenticate handler
                    self.google_action_btn.clicked.disconnect()
                    self.google_action_btn.clicked.connect(self._on_authenticate_clicked)
                
                QMessageBox.information(None, "Success", "Disconnected")
            else:
                self.log(f"❌ Disconnect failed: {message}")
        except Exception as e:
            self.log(f"❌ Error: {e}")
    
    # ============ MCP TOOLS ============
    
    def get_tools(self):
        """Return all tools"""
        tools = [
            {
                "name": "google_search",
                "description": "Search the web using Google Custom Search",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "num_results": {"type": "integer", "default": 5}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "web_fetch",
                "description": "Fetch and extract text from URL",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"}
                    },
                    "required": ["url"]
                }
            }
        ]
        
        # Add OAuth tools if authenticated
        if self.get_config("authenticated", False):
            tools.extend([
                {
                    "name": "gmail_send",
                    "description": "Send email via Gmail",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string"},
                            "subject": {"type": "string"},
                            "body": {"type": "string"},
                            "body_html": {"type": "string"}
                        },
                        "required": ["to", "subject", "body"]
                    }
                },
                {
                    "name": "gmail_list",
                    "description": "List emails from inbox",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "max_results": {"type": "integer", "default": 10},
                            "query": {"type": "string", "default": ""}
                        }
                    }
                },
                {
                    "name": "calendar_list",
                    "description": "List calendar events",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "max_results": {"type": "integer", "default": 10}
                        }
                    }
                },
                {
                    "name": "calendar_create",
                    "description": "Create calendar event",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string"},
                            "start_time": {"type": "string"},
                            "end_time": {"type": "string"},
                            "description": {"type": "string"},
                            "location": {"type": "string"}
                        },
                        "required": ["summary", "start_time", "end_time"]
                    }
                },
                {
                    "name": "calendar_delete",
                    "description": "Delete calendar event",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "event_id": {"type": "string"}
                        },
                        "required": ["event_id"]
                    }
                },
                {
                    "name": "youtube_search",
                    "description": "Search YouTube videos",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "max_results": {"type": "integer", "default": 5}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "youtube_play",
                    "description": "Open YouTube video",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"}
                        },
                        "required": ["url"]
                    }
                }
            ])
        
        return tools
    
    def get_prompt_section(self):
        """Return detailed prompt section for Google Services"""
        is_authenticated = self.get_config("authenticated", False)
        
        prompt = """=== GOOGLE SERVICES ===

- google_search: Search the web using Google (arguments: query, num_results)
- web_fetch: Fetch and extract text content from any URL (arguments: url)

SEARCH EXAMPLES:
User: "Search for Python tutorials"
→ {"id": "call_1", "tool": "google_search", "arguments": {"query": "Python tutorials", "num_results": 5}}

User: "What's on this page: https://example.com"
→ {"id": "call_2", "tool": "web_fetch", "arguments": {"url": "https://example.com"}}
"""
        
        if is_authenticated:
            prompt += """
=== GMAIL (Authenticated) ===
- gmail_send: Send email via Gmail (arguments: to, subject, body, body_html)
- gmail_list: List recent emails (arguments: max_results, query)

GMAIL EXAMPLES:
User: "Send an email to john@example.com about the meeting"
→ {"id": "call_1", "tool": "gmail_send", "arguments": {"to": "john@example.com", "subject": "Meeting", "body": "..."}}

User: "Show my last 5 emails"
→ {"id": "call_2", "tool": "gmail_list", "arguments": {"max_results": 5}}

=== GOOGLE CALENDAR (Authenticated) ===
- calendar_list: List upcoming events (arguments: max_results)
- calendar_create: Create new event (arguments: summary, start_time, end_time, description, location)
- calendar_delete: Delete event (arguments: event_id)

CALENDAR EXAMPLES:
User: "Show my calendar for today"
→ {"id": "call_1", "tool": "calendar_list", "arguments": {"max_results": 10}}

User: "Schedule a meeting tomorrow at 2 PM"
→ {"id": "call_2", "tool": "calendar_create", "arguments": {"summary": "Meeting", "start_time": "2024-02-07T14:00:00", "end_time": "2024-02-07T15:00:00"}}

=== YOUTUBE (Authenticated) ===
- youtube_search: Search YouTube videos (arguments: query, max_results)
- youtube_play: Open YouTube video in browser (arguments: video_id)

YOUTUBE EXAMPLES:
User: "Find cat videos on YouTube"
→ {"id": "call_1", "tool": "youtube_search", "arguments": {"query": "funny cats", "max_results": 5}}

User: "Play the first video"
→ {"id": "call_2", "tool": "youtube_play", "arguments": {"video_id": "abc123"}}
"""
        
        return prompt
    
    def handle_tool_call(self, tool_name, arguments):
        """Route tool calls"""
        try:
            if tool_name == "google_search":
                return self._google_search(arguments)
            elif tool_name == "web_fetch":
                return self._web_fetch(arguments)
            elif tool_name == "gmail_send":
                return self._gmail_send(arguments)
            elif tool_name == "gmail_list":
                return self._gmail_list(arguments)
            elif tool_name == "calendar_list":
                return self._calendar_list(arguments)
            elif tool_name == "calendar_create":
                return self._calendar_create(arguments)
            elif tool_name == "calendar_delete":
                return self._calendar_delete(arguments)
            elif tool_name == "youtube_search":
                return self._youtube_search(arguments)
            elif tool_name == "youtube_play":
                return self._youtube_play(arguments)
            else:
                return {
                    "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                    "isError": True
                }
        except Exception as e:
            self.log(f"Error in {tool_name}: {e}", "error")
            return {
                "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                "isError": True
            }
    
    # ============ GOOGLE SEARCH ============
    
    def _google_search(self, args):
        """Google Custom Search using hardcoded API key"""
        query = args.get("query", "")
        num_results = args.get("num_results", 5)
        
        if GOOGLE_API_KEY == "DUMMY_API_KEY_REPLACE_ME":
            return {"content": [{"type": "text", "text": "⚠️ Google API Key not configured. Admin: Please update GOOGLE_API_KEY in plugin."}], "isError": True}
        
        if GOOGLE_CSE_ID == "DUMMY_CSE_ID_REPLACE_ME":
            return {"content": [{"type": "text", "text": "⚠️ Google CSE ID not configured. Admin: Please update GOOGLE_CSE_ID in plugin."}], "isError": True}
        
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            response = requests.get(url, params={"key": GOOGLE_API_KEY, "cx": GOOGLE_CSE_ID, "q": query, "num": num_results}, timeout=10)
            response.raise_for_status()
            
            results = [{"title": item.get("title", ""), "url": item.get("link", ""), "snippet": item.get("snippet", "")} for item in response.json().get("items", [])]
            
            return {"content": [{"type": "text", "text": json.dumps(results, indent=2)}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Search failed: {str(e)}"}], "isError": True}
    
    def _web_fetch(self, args):
        """Fetch web page"""
        url = args.get("url", "")
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            if len(text) > 5000:
                text = text[:5000] + "\n\n[Truncated...]"
            
            return {"content": [{"type": "text", "text": text}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Fetch failed: {str(e)}"}], "isError": True}
    
    # ============ GMAIL ============
    
    def _gmail_send(self, args):
        """Send email"""
        if not self.gmail_service:
            return {"content": [{"type": "text", "text": "Gmail not authenticated"}], "isError": True}
        
        try:
            to = args.get("to")
            subject = args.get("subject")
            body = args.get("body")
            body_html = args.get("body_html")
            
            if body_html:
                message = MIMEMultipart('alternative')
                message.attach(MIMEText(body, 'plain'))
                message.attach(MIMEText(body_html, 'html'))
            else:
                message = MIMEText(body)
            
            message['to'] = to
            message['subject'] = subject
            
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            result = self.gmail_service.users().messages().send(
                userId='me', body={'raw': raw}
            ).execute()
            
            return {"content": [{"type": "text", "text": f"✅ Email sent successfully\nMessage ID: {result.get('id', '')}"}]}
            
        except Exception as e:
            return {"content": [{"type": "text", "text": f"❌ Send failed: {str(e)}"}], "isError": True}
    
    def _gmail_list(self, args):
        """List emails"""
        if not self.gmail_service:
            return {"content": [{"type": "text", "text": "Gmail not authenticated"}], "isError": True}
        
        try:
            max_results = args.get("max_results", 10)
            query = args.get("query", "")
            
            results = self.gmail_service.users().messages().list(
                userId='me', maxResults=max_results, q=query
            ).execute()
            
            messages = []
            for msg in results.get('messages', []):
                detail = self.gmail_service.users().messages().get(
                    userId='me', id=msg['id'], format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date']
                ).execute()
                
                headers = detail.get('payload', {}).get('headers', [])
                messages.append({
                    'id': msg['id'],
                    'from': next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown'),
                    'subject': next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject'),
                    'date': next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown'),
                    'snippet': detail.get('snippet', '')
                })
            
            return {"content": [{"type": "text", "text": json.dumps(messages, indent=2)}]}
            
        except Exception as e:
            return {"content": [{"type": "text", "text": f"❌ List failed: {str(e)}"}], "isError": True}
    
    # ============ CALENDAR ============
    
    def _calendar_list(self, args):
        """List events"""
        if not self.calendar_service:
            return {"content": [{"type": "text", "text": "Calendar not authenticated"}], "isError": True}
        
        try:
            max_results = args.get("max_results", 10)
            
            time_min = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            time_max = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
            
            result = self.calendar_service.events().list(
                calendarId='primary', timeMin=time_min, timeMax=time_max,
                maxResults=max_results, singleEvents=True, orderBy='startTime'
            ).execute()
            
            events = []
            for event in result.get('items', []):
                events.append({
                    'id': event['id'],
                    'summary': event.get('summary', 'No title'),
                    'start': event['start'].get('dateTime', event['start'].get('date')),
                    'end': event['end'].get('dateTime', event['end'].get('date')),
                    'description': event.get('description', ''),
                    'location': event.get('location', '')
                })
            
            return {"content": [{"type": "text", "text": json.dumps(events, indent=2)}]}
            
        except Exception as e:
            return {"content": [{"type": "text", "text": f"❌ List failed: {str(e)}"}], "isError": True}
    
    def _calendar_create(self, args):
        """Create event"""
        if not self.calendar_service:
            return {"content": [{"type": "text", "text": "Calendar not authenticated"}], "isError": True}
        
        try:
            event = {
                'summary': args.get("summary"),
                'location': args.get("location", ""),
                'description': args.get("description", ""),
                'start': {'dateTime': args.get("start_time"), 'timeZone': 'Europe/Bucharest'},
                'end': {'dateTime': args.get("end_time"), 'timeZone': 'Europe/Bucharest'},
            }
            
            result = self.calendar_service.events().insert(
                calendarId='primary', body=event
            ).execute()
            
            return {"content": [{"type": "text", "text": f"✅ Event created\nID: {result.get('id', '')}\nLink: {result.get('htmlLink', '')}"}]}
            
        except Exception as e:
            return {"content": [{"type": "text", "text": f"❌ Create failed: {str(e)}"}], "isError": True}
    
    def _calendar_delete(self, args):
        """Delete event"""
        if not self.calendar_service:
            return {"content": [{"type": "text", "text": "Calendar not authenticated"}], "isError": True}
        
        try:
            self.calendar_service.events().delete(
                calendarId='primary', eventId=args.get("event_id")
            ).execute()
            
            return {"content": [{"type": "text", "text": "✅ Event deleted successfully"}]}
            
        except Exception as e:
            return {"content": [{"type": "text", "text": f"❌ Delete failed: {str(e)}"}], "isError": True}
    
    # ============ YOUTUBE ============
    
    def _youtube_search(self, args):
        """Search YouTube"""
        if not self.youtube_service:
            return {"content": [{"type": "text", "text": "YouTube not authenticated"}], "isError": True}
        
        try:
            result = self.youtube_service.search().list(
                q=args.get("query"), part='snippet',
                maxResults=args.get("max_results", 5), type='video'
            ).execute()
            
            videos = []
            for item in result.get('items', []):
                video_id = item['id']['videoId']
                videos.append({
                    'title': item['snippet']['title'],
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'description': item['snippet']['description'],
                    'channel': item['snippet']['channelTitle'],
                    'published': item['snippet']['publishedAt']
                })
            
            return {"content": [{"type": "text", "text": json.dumps(videos, indent=2)}]}
            
        except Exception as e:
            return {"content": [{"type": "text", "text": f"❌ Search failed: {str(e)}"}], "isError": True}
    
    def _youtube_play(self, args):
        """Open YouTube video"""
        try:
            webbrowser.open(args.get("url", ""))
            return {"content": [{"type": "text", "text": "✅ Opening video in browser..."}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"❌ Failed: {str(e)}"}], "isError": True}
    
    # ============ OAUTH MANAGEMENT ============
    
    def authenticate(self):
        """OAuth authentication with People API for real name"""
        if not GOOGLE_LIBS_AVAILABLE:
            return False, "Google libraries not installed"
        
        if not os.path.exists(self.credentials_file):
            return False, f"Credentials file not found at:\n{self.credentials_file}"
        
        try:
            creds = None
            
            if os.path.exists(self.token_file):
                creds = Credentials.from_authorized_user_file(self.token_file, self.GOOGLE_SCOPES)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, self.GOOGLE_SCOPES)
                    creds = flow.run_local_server(port=0)
                
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
            
            # Build services
            self.gmail_service = build('gmail', 'v1', credentials=creds)
            self.calendar_service = build('calendar', 'v3', credentials=creds)
            self.youtube_service = build('youtube', 'v3', credentials=creds)
            self.people_service = build('people', 'v1', credentials=creds)
            self.creds = creds
            
            # Get email from Gmail
            gmail_profile = self.gmail_service.users().getProfile(userId='me').execute()
            email = gmail_profile.get('emailAddress', 'unknown')
            
            # Get REAL NAME from People API
            try:
                people_profile = self.people_service.people().get(
                    resourceName='people/me',
                    personFields='names'
                ).execute()
                
                # Extract display name
                if 'names' in people_profile and len(people_profile['names']) > 0:
                    user_name = people_profile['names'][0].get('displayName', email.split('@')[0])
                else:
                    # Fallback to email username
                    user_name = email.split('@')[0]
            except Exception as e:
                self.log(f"⚠️ Could not get real name: {e}", "warning")
                # Fallback to email username
                user_name = email.split('@')[0]
            
            # Save config (only auth status and user name, NO API keys)
            self.set_config("authenticated", True)
            self.set_config("user_email", email)
            self.set_config("user_name", user_name)
            
            self.log(f"Authenticated: {user_name} ({email})", "info")
            return True, user_name  # Return real name
            
        except Exception as e:
            self.log(f"Auth failed: {e}", "error")
            return False, str(e)
    
    def disconnect(self):
        """Disconnect OAuth"""
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
            
            self.gmail_service = None
            self.calendar_service = None
            self.youtube_service = None
            self.people_service = None
            self.creds = None
            
            self.set_config("authenticated", False)
            self.set_config("user_email", "")
            self.set_config("user_name", "")
            
            return True, "Disconnected successfully"
        except Exception as e:
            return False, str(e)
    
    def _load_oauth_services(self):
        """Load OAuth services from token"""
        if not os.path.exists(self.token_file):
            return
        
        try:
            creds = Credentials.from_authorized_user_file(self.token_file, self.GOOGLE_SCOPES)
            
            if creds and creds.valid:
                self.gmail_service = build('gmail', 'v1', credentials=creds)
                self.calendar_service = build('calendar', 'v3', credentials=creds)
                self.youtube_service = build('youtube', 'v3', credentials=creds)
                self.people_service = build('people', 'v1', credentials=creds)
                self.creds = creds
                self.log("OAuth services loaded", "info")
        except Exception as e:
            self.log(f"Failed to load OAuth: {e}", "warning")