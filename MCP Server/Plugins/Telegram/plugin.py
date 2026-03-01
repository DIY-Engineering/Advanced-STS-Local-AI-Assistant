"""
Telegram Bot API Plugin
Pure Python, zero new dependencies (uses 'requests' only)
"""

import os
import requests


class TelegramPlugin(BasePlugin):
    """Telegram Bot API integration - ZERO dependencies!"""
    
    def __init__(self, plugin_dir, config_manager):
        super().__init__(plugin_dir, config_manager)
        
        # Bot configuration
        self.bot_token = None
        self.api_url = None
        
        # GUI elements
        self.telegram_status = None
    
    def activate(self):
        self.log("Activating...")
        
        # Load bot token
        self.bot_token = self.get_config("bot_token", "")
        
        if self.bot_token:
            self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
            
            # Test connection
            if self._test_connection():
                self.log("Bot token valid", "info")
            else:
                self.log("Bot token invalid or connection failed", "warning")
        else:
            self.log("Bot token not configured", "warning")
        
        self.log("Activated", "info")
        return True
    
    def deactivate(self):
        self.bot_token = None
        self.api_url = None
        return True
    
    # ============ GUI METHODS ============
    
    def get_frame_size(self):
        """Standard 380x80 frame"""
        return (380, 80)
    
    def create_gui_frame(self, parent, x, y):
        """Create Telegram GUI frame"""
        from PyQt5.QtWidgets import QGroupBox, QLabel, QLineEdit, QPushButton
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
        
        ENTRY_STYLE = """
            QLineEdit {
                background-color: #121212;
                color: #00FF00;
                border: 1px solid #FFFFFF;
                border-radius: 5px;
                padding: 3px;
            }
        """
        
        BUTTON_STYLE = """
            QPushButton {
                background-color: #787878;
                color: #FFFFFF;
                border-radius: 10px;
                font-weight: bold;
                padding: 1px;
            }
            QPushButton:hover { background-color: #8C8C8C; }
            QPushButton:pressed { background-color: #666666; }
        """
        
        # Frame
        frame = QGroupBox("Telegram", parent)
        frame.setGeometry(x, y, 380, 80)
        frame.setStyleSheet(GROUP_STYLE)
        
        # Logo (Telegram paper plane emoji or icon)
        logo = QLabel(frame)
        logo.setGeometry(8, 38, 32, 32)
        
        # Try to load Telegram logo if exists
        plugin_graphics = os.path.join(self.plugin_dir, "Graphics", "Telegram.png")
        if os.path.exists(plugin_graphics):
            pixmap = QPixmap(plugin_graphics)
            logo.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo.setText("✈️")  # Telegram paper plane emoji
            logo.setStyleSheet("color: #FFFFFF; border: none; font-size: 16pt;")
        
        # Bot Token label
        token_label = QLabel("= Bot Token =", frame)
        token_label.setGeometry(85, 30, 120, 20)
        token_label.setStyleSheet(LABEL_STYLE)
        
        # Bot Token entry
        token_entry = QLineEdit(frame)
        token_entry.setGeometry(46, 50, 160, 20)
        token_entry.setStyleSheet(ENTRY_STYLE)
        token_entry.setPlaceholderText("    Paste from @BotFather")
        token_entry.setEchoMode(QLineEdit.Password)  # Hide token
        token_entry.setText(self.get_config("bot_token", ""))
        token_entry.textChanged.connect(lambda t: self._on_token_changed(t))
                
        # Status value (red "Not Connected" or green "Bot Connected")
        if self.bot_token and self._test_connection():
            status_text = "Bot Connected"
            status_color = "#00FF00"  # Green
        else:
            status_text = "Not Connected"
            status_color = "#FF6666"  # Red
        
        self.telegram_status = QLabel(status_text, frame)
        self.telegram_status.setGeometry(250, 30, 100, 20)
        self.telegram_status.setStyleSheet(f"color: {status_color}; border: none; font-weight: bold;")
        
        # Test Connection button
        test_btn = QPushButton("Test Connection", frame)
        test_btn.setGeometry(212, 50, 160, 20)
        test_btn.setStyleSheet(BUTTON_STYLE)
        test_btn.clicked.connect(self.test_connection_gui)
        
        return frame
    
    def _on_token_changed(self, text):
        """Handle bot token change"""
        self.set_config("bot_token", text)
        self.bot_token = text
        
        if text:
            self.api_url = f"https://api.telegram.org/bot{text}"
        else:
            self.api_url = None
        
        # Update status
        if self.telegram_status:
            self.telegram_status.setText("Not Connected")
            self.telegram_status.setStyleSheet("color: #FF6666; border: none; font-weight: bold;")
    
    def test_connection_gui(self):
        """Test bot token from GUI"""
        if not self.bot_token:
            self.log("Please enter bot token first!", "error")
            if self.telegram_status:
                self.telegram_status.setText("Not Connected")
                self.telegram_status.setStyleSheet("color: #FF6666; border: none; font-weight: bold;")
            return
        
        self.log("Testing Telegram bot connection...", "info")
        
        if self._test_connection():
            self.log("✅ Bot connected successfully!", "info")
            if self.telegram_status:
                self.telegram_status.setText("Bot Connected")
                self.telegram_status.setStyleSheet("color: #00FF00; border: none; font-weight: bold;")
        else:
            self.log("❌ Bot connection failed - check token!", "error")
            if self.telegram_status:
                self.telegram_status.setText("Connection Failed")
                self.telegram_status.setStyleSheet("color: #FF6666; border: none; font-weight: bold;")
    
    # ============ MCP TOOLS ============
    
    def get_tools(self):
        """Return Telegram tools"""
        if not self.bot_token:
            return []
        
        return [
            {
                "name": "telegram_send_message",
                "description": "Send Telegram message to a chat",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "chat_id": {
                            "type": "string",
                            "description": "Chat ID or username (e.g., '123456' or '@username')"
                        },
                        "text": {
                            "type": "string",
                            "description": "Message text to send"
                        }
                    },
                    "required": ["chat_id", "text"]
                }
            },
            {
                "name": "telegram_send_photo",
                "description": "Send photo to a Telegram chat",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "chat_id": {
                            "type": "string",
                            "description": "Chat ID or username"
                        },
                        "photo_path": {
                            "type": "string",
                            "description": "Local file path to photo"
                        },
                        "caption": {
                            "type": "string",
                            "description": "Optional caption for the photo"
                        }
                    },
                    "required": ["chat_id", "photo_path"]
                }
            },
            {
                "name": "telegram_get_updates",
                "description": "Get recent Telegram messages (last 24h)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 10,
                            "description": "Number of updates to retrieve"
                        }
                    }
                }
            },
            {
                "name": "telegram_get_me",
                "description": "Get bot information",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
    
    def get_prompt_section(self):
        """Return detailed prompt section"""
        if not self.bot_token:
            return """=== TELEGRAM ===
Telegram bot not configured. Set bot token in GUI to enable messaging.
Get token from @BotFather on Telegram.
"""
        
        return """=== TELEGRAM BOT ===

- telegram_send_message: Send text message to chat (arguments: chat_id, text)
- telegram_send_photo: Send photo to chat (arguments: chat_id, photo_path, caption)
- telegram_get_updates: Get recent messages (arguments: limit)
- telegram_get_me: Get bot information

TELEGRAM USAGE EXAMPLES:

User: "Send a Telegram to John saying I'll be late"
→ {"id": "call_1", "tool": "telegram_send_message", "arguments": {"chat_id": "123456789", "text": "I'll be late"}}

User: "Check my Telegram messages"
→ {"id": "call_2", "tool": "telegram_get_updates", "arguments": {"limit": 10}}

User: "Send this screenshot to Maria on Telegram"
→ {"id": "call_3", "tool": "telegram_send_photo", "arguments": {"chat_id": "987654321", "photo_path": "C:\\\\screenshot.png", "caption": "Screenshot"}}

User: "What's my bot info?"
→ {"id": "call_4", "tool": "telegram_get_me", "arguments": {}}

IMPORTANT NOTES:
- chat_id can be numeric ID or @username
- To get chat_id: send message to bot, then use telegram_get_updates
- Photo path must be absolute Windows path (e.g., C:\\\\Pictures\\\\photo.jpg)
- Bot must be added to group/channel to send messages there
"""
    
    def handle_tool_call(self, tool_name, arguments):
        """Execute Telegram tool"""
        try:
            if tool_name == "telegram_send_message":
                result = self._send_message(arguments)
            elif tool_name == "telegram_send_photo":
                result = self._send_photo(arguments)
            elif tool_name == "telegram_get_updates":
                result = self._get_updates(arguments)
            elif tool_name == "telegram_get_me":
                result = self._get_me()
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
    
    # ============ TELEGRAM API METHODS ============
    
    def _test_connection(self):
        """Test if bot token is valid"""
        if not self.api_url:
            return False
        
        try:
            response = requests.get(f"{self.api_url}/getMe", timeout=5)
            return response.status_code == 200 and response.json().get("ok", False)
        except:
            return False
    
    def _send_message(self, args):
        """Send text message"""
        try:
            chat_id = args.get("chat_id")
            text = args.get("text")
            
            if not chat_id or not text:
                return {"ok": False, "error": "Missing chat_id or text"}
            
            response = requests.post(f"{self.api_url}/sendMessage", json={
                "chat_id": chat_id,
                "text": text
            }, timeout=10)
            
            data = response.json()
            
            if data.get("ok"):
                self.log(f"Message sent to {chat_id}", "info")
                return {
                    "ok": True,
                    "message": "Message sent successfully",
                    "message_id": data.get("result", {}).get("message_id")
                }
            else:
                error_msg = data.get("description", "Unknown error")
                self.log(f"Send failed: {error_msg}", "error")
                return {"ok": False, "error": error_msg}
        
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _send_photo(self, args):
        """Send photo"""
        try:
            chat_id = args.get("chat_id")
            photo_path = args.get("photo_path")
            caption = args.get("caption", "")
            
            if not chat_id or not photo_path:
                return {"ok": False, "error": "Missing chat_id or photo_path"}
            
            # Check if file exists
            if not os.path.exists(photo_path):
                return {"ok": False, "error": f"File not found: {photo_path}"}
            
            # Send photo
            with open(photo_path, 'rb') as photo_file:
                files = {'photo': photo_file}
                data = {'chat_id': chat_id}
                
                if caption:
                    data['caption'] = caption
                
                response = requests.post(
                    f"{self.api_url}/sendPhoto",
                    files=files,
                    data=data,
                    timeout=30
                )
            
            result = response.json()
            
            if result.get("ok"):
                self.log(f"Photo sent to {chat_id}", "info")
                return {
                    "ok": True,
                    "message": "Photo sent successfully",
                    "message_id": result.get("result", {}).get("message_id")
                }
            else:
                error_msg = result.get("description", "Unknown error")
                self.log(f"Photo send failed: {error_msg}", "error")
                return {"ok": False, "error": error_msg}
        
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _get_updates(self, args):
        """Get recent messages"""
        try:
            limit = args.get("limit", 10)
            
            response = requests.get(f"{self.api_url}/getUpdates", params={
                "limit": limit
            }, timeout=10)
            
            data = response.json()
            
            if data.get("ok"):
                updates = data.get("result", [])
                
                # Format updates
                messages = []
                for update in updates:
                    if "message" in update:
                        msg = update["message"]
                        messages.append({
                            "message_id": msg.get("message_id"),
                            "from": msg.get("from", {}).get("username", "Unknown"),
                            "chat_id": msg.get("chat", {}).get("id"),
                            "text": msg.get("text", ""),
                            "date": msg.get("date")
                        })
                
                self.log(f"Retrieved {len(messages)} updates", "info")
                return {
                    "ok": True,
                    "count": len(messages),
                    "messages": messages
                }
            else:
                error_msg = data.get("description", "Unknown error")
                return {"ok": False, "error": error_msg}
        
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _get_me(self):
        """Get bot information"""
        try:
            response = requests.get(f"{self.api_url}/getMe", timeout=10)
            data = response.json()
            
            if data.get("ok"):
                bot_info = data.get("result", {})
                self.log(f"Bot info: {bot_info.get('username')}", "info")
                return {
                    "ok": True,
                    "bot": {
                        "id": bot_info.get("id"),
                        "username": bot_info.get("username"),
                        "first_name": bot_info.get("first_name"),
                        "can_join_groups": bot_info.get("can_join_groups"),
                        "can_read_all_group_messages": bot_info.get("can_read_all_group_messages")
                    }
                }
            else:
                error_msg = data.get("description", "Unknown error")
                return {"ok": False, "error": error_msg}
        
        except Exception as e:
            return {"ok": False, "error": str(e)}
