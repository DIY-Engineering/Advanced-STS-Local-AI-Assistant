"""
Windows Tools Plugin - SECURE VERSION
With blacklist system, shell=False, and file validation
"""

import platform
import psutil
import subprocess
import datetime
import os
import webbrowser
import difflib


# Try pycaw for volume
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    PYCAW_AVAILABLE = True
except:
    PYCAW_AVAILABLE = False

# ============ DEFAULT BLACKLIST ============
# Dangerous commands that should not be executed in Restricted mode
DEFAULT_BLACKLIST = [
    "format",
    "del",
    "rm",
    "rmdir",
    "rd",
    "erase",
    "deltree",
    "shutdown",
    "reboot",
    "restart",
    "logoff",
    "taskkill",
    "net",
    "netsh",
    "reg",
    "regedit",
    "diskpart",
    "cipher",
    "bcdedit",
    "wmic",
    "powercfg",
    "schtasks",
    "attrib",
]

# Safe media file extensions
SAFE_MEDIA_EXTENSIONS = [
    '.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a',  # Audio
    '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv',  # Video
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',  # Images
    '.pdf', '.txt', '.docx', '.xlsx', '.pptx',  # Documents
]

# Media extensions grouped by type - open_media_file now searches ALL standard
# folders simultaneously (non-recursive), so no "primary folder" per type is needed anymore
MEDIA_TYPE_MAP = {
    "photo": ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'],
    "video": ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv'],
    "audio": ['.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'],
}

# Standard user folders - enum driven, no raw path input from the LLM
FOLDER_MAP = {
    "documents": "Documents",
    "downloads": "Downloads",
    "videos":    "Videos",
    "pictures":  "Pictures",
    "music":     "Music",
    "desktop":   "Desktop",
}

# Same 6 folders as a flat list - used for open_media_file's simultaneous search
# AND as the security boundary for get_file_details / read_text_file (prevents
# reading arbitrary system paths like .ssh keys or browser profile data)
STANDARD_USER_FOLDERS = ["Desktop", "Documents", "Downloads", "Music", "Pictures", "Videos"]

# Text file extensions readable via read_text_file - kept deliberately small,
# no Office/PDF parsing to avoid adding new dependencies (python-docx, PyPDF2, etc.)
TEXT_FILE_EXTENSIONS = ['.txt', '.md', '.csv', '.json', '.log', '.py']

# Hard cap on read_text_file - protects context window and avoids surprise
# cloud/token costs once this content can be routed to a cloud LLM later
MAX_TEXT_FILE_SIZE = 50 * 1024  # 50 KB

# Built-in Windows utilities - fixed command per tool, shell=False, no user-controlled strings
SYSTEM_TOOLS_MAP = {
    "taskmgr":    ["taskmgr"],
    "calculator": ["calc"],
    "notepad":    ["notepad"],
    "paint":      ["mspaint"],
    "control":    ["control"],
    "devmgmt":    ["mmc", "devmgmt.msc"],
}



class WindowsToolsPlugin(BasePlugin):
    """Windows system tools with SECURE blacklist system"""
    
    def activate(self):
        self.log("Activating...")
        
        if not PYCAW_AVAILABLE:
            self.log("pycaw not available - volume control disabled", "warning")
        
        # Load or initialize blacklist
        blacklist = self.get_config("cli_blacklist", [])
        if not blacklist:
            # Set default blacklist
            self.set_config("cli_blacklist", DEFAULT_BLACKLIST)
        
        # Build Start Menu shortcut index once - powers fuzzy open_app lookups
        self._build_app_index()
        
        self.log("Activated", "info")
        return True
    
    def deactivate(self):
        return True
    
    # ============ GUI METHODS ============
    
    def get_frame_size(self):
        """Standard 380x80 frame"""
        return (380, 80)
    
    def create_gui_frame(self, parent, x, y):
        """Create Windows Tools GUI frame - SECURE with blacklist button!"""
        from PyQt5.QtWidgets import (QGroupBox, QLabel, QPushButton, 
                                     QButtonGroup, QRadioButton)
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtCore import Qt
        import os
        
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
        
        BUTTON_STYLE = """
            QPushButton {
                background-color: #787878;
                color: #FFFFFF;
                border-radius: 10px;
                font-weight: bold;
                padding: 3px;
            }
            QPushButton:hover { background-color: #8C8C8C; }
            QPushButton:pressed { background-color: #666666; }
        """
        
        # Create frame
        frame = QGroupBox("Windows Tools", parent)
        frame.setGeometry(x, y, 380, 80)
        frame.setStyleSheet(GROUP_STYLE)
        
        # Logo
        logo = QLabel(frame)
        logo.setGeometry(8, 38, 32, 32)
        
        # Try to load CLI logo
        plugin_graphics = os.path.join(self.plugin_dir, "Graphics", "CLI.png")
        if os.path.exists(plugin_graphics):
            pixmap = QPixmap(plugin_graphics)
            logo.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo.setText("💻")
            logo.setStyleSheet("color: #FFFFFF; border: none; font-size: 16pt;")
        
        # Access Level Label
        access_label = QLabel("= Access Level =", frame)
        access_label.setGeometry(84, 30, 110, 20)
        access_label.setStyleSheet(LABEL_STYLE)
        
        # Radio buttons with CORRECT colors
        cli_access_group = QButtonGroup(frame)
        
        current_access = self.get_config("cli_access_level", "restricted")
        
        # Restricted mode (VERDE - safe)
        radio_restricted = QRadioButton("Restricted", frame)
        radio_restricted.setGeometry(48, 50, 90, 20)
        
        if current_access == "restricted":
            # Active: GREEN (safe)
            radio_restricted.setStyleSheet("""
                QRadioButton {
                    color: #00FF00;
                    font-weight: bold;
                }
                QRadioButton::indicator {
                    width: 6px;
                    height: 6px;
                }
                QRadioButton::indicator::unchecked {
                    border: 2px solid #00FF00;
                    border-radius: 7px;
                    background-color: #191919;
                }
                QRadioButton::indicator::checked {
                    border: 2px solid #00FF00;
                    border-radius: 7px;
                    background-color: #00FF00;
                }
            """)
        else:
            # Inactive: Gray
            radio_restricted.setStyleSheet("""
                QRadioButton {
                    color: #666666;
                }
                QRadioButton::indicator {
                    width: 6px;
                    height: 6px;
                }
                QRadioButton::indicator::unchecked {
                    border: 2px solid #666666;
                    border-radius: 7px;
                    background-color: #191919;
                }
            """)
        
        radio_restricted.setChecked(current_access == "restricted")
        radio_restricted.toggled.connect(lambda checked: self._on_access_changed("restricted") if checked else None)
        cli_access_group.addButton(radio_restricted, 0)
        
        # Full Access mode (ROȘU - dangerous)
        radio_full = QRadioButton("Full Access", frame)
        radio_full.setGeometry(130, 50, 90, 20)
        
        if current_access == "full":
            # Active: RED (dangerous)
            radio_full.setStyleSheet("""
                QRadioButton {
                    color: #FF0000;
                    font-weight: bold;
                }
                QRadioButton::indicator {
                    width: 6px;
                    height: 6px;
                }
                QRadioButton::indicator::unchecked {
                    border: 2px solid #FF0000;
                    border-radius: 7px;
                    background-color: #191919;
                }
                QRadioButton::indicator::checked {
                    border: 2px solid #FF0000;
                    border-radius: 7px;
                    background-color: #FF0000;
                }
            """)
        else:
            # Inactive: Gray
            radio_full.setStyleSheet("""
                QRadioButton {
                    color: #666666;
                }
                QRadioButton::indicator {
                    width: 6px;
                    height: 6px;
                }
                QRadioButton::indicator::unchecked {
                    border: 2px solid #666666;
                    border-radius: 7px;
                    background-color: #191919;
                }
            """)
        
        radio_full.setChecked(current_access == "full")
        radio_full.toggled.connect(lambda checked: self._on_access_changed("full") if checked else None)
        cli_access_group.addButton(radio_full, 1)
        
        # Store references for dynamic updates
        self.radio_restricted = radio_restricted
        self.radio_full = radio_full
        
        # Blacklist button (bottom right)
        blacklist_btn = QPushButton("Blacklist", frame)
        blacklist_btn.setGeometry(212, 50, 160, 20)
        blacklist_btn.setStyleSheet(BUTTON_STYLE)
        blacklist_btn.clicked.connect(self._on_blacklist_clicked)
        
        return frame
    
    def _on_access_changed(self, new_level):
        """Handle access level change with dynamic styling"""
        self.set_config("cli_access_level", new_level)
        self.log(f"🔒 Access level: {new_level}")
        
        # Update radio button styles dynamically
        if new_level == "restricted":
            # Restricted active (GREEN)
            self.radio_restricted.setStyleSheet("""
                QRadioButton {
                    color: #00FF00;
                    font-weight: bold;
                }
                QRadioButton::indicator {
                    width: 6px;
                    height: 6px;
                }
                QRadioButton::indicator::unchecked {
                    border: 2px solid #00FF00;
                    border-radius: 7px;
                    background-color: #191919;
                }
                QRadioButton::indicator::checked {
                    border: 2px solid #00FF00;
                    border-radius: 7px;
                    background-color: #00FF00;
                }
            """)
            # Full inactive (GRAY)
            self.radio_full.setStyleSheet("""
                QRadioButton {
                    color: #666666;
                }
                QRadioButton::indicator {
                    width: 6px;
                    height: 6px;
                }
                QRadioButton::indicator::unchecked {
                    border: 2px solid #666666;
                    border-radius: 7px;
                    background-color: #191919;
                }
            """)
        else:
            # Full active (RED)
            self.radio_full.setStyleSheet("""
                QRadioButton {
                    color: #FF0000;
                    font-weight: bold;
                }
                QRadioButton::indicator {
                    width: 6px;
                    height: 6px;
                }
                QRadioButton::indicator::unchecked {
                    border: 2px solid #FF0000;
                    border-radius: 7px;
                    background-color: #191919;
                }
                QRadioButton::indicator::checked {
                    border: 2px solid #FF0000;
                    border-radius: 7px;
                    background-color: #FF0000;
                }
            """)
            # Restricted inactive (GRAY)
            self.radio_restricted.setStyleSheet("""
                QRadioButton {
                    color: #666666;
                }
                QRadioButton::indicator {
                    width: 6px;
                    height: 6px;
                }
                QRadioButton::indicator::unchecked {
                    border: 2px solid #666666;
                    border-radius: 7px;
                    background-color: #191919;
                }
            """)
    
    def _on_blacklist_clicked(self):
        """Open blacklist editor dialog"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QLabel, QApplication
        
        dialog = QDialog()
        dialog.setWindowTitle("Command Blacklist Editor")
        dialog.resize(400, 300)
        dialog.setStyleSheet("QDialog { background-color: #191919; }")
        
        # Centreaza fereastra pe ecran
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - 400) // 2
        y = (screen.height() - 300) // 2
        dialog.move(x, y)
        
        layout = QVBoxLayout()
        
        # Info label
        info = QLabel("⚠️ Commands in blacklist are BLOCKED in Restricted mode.\nFull Access mode IGNORES blacklist (executes everything).")
        info.setStyleSheet("color: #FFFFFF; padding: 10px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Text editor
        editor = QTextEdit()
        editor.setStyleSheet("""
            QTextEdit {
                background-color: #121212;
                color: #FFFFFF;
                border: 1px solid #FFFFFF;
                border-radius: 5px;
                font-family: 'Courier New';
            }
        """)
        
        # Load current blacklist
        blacklist = self.get_config("cli_blacklist", DEFAULT_BLACKLIST)
        editor.setPlainText("\n".join(blacklist))
        layout.addWidget(editor)
        
        # Save button
        save_btn = QPushButton("Save Blacklist")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #00FF00;
                color: #000000;
                border-radius: 5px;
                font-weight: bold;
                padding: 5px;
            }
            QPushButton:hover { background-color: #00CC00; }
        """)
        save_btn.clicked.connect(lambda: self._save_blacklist(editor.toPlainText(), dialog))
        layout.addWidget(save_btn)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def _save_blacklist(self, text, dialog):
        """Save blacklist from editor"""
        # Parse commands (one per line, strip whitespace)
        commands = [line.strip().lower() for line in text.split('\n') if line.strip()]
        
        self.set_config("cli_blacklist", commands)
        self.log(f"✅ Blacklist updated: {len(commands)} commands")
        
        dialog.accept()
    
    # ============ MCP TOOLS ============
    
    def get_tools(self):
        """Return Windows tools"""
        tools = [
            {"name": "system_info", "description": "Get complete system info", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "system_os", "description": "Get OS information", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "system_cpu", "description": "Get CPU information", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "system_ram", "description": "Get RAM information", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "system_storage", "description": "Get storage information", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "system_gpu", "description": "Get GPU information", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "system_network", "description": "Get network information", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "system_datetime", "description": "Get current date/time", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "system_shutdown", "description": "Shutdown computer", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "system_volume_get", "description": "Get volume level", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "system_volume_set", "description": "Set volume", "inputSchema": {"type": "object", "properties": {"level": {"type": "integer", "minimum": 0, "maximum": 100}}, "required": ["level"]}},
            {"name": "windows_media_play", "description": "Play media file", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
            {"name": "windows_cli", "description": "Execute CLI command", "inputSchema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
            {"name": "windows_processes", "description": "List running processes sorted by RAM or CPU usage", "inputSchema": {"type": "object", "properties": {"sort_by": {"type": "string", "enum": ["ram", "cpu"], "default": "ram"}, "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10}}}},
            {"name": "system_health_check", "description": "System health diagnostics", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "open_system_tool", "description": "Open a built-in Windows system utility", "inputSchema": {"type": "object", "properties": {"tool": {"type": "string", "enum": ["taskmgr", "calculator", "notepad", "paint", "control", "devmgmt"]}}, "required": ["tool"]}},
            {"name": "open_app", "description": "Open an installed application by name, fuzzy-matched against Start Menu shortcuts", "inputSchema": {"type": "object", "properties": {"app_name": {"type": "string", "description": "Name of the application, e.g. 'blender', 'discord', 'lm studio'"}}, "required": ["app_name"]}},
            {"name": "open_folder", "description": "Open a standard user folder in File Explorer", "inputSchema": {"type": "object", "properties": {"folder": {"type": "string", "enum": ["documents", "downloads", "videos", "pictures", "music", "desktop"]}}, "required": ["folder"]}},
            {"name": "open_media_file", "description": "Search for a photo, video, or audio file by name across all standard user folders (Desktop, Documents, Downloads, Music, Pictures, Videos). Returns a list of matches - use windows_media_play with the chosen path to open it.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "description": "Filename or partial filename to search for"}, "media_type": {"type": "string", "enum": ["photo", "video", "audio"]}}, "required": ["query", "media_type"]}},
            {"name": "get_file_details", "description": "Get metadata for a file (size, extension, created/modified dates) without reading its content. Read-only. Provide EITHER 'path' (e.g. from open_media_file results) OR 'folder' + 'filename' (preferred when you don't already have a full path - avoids guessing the Windows username).", "inputSchema": {"type": "object", "properties": {"path": {"type": "string", "description": "Full path to the file, e.g. from open_media_file results"}, "folder": {"type": "string", "enum": ["documents", "downloads", "videos", "pictures", "music", "desktop"], "description": "Standard folder - use with filename instead of guessing a full path"}, "filename": {"type": "string", "description": "Filename within the folder, e.g. 'readme.md'"}}}},
            {"name": "read_text_file", "description": "Read the text content of a small file (.txt, .md, .csv, .json, .log, .py) from a standard user folder. Max 50 KB. Provide EITHER 'path' (e.g. from open_media_file results) OR 'folder' + 'filename' (preferred when you don't already have a full path - avoids guessing the Windows username).", "inputSchema": {"type": "object", "properties": {"path": {"type": "string", "description": "Full path to the text file"}, "folder": {"type": "string", "enum": ["documents", "downloads", "videos", "pictures", "music", "desktop"], "description": "Standard folder - use with filename instead of guessing a full path"}, "filename": {"type": "string", "description": "Filename within the folder, e.g. 'todo.txt'"}}}}
        ]
        
        return tools
    
    def get_prompt_section(self):
        """Return detailed prompt section for Windows Tools"""
        access_level = self.get_config("cli_access_level", "restricted")
        
        prompt = """=== WINDOWS SYSTEM TOOLS ===

- windows_cli: Execute Windows CLI commands
  * Access level: """ + access_level.upper() + """
  * Available commands: ipconfig, tasklist, dir, ping, netstat, systeminfo, and more
  * Can manage processes, services, network, and system
  * RESTRICTED mode has blacklist protection

- windows_processes: List running processes sorted by RAM or CPU usage
  * Arguments: sort_by (ram/cpu), limit (1-50, default 10)
  * Shows process name, PID, RAM%, CPU%
  * Perfect for finding resource hogs!

- system_info: Get complete system information (OS, CPU, RAM, storage, GPU, network)
- system_health_check: Comprehensive diagnostics (RAM, CPU, disk, uptime)
  * Returns: healthy/warning/critical status
  * Recommends actions (restart, cleanup, etc.)

=== SYSTEM INFO & CONTROL ===
- system_os: Get OS information
- system_cpu: Get CPU information
- system_ram: Get RAM information
- system_storage: Get storage information
- system_gpu: Get GPU information
- system_network: Get network information
- system_datetime: Get current date/time
- system_shutdown: Shutdown computer (with confirmation)

=== MEDIA & VOLUME ===
- system_volume_set: Set volume (0-100, arguments: level)
- system_volume_get: Get current volume level
- windows_media_play: Play media files in default player (arguments: path)

=== LAUNCHERS (apps, folders, media search) ===
- open_system_tool: Open a built-in Windows utility
  * Arguments: tool (enum: taskmgr, calculator, notepad, paint, control, devmgmt)
  * Instant - no search needed, use this for these 6 utilities specifically

- open_app: Open an installed application by name
  * Arguments: app_name (free text, e.g. "blender", "discord", "lm studio")
  * Fuzzy-matched against Start Menu shortcuts - works for any installed program
  * Use this for anything NOT in the open_system_tool list

- open_folder: Open a standard user folder in File Explorer
  * Arguments: folder (enum: documents, downloads, videos, pictures, music, desktop)

- open_media_file: Search for a photo, video, or audio file by name
  * Arguments: query (filename to search for), media_type (enum: photo, video, audio)
  * Searches ALL standard folders at once (Desktop, Documents, Downloads, Music, Pictures, Videos)
  * Returns a LIST of matches - does NOT open the file itself
  * If there's more than one match, ask the user which one they want
  * Then call windows_media_play with the chosen "path" from the results to actually open it

=== FILE DETAILS & TEXT READING ===
- get_file_details: Get metadata for a file - size, extension, created/modified dates
  * Arguments: EITHER path (full path, e.g. from open_media_file results)
               OR folder (enum: documents/downloads/videos/pictures/music/desktop) + filename
  * PREFER folder + filename when the user just names a file - NEVER guess the
    Windows account folder name (it's often NOT the same as the person's first
    name in conversation, e.g. account folder "Nechifor Marian" vs chat name "Marian")
  * Read-only, no content returned - just metadata

- read_text_file: Read the text content of a small file
  * Arguments: EITHER path (full path to a .txt/.md/.csv/.json/.log/.py file)
               OR folder (enum: documents/downloads/videos/pictures/music/desktop) + filename
  * Same rule as above: PREFER folder + filename, never guess the account folder name
  * Scoped to standard user folders only, max 50 KB
  * Use this when the user wants to know what's IN a file, not just its size/dates

WINDOWS TOOLS USAGE EXAMPLES:

User: "What's hogging up all my RAM?"
→ {"id": "call_1", "tool": "windows_processes", "arguments": {"sort_by": "ram", "limit": 10}}

User: "Show me the top 5 CPU-intensive processes"
→ {"id": "call_2", "tool": "windows_processes", "arguments": {"sort_by": "cpu", "limit": 5}}

User: "Show network configuration"
→ {"id": "call_3", "tool": "windows_cli", "arguments": {"command": "ipconfig /all"}}

User: "List running processes"
→ {"id": "call_4", "tool": "windows_cli", "arguments": {"command": "tasklist"}}

User: "Check disk space"
→ {"id": "call_5", "tool": "windows_cli", "arguments": {"command": "wmic logicaldisk get size,freespace,caption"}}

User: "System feels slow, check what's wrong"
→ {"id": "call_6", "tool": "system_health_check", "arguments": {}}

User: "Set volume to 75%"
→ {"id": "call_7", "tool": "system_volume_set", "arguments": {"level": 75}}

User: "Play this music file: C:\\Music\\song.mp3"
→ {"id": "call_8", "tool": "windows_media_play", "arguments": {"path": "C:\\\\Music\\\\song.mp3"}}

User: "Get complete system info"
→ {"id": "call_9", "tool": "system_info", "arguments": {}}

User: "Open Task Manager"
→ {"id": "call_10", "tool": "open_system_tool", "arguments": {"tool": "taskmgr"}}

User: "Open Blender"
→ {"id": "call_11", "tool": "open_app", "arguments": {"app_name": "blender"}}

User: "Open my Downloads folder"
→ {"id": "call_12", "tool": "open_folder", "arguments": {"folder": "downloads"}}

User: "Find the photo of my Kugoo scooter"
→ {"id": "call_13", "tool": "open_media_file", "arguments": {"query": "kugoo", "media_type": "photo"}}
Results come back with 2 matches → ask user which one, then:
→ {"id": "call_14", "tool": "windows_media_play", "arguments": {"path": "<path_from_chosen_match>"}}

User: "How big is that notes.txt file on my Desktop?"
→ {"id": "call_15", "tool": "get_file_details", "arguments": {"folder": "desktop", "filename": "notes.txt"}}

User: "What's written in my todo.txt on the desktop?"
→ {"id": "call_16", "tool": "read_text_file", "arguments": {"folder": "desktop", "filename": "todo.txt"}}
"""
        
        return prompt
    
    def handle_tool_call(self, tool_name, arguments):
        """Execute tool"""
        try:
            if tool_name == "system_info":
                result = self._get_system_info()
            elif tool_name == "system_os":
                result = self._get_os_info()
            elif tool_name == "system_cpu":
                result = self._get_cpu_info()
            elif tool_name == "system_ram":
                result = self._get_ram_info()
            elif tool_name == "system_storage":
                result = self._get_storage_info()
            elif tool_name == "system_gpu":
                result = self._get_gpu_info()
            elif tool_name == "system_network":
                result = self._get_network_info()
            elif tool_name == "system_datetime":
                result = self._get_datetime()
            elif tool_name == "system_shutdown":
                result = self._shutdown_system()
            elif tool_name == "system_volume_get":
                result = self._get_volume()
            elif tool_name == "system_volume_set":
                result = self._set_volume(arguments.get("level", 50))
            elif tool_name == "windows_media_play":
                result = self._play_media(arguments)
            elif tool_name == "windows_cli":
                result = self._execute_cli(arguments)
            elif tool_name == "windows_processes":
                result = self._list_processes(arguments)
            elif tool_name == "system_health_check":
                result = self._health_check()
            elif tool_name == "open_system_tool":
                result = self._open_system_tool(arguments.get("tool", ""))
            elif tool_name == "open_app":
                result = self._open_app(arguments)
            elif tool_name == "open_folder":
                result = self._open_folder(arguments)
            elif tool_name == "open_media_file":
                result = self._open_media_file(arguments)
            elif tool_name == "get_file_details":
                result = self._get_file_details(arguments)
            elif tool_name == "read_text_file":
                result = self._read_text_file(arguments)
            else:
                result = {"ok": False, "error": f"Unknown tool: {tool_name}"}
            
            import json
            if result.get("ok"):
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            else:
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}], "isError": True}
                
        except Exception as e:
            self.log(f"Error in {tool_name}: {e}", "error")
            return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "isError": True}
    
    # ============ SYSTEM INFO ============
    
    def _get_system_info(self):
        try:
            return {
                "ok": True,
                "os": self._get_os_info().get("os", {}),
                "cpu": self._get_cpu_info().get("cpu", {}),
                "ram": self._get_ram_info().get("ram", {}),
                "storage": self._get_storage_info().get("storage", []),
                "gpu": self._get_gpu_info().get("gpu", []),
                "network": self._get_network_info().get("network", [])
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _get_os_info(self):
        try:
            return {
                "ok": True,
                "os": {
                    "system": platform.system(),
                    "release": platform.release(),
                    "version": platform.version(),
                    "machine": platform.machine(),
                    "processor": platform.processor()
                }
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _get_cpu_info(self):
        try:
            return {
                "ok": True,
                "cpu": {
                    "cores_physical": psutil.cpu_count(logical=False),
                    "cores_logical": psutil.cpu_count(logical=True),
                    "percent": psutil.cpu_percent(interval=1)
                }
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _get_ram_info(self):
        try:
            ram = psutil.virtual_memory()
            return {
                "ok": True,
                "ram": {
                    "total_gb": round(ram.total / (1024 ** 3), 2),
                    "available_gb": round(ram.available / (1024 ** 3), 2),
                    "used_gb": round(ram.used / (1024 ** 3), 2),
                    "percent": ram.percent
                }
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _get_storage_info(self):
        try:
            storage = []
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    storage.append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "fstype": partition.fstype,
                        "total_gb": round(usage.total / (1024 ** 3), 2),
                        "used_gb": round(usage.used / (1024 ** 3), 2),
                        "free_gb": round(usage.free / (1024 ** 3), 2),
                        "percent": usage.percent
                    })
                except:
                    pass
            return {"ok": True, "storage": storage}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _get_gpu_info(self):
        try:
            gpu_info = []
            
            try:
                output = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used,memory.free", "--format=csv,noheader"],
                    timeout=5
                ).decode().strip()
                
                for line in output.split("\n"):
                    parts = line.split(", ")
                    if len(parts) >= 5:
                        gpu_info.append({
                            "name": parts[0],
                            "driver": parts[1],
                            "memory_total": parts[2],
                            "memory_used": parts[3],
                            "memory_free": parts[4]
                        })
            except:
                gpu_info = [{"info": "GPU info not available (nvidia-smi required)"}]
            
            return {"ok": True, "gpu": gpu_info}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _get_network_info(self):
        try:
            network = []
            for interface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == 2:  # IPv4
                        network.append({
                            "interface": interface,
                            "ip": addr.address,
                            "netmask": addr.netmask
                        })
            return {"ok": True, "network": network}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _get_datetime(self):
        try:
            current = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return {"ok": True, "datetime": current}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _shutdown_system(self):
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["shutdown", "/s", "/f", "/t", "0"])
            elif platform.system() in ["Linux", "Darwin"]:
                subprocess.Popen(["sudo", "shutdown", "-h", "now"])
            return {"ok": True, "message": "Shutdown initiated"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _get_volume(self):
        if not PYCAW_AVAILABLE:
            return {"ok": False, "error": "pycaw not available"}
        
        try:
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            level = int(volume.GetMasterVolumeLevelScalar() * 100)
            return {"ok": True, "volume": level}
        except AttributeError:
            # NEW pycaw API (v0.3.0+)
            try:
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                from ctypes import cast, POINTER
                
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(
                    IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = cast(interface, POINTER(IAudioEndpointVolume))
                level = int(volume.GetMasterVolumeLevelScalar() * 100)
                return {"ok": True, "volume": level}
            except:
                # ALTERNATIVE: Direct comtypes approach
                try:
                    from comtypes import CLSCTX_ALL, CoCreateInstance
                    from ctypes import cast, POINTER
                    
                    devices = AudioUtilities.GetSpeakers()
                    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    volume = cast(interface, POINTER(IAudioEndpointVolume))
                    current_volume = volume.GetMasterVolumeLevelScalar()
                    level = int(current_volume * 100)
                    return {"ok": True, "volume": level}
                except Exception as inner_e:
                    return {"ok": False, "error": f"pycaw API error: {str(inner_e)}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _set_volume(self, level):
        if not PYCAW_AVAILABLE:
            return {"ok": False, "error": "pycaw not available"}
        
        try:
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from ctypes import cast, POINTER
            
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(level / 100, None)
            return {"ok": True, "message": f"Volume set to {level}%"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _play_media(self, args):
        """🔒 SECURE: Validate file extension before playing"""
        path = args.get("path", "")
        
        if not path:
            return {"ok": False, "error": "No path provided"}
        
        if not os.path.exists(path):
            return {"ok": False, "error": f"File not found: {path}"}
        
        # 🔒 SECURITY: Validate file extension
        _, ext = os.path.splitext(path.lower())
        if ext not in SAFE_MEDIA_EXTENSIONS:
            return {"ok": False, "error": f"⚠️ File type not allowed: {ext}\nAllowed: {', '.join(SAFE_MEDIA_EXTENSIONS)}"}
        
        try:
            os.startfile(path)
            return {"ok": True, "message": f"Playing: {path}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _execute_cli(self, args):
        """🔒 SECURE: Execute with blacklist check and shell=False"""
        command = args.get("command", "")
        
        if not command:
            return {"ok": False, "error": "No command provided"}
        
        access_level = self.get_config("cli_access_level", "restricted")
        
        # 🔒 SECURITY: Check blacklist in Restricted mode
        if access_level == "restricted":
            blacklist = self.get_config("cli_blacklist", DEFAULT_BLACKLIST)
            
            # Extract base command (first word)
            cmd_base = command.split()[0].lower() if command.split() else ""
            
            # Check if command is blacklisted
            if cmd_base in blacklist:
                return {
                    "ok": False,
                    "error": f"⚠️ Command '{cmd_base}' is BLACKLISTED in Restricted mode.\nSwitch to Full Access to execute, or remove from blacklist."
                }
        
        # Full Access mode: IGNORE blacklist, execute everything
        
        try:
            # 🔒 SECURITY: Use shell=False and pass command as list
            # Parse command into list for shell=False
            import shlex
            try:
                cmd_list = shlex.split(command)
            except:
                # If parsing fails, use simple split
                cmd_list = command.split()
            
            result = subprocess.run(
                cmd_list,
                shell=False,  # 🔒 SECURITY: Never use shell=True
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "ok": True,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Command timeout (30s)"}
        except FileNotFoundError:
            return {"ok": False, "error": f"Command not found: {cmd_list[0] if cmd_list else command}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    
    def _list_processes(self, args):
        """List running processes sorted by RAM or CPU usage"""
        try:
            sort_by = args.get("sort_by", "ram")
            limit = args.get("limit", 10)
            
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent']):
                try:
                    pinfo = proc.info
                    processes.append({
                        "pid": pinfo['pid'],
                        "name": pinfo['name'],
                        "ram_percent": round(pinfo['memory_percent'], 2),
                        "cpu_percent": round(pinfo['cpu_percent'], 2)
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            # Sort processes
            if sort_by == "ram":
                processes.sort(key=lambda x: x['ram_percent'], reverse=True)
            else:  # cpu
                processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
            
            # Limit results
            top_processes = processes[:limit]
            
            return {
                "ok": True,
                "sort_by": sort_by,
                "count": len(top_processes),
                "processes": top_processes
            }
            
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _health_check(self):
        try:
            health = {
                "ok": True,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "checks": {}
            }
            
            cpu_percent = psutil.cpu_percent(interval=1)
            health["checks"]["cpu"] = {
                "status": "OK" if cpu_percent < 80 else "WARNING",
                "usage_percent": cpu_percent
            }
            
            ram = psutil.virtual_memory()
            health["checks"]["ram"] = {
                "status": "OK" if ram.percent < 85 else "WARNING",
                "usage_percent": ram.percent,
                "available_gb": round(ram.available / (1024 ** 3), 2)
            }
            
            disk_ok = True
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    if usage.percent > 90:
                        disk_ok = False
                except:
                    pass
            
            health["checks"]["disk"] = {"status": "OK" if disk_ok else "WARNING"}
            
            return health
            
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ============ APP / FOLDER / MEDIA LAUNCHER ============

    def _build_app_index(self):
        """
        Scan Start Menu shortcuts ONCE at activation - powers fuzzy open_app lookups.
        This mirrors what Windows itself uses to populate its own Start Menu search,
        so it's always in sync with what's actually installed - no slow recursive
        Program Files scan needed.
        """
        self.app_index = {}
        start_menu_paths = [
            os.path.join(os.environ.get("ProgramData", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
            os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
        ]

        for base_path in start_menu_paths:
            if not os.path.exists(base_path):
                continue
            try:
                for root, dirs, files in os.walk(base_path):
                    for file in files:
                        if file.lower().endswith(".lnk"):
                            app_name = os.path.splitext(file)[0]
                            self.app_index[app_name.lower()] = os.path.join(root, file)
            except Exception as e:
                self.log(f"Error scanning {base_path}: {e}", "warning")

        self.log(f"App index built: {len(self.app_index)} shortcuts found", "info")

    def _open_system_tool(self, tool_name):
        """🔒 SECURE: Fixed command list per enum value, shell=False, no user-controlled string reaches subprocess"""
        if tool_name not in SYSTEM_TOOLS_MAP:
            return {"ok": False, "error": f"Unknown system tool: {tool_name}. Valid options: {', '.join(SYSTEM_TOOLS_MAP.keys())}"}

        try:
            subprocess.Popen(SYSTEM_TOOLS_MAP[tool_name], shell=False)
            return {"ok": True, "message": f"Opening {tool_name}..."}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _open_app(self, args):
        """🔒 SECURE: Fuzzy-match against the pre-built Start Menu index, launch via os.startfile on the .lnk"""
        app_name = args.get("app_name", "").strip()

        if not app_name:
            return {"ok": False, "error": "No app_name provided"}

        if not self.app_index:
            return {"ok": False, "error": "App index is empty - no Start Menu shortcuts were found on this system"}

        matches = difflib.get_close_matches(app_name.lower(), self.app_index.keys(), n=1, cutoff=0.5)

        if not matches:
            return {"ok": False, "error": f"No installed app found matching '{app_name}'"}

        matched_name   = matches[0]
        shortcut_path  = self.app_index[matched_name]

        try:
            os.startfile(shortcut_path)
            return {"ok": True, "message": f"Opening {matched_name}..."}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _open_folder(self, args):
        """Open a standard user folder in Explorer - enum driven, no raw path from the LLM"""
        folder_key = args.get("folder", "").lower()

        if folder_key not in FOLDER_MAP:
            return {"ok": False, "error": f"Unknown folder: {folder_key}. Valid options: {', '.join(FOLDER_MAP.keys())}"}

        folder_path = os.path.join(os.path.expanduser("~"), FOLDER_MAP[folder_key])

        if not os.path.exists(folder_path):
            return {"ok": False, "error": f"Folder not found: {folder_path}"}

        try:
            os.startfile(folder_path)
            return {"ok": True, "message": f"Opened {FOLDER_MAP[folder_key]} folder"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _search_media_in_folder(self, folder, query, extensions):
        """Non-recursive search of a single folder for files matching query + extensions"""
        results = []
        if not os.path.exists(folder):
            return results
        try:
            for filename in os.listdir(folder):
                full_path = os.path.join(folder, filename)
                if not os.path.isfile(full_path):
                    continue
                name_no_ext, ext = os.path.splitext(filename)
                if ext.lower() in extensions and query in name_no_ext.lower():
                    results.append({"filename": filename, "path": full_path})
        except Exception as e:
            self.log(f"Error searching {folder}: {e}", "warning")
        return results

    def _open_media_file(self, args):
        """
        Search for a media file by name across ALL standard user folders
        (Desktop, Documents, Downloads, Music, Pictures, Videos) at once.
        Non-recursive per folder - fast, and avoids triggering OneDrive
        Files On-Demand downloads (a listdir/isfile pass does not force a
        cloud-only file to download; only opening its content would).
        Returns a list of matches - the LLM should then call windows_media_play
        with the chosen path to actually open the file.
        """
        query      = args.get("query", "").strip().lower()
        media_type = args.get("media_type", "")

        if not query:
            return {"ok": False, "error": "No search query provided"}

        if media_type not in MEDIA_TYPE_MAP:
            return {"ok": False, "error": f"Invalid media_type. Must be one of: {', '.join(MEDIA_TYPE_MAP.keys())}"}

        extensions = MEDIA_TYPE_MAP[media_type]

        # === Strip any extension the LLM might have included (e.g. "audacity.png") ===
        # === _search_media_in_folder matches against the filename WITHOUT its  ===
        # === extension, so the query must be normalized the same way to match. ===
        # === Only strips if it's actually a known extension for this media_type ===
        # === avoids mangling legitimate dots in a filename (e.g. "v1.2 photo") ===
        _, query_ext = os.path.splitext(query)
        if query_ext.lower() in extensions:
            query = query[:-len(query_ext)]

        home       = os.path.expanduser("~")

        all_matches = []
        for folder_name in STANDARD_USER_FOLDERS:
            folder_path = os.path.join(home, folder_name)
            for match in self._search_media_in_folder(folder_path, query, extensions):
                match["folder"] = folder_name
                all_matches.append(match)

        if not all_matches:
            searched = ", ".join(STANDARD_USER_FOLDERS)
            return {"ok": False, "error": f"No {media_type} files matching '{query}' found in any of: {searched}"}

        return {
            "ok": True,
            "matches": all_matches,
            "count": len(all_matches),
            "message": f"Found {len(all_matches)} matching file(s). Ask the user which one if there are multiple, then call windows_media_play with the chosen path."
        }

    # ============ FILE DETAILS / TEXT READING ============

    def _is_path_in_standard_folders(self, path):
        """
        🔒 SECURE: Resolves the path (defeats '..' traversal tricks and symlinks)
        and checks it actually lives inside one of the 6 standard user folders.
        Prevents get_file_details / read_text_file from reaching arbitrary
        system paths like .ssh keys, browser profile data, or saved credentials.
        """
        try:
            home          = os.path.expanduser("~")
            resolved_path = os.path.realpath(path)

            for folder_name in STANDARD_USER_FOLDERS:
                folder_path = os.path.realpath(os.path.join(home, folder_name))
                if resolved_path == folder_path or resolved_path.startswith(folder_path + os.sep):
                    return True
            return False
        except Exception:
            return False

    def _resolve_target_path(self, args):
        """
        Resolve either an explicit 'path' or a 'folder' + 'filename' pair into
        a usable path string. The folder+filename form is the SAFE default for
        the LLM: it builds the path via os.path.expanduser("~") internally, so
        the model never has to guess the Windows account folder name (which is
        often NOT the same as the person's first name in conversation, e.g.
        the account folder can be "Nechifor Marian" while the user just goes
        by "Marian" in chat).
        Returns (path, error_message) - error_message is None on success.
        """
        path       = args.get("path", "").strip()
        folder_key = args.get("folder", "").strip().lower()
        filename   = args.get("filename", "").strip()

        if not path and folder_key and filename:
            if folder_key not in FOLDER_MAP:
                return None, f"Unknown folder: {folder_key}. Valid options: {', '.join(FOLDER_MAP.keys())}"
            path = os.path.join(os.path.expanduser("~"), FOLDER_MAP[folder_key], filename)

        if not path:
            return None, "Provide either 'path', or both 'folder' and 'filename'"

        return path, None

    def _human_readable_size(self, size_bytes):
        """Format a byte count as a human-readable string (e.g. '482.3 KB')"""
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}" if unit != 'B' else f"{int(size)} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def _get_file_details(self, args):
        """Read-only metadata for a single file - size, extension, timestamps. No content."""
        path, error = self._resolve_target_path(args)
        if error:
            return {"ok": False, "error": error}

        if not self._is_path_in_standard_folders(path):
            return {"ok": False, "error": f"Path must be inside one of: {', '.join(STANDARD_USER_FOLDERS)}"}

        if not os.path.exists(path) or not os.path.isfile(path):
            return {"ok": False, "error": f"File not found: {path}"}

        try:
            stat = os.stat(path)
            _, ext = os.path.splitext(path)

            return {
                "ok": True,
                "path": path,
                "filename": os.path.basename(path),
                "extension": ext,
                "size_bytes": stat.st_size,
                "size_human": self._human_readable_size(stat.st_size),
                "created":  datetime.datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _read_text_file(self, args):
        """
        Read the text content of a small file (.txt/.md/.csv/.json/.log/.py).
        Scoped to the 6 standard user folders, capped at MAX_TEXT_FILE_SIZE.
        Note: this is the one tool in the plugin that actually opens file
        content - on a OneDrive-synced folder with Files On-Demand, this can
        trigger a cloud download for a placeholder file (search/details do not).
        """
        path, error = self._resolve_target_path(args)
        if error:
            return {"ok": False, "error": error}

        if not self._is_path_in_standard_folders(path):
            return {"ok": False, "error": f"Path must be inside one of: {', '.join(STANDARD_USER_FOLDERS)}"}

        if not os.path.exists(path) or not os.path.isfile(path):
            return {"ok": False, "error": f"File not found: {path}"}

        _, ext = os.path.splitext(path)
        if ext.lower() not in TEXT_FILE_EXTENSIONS:
            return {"ok": False, "error": f"Unsupported file type '{ext}'. Supported: {', '.join(TEXT_FILE_EXTENSIONS)}"}

        try:
            size_bytes = os.path.getsize(path)
            if size_bytes > MAX_TEXT_FILE_SIZE:
                return {
                    "ok": False,
                    "error": f"File too large ({self._human_readable_size(size_bytes)}). "
                             f"Max supported: {self._human_readable_size(MAX_TEXT_FILE_SIZE)}"
                }

            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            return {
                "ok": True,
                "path": path,
                "filename": os.path.basename(path),
                "size_bytes": size_bytes,
                "content": content
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
