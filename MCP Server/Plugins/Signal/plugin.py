"""
Signal Messenger Plugin
Pure Python implementation using Semaphore
Zero new dependencies (uses existing websockets + aiohttp)
"""

import asyncio
import os

try:
    from semaphore import Bot, ChatContext
    SEMAPHORE_AVAILABLE = True
except ImportError:
    SEMAPHORE_AVAILABLE = False


class SignalPlugin(BasePlugin):
    """Signal Messenger integration - Pure Python with Semaphore"""
    
    def __init__(self, plugin_dir, config_manager):
        super().__init__(plugin_dir, config_manager)
        self.phone_number = None
        self.bot = None
        self.message_prefix = "AI Assistant: "
        
        # GUI elements
        self.signal_status = None
    
    def activate(self):
        self.log("Activating...")
        
        if not SEMAPHORE_AVAILABLE:
            self.log("Semaphore not installed - run: pip install semaphore-bot", "warning")
            return False
        
        self.phone_number = self.get_config("phone_number", "")
        
        if not self.phone_number:
            self.log("Phone number not configured", "warning")
        else:
            self.log(f"Configured for {self.phone_number}", "info")
            
            # Check if linked
            if self._check_linked():
                self.log("Device is linked", "info")
            else:
                self.log("Device not linked - use 'Link Device' button", "warning")
        
        self.log("Activated", "info")
        return True
    
    def deactivate(self):
        self.bot = None
        return True
    
    # ============ GUI METHODS ============
    
    def get_frame_size(self):
        """Standard 380x80 frame"""
        return (380, 80)
    
    def create_gui_frame(self, parent, x, y):
        """Create Signal GUI frame"""
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
        frame = QGroupBox("Signal", parent)
        frame.setGeometry(x, y, 380, 80)
        frame.setStyleSheet(GROUP_STYLE)
        
        # Logo (Signal emoji)
        logo = QLabel(frame)
        logo.setGeometry(8, 38, 32, 32)
        
        # Try to load Signal logo if exists
        plugin_graphics = os.path.join(self.plugin_dir, "Graphics", "Signal.png")
        if os.path.exists(plugin_graphics):
            pixmap = QPixmap(plugin_graphics)
            logo.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo.setText("💬")
            logo.setStyleSheet("color: #FFFFFF; border: none; font-size: 16pt;")
        
        # Phone number label
        phone_label = QLabel("= Phone Number =", frame)
        phone_label.setGeometry(75, 30, 120, 20)
        phone_label.setStyleSheet(LABEL_STYLE)
        
        # Phone number entry
        phone_entry = QLineEdit(frame)
        phone_entry.setGeometry(46, 50, 160, 20)
        phone_entry.setStyleSheet(ENTRY_STYLE)
        phone_entry.setText(self.get_config("phone_number", ""))
        phone_entry.setPlaceholderText(" Enter Your Phone Number")
        phone_entry.textChanged.connect(lambda t: self._on_phone_changed(t))
                
        # Status value (red "Not Connected" or green "Device Connected")
        if self.phone_number and self._check_linked():
            status_text = "Device Connected"
            status_color = "#00FF00"  # Green
        else:
            status_text = "  Not Connected"
            status_color = "#FF6666"  # Red
        
        self.signal_status = QLabel(status_text, frame)
        self.signal_status.setGeometry(242, 30, 104, 20)
        self.signal_status.setStyleSheet(f"color: {status_color}; border: none; font-weight: bold;")
        
        # Link button
        link_btn = QPushButton("Link Device", frame)
        link_btn.setGeometry(212, 50, 160, 20)
        link_btn.setStyleSheet(BUTTON_STYLE)
        link_btn.clicked.connect(self.link_device_gui)
        
        return frame
    
    def _on_phone_changed(self, text):
        """Handle phone number change"""
        self.set_config("phone_number", text)
        self.phone_number = text
        
        # Update status (consistent with Google Services)
        if self.signal_status:
            if text and self._check_linked():
                self.signal_status.setText("Device Connected")
                self.signal_status.setStyleSheet("color: #00FF00; border: none; font-weight: bold;")  # Green
            else:
                self.signal_status.setText("Not Connected")
                self.signal_status.setStyleSheet("color: #FF6666; border: none; font-weight: bold;")  # Red
    
    # ============ MCP TOOLS ============
    
    def get_tools(self):
        """Return Signal tools"""
        if not self.phone_number or not self._check_linked():
            return []
        
        return [
            {
                "name": "signal_send",
                "description": "Send Signal message (auto-prefixed with 'AI Assistant:')",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "recipient": {
                            "type": "string",
                            "description": "Phone number with country code (e.g., +40123456789)"
                        },
                        "message": {
                            "type": "string",
                            "description": "Message text (will be prefixed with 'AI Assistant:')"
                        }
                    },
                    "required": ["recipient", "message"]
                }
            },
            {
                "name": "signal_send_group",
                "description": "Send message to Signal group",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "group_id": {
                            "type": "string",
                            "description": "Signal group ID (base64 encoded)"
                        },
                        "message": {
                            "type": "string",
                            "description": "Message text (will be prefixed with 'AI Assistant:')"
                        }
                    },
                    "required": ["group_id", "message"]
                }
            }
        ]
    
    def get_prompt_section(self):
        """Return prompt section"""
        if not self.phone_number or not self._check_linked():
            return """=== SIGNAL MESSENGER ===
Signal not configured or device not linked.
Configure phone number and link device to enable Signal messaging.
"""
        
        return """=== SIGNAL MESSENGER ===

- signal_send: Send Signal message to contact (arguments: recipient, message)
  * Messages auto-prefixed with "AI Assistant:" to avoid confusion
  * Recipient must include country code (e.g., +40123456789)

- signal_send_group: Send message to Signal group (arguments: group_id, message)
  * Group ID is base64 encoded group identifier
  * Messages also prefixed with "AI Assistant:"

SIGNAL USAGE EXAMPLES:

User: "Send a Signal to John saying I'll be late"
→ {"id": "call_1", "tool": "signal_send", "arguments": {"recipient": "+40123456789", "message": "I'll be late"}}

User: "Message the family group that dinner is ready"
→ {"id": "call_2", "tool": "signal_send_group", "arguments": {"group_id": "group_xyz...", "message": "Dinner is ready!"}}

User: "Tell Maria via Signal that the meeting is postponed"
→ {"id": "call_3", "tool": "signal_send", "arguments": {"recipient": "+40987654321", "message": "Meeting postponed to tomorrow"}}

IMPORTANT NOTES:
- All messages are automatically prefixed with "AI Assistant:" 
- Phone numbers must include country code (+XX format)
- User's personal Signal account is used (linked device)
"""
    
    def handle_tool_call(self, tool_name, arguments):
        """Execute Signal tool"""
        try:
            if tool_name == "signal_send":
                return self._run_async(self._send_message(arguments))
            elif tool_name == "signal_send_group":
                return self._run_async(self._send_group_message(arguments))
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
    
    # ============ HELPER METHODS ============
    
    def _run_async(self, coro):
        """Run async coroutine in sync context"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If event loop is running, create new one
                import nest_asyncio
                nest_asyncio.apply()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(coro)
    
    def _check_linked(self):
        """Check if device is linked"""
        if not self.phone_number:
            return False
        
        try:
            # Check if signal data directory exists
            # Semaphore stores data in ~/.local/share/semaphore/
            import pathlib
            data_dir = pathlib.Path.home() / ".local" / "share" / "semaphore" / self.phone_number.replace("+", "")
            return data_dir.exists()
        except:
            return False
    
    # ============ SIGNAL OPERATIONS ============
    
    async def _send_message(self, args):
        """Send Signal message"""
        try:
            recipient = args["recipient"]
            message = self.message_prefix + args["message"]
            
            self.log(f"Sending to {recipient}: {message[:50]}...", "debug")
            
            async with Bot(self.phone_number) as bot:
                await bot.send_message(recipient=recipient, text=message)
            
            self.log(f"Message sent to {recipient}", "info")
            
            return {
                "content": [{
                    "type": "text",
                    "text": f"✅ Signal message sent to {recipient}\nMessage: \"{args['message']}\""
                }]
            }
        
        except Exception as e:
            self.log(f"Send failed: {e}", "error")
            return {
                "content": [{"type": "text", "text": f"❌ Failed to send Signal message: {str(e)}"}],
                "isError": True
            }
    
    async def _send_group_message(self, args):
        """Send Signal group message"""
        try:
            group_id = args["group_id"]
            message = self.message_prefix + args["message"]
            
            self.log(f"Sending to group {group_id[:20]}...: {message[:50]}...", "debug")
            
            async with Bot(self.phone_number) as bot:
                await bot.send_message(recipient=group_id, text=message)
            
            self.log(f"Group message sent", "info")
            
            return {
                "content": [{
                    "type": "text",
                    "text": f"✅ Signal group message sent\nMessage: \"{args['message']}\""
                }]
            }
        
        except Exception as e:
            self.log(f"Group send failed: {e}", "error")
            return {
                "content": [{"type": "text", "text": f"❌ Failed to send group message: {str(e)}"}],
                "isError": True
            }
    
    # ============ DEVICE LINKING ============
    
    def link_device_gui(self):
        """Link Signal device from GUI - shows QR code in console"""
        try:
            if not self.phone_number:
                self.log("Please enter phone number first!", "error")
                if self.signal_status:
                    self.signal_status.setText("Not Connected")
                    self.signal_status.setStyleSheet("color: #FF6666; border: none; font-weight: bold;")
                return
            
            self.log("=" * 50, "info")
            self.log("LINKING SIGNAL DEVICE", "info")
            self.log("=" * 50, "info")
            self.log("", "info")
            self.log("📱 INSTRUCTIONS:", "info")
            self.log("1. Open Signal on your phone", "info")
            self.log("2. Go to Settings → Linked Devices", "info")
            self.log("3. Tap '+' to add new device", "info")
            self.log("4. Scan the QR code that will appear in the CONSOLE window", "info")
            self.log("", "info")
            self.log("⚠️  IMPORTANT: Check the CONSOLE/TERMINAL window for QR code!", "info")
            self.log("=" * 50, "info")
            
            if self.signal_status:
                self.signal_status.setText("Linking...")
                self.signal_status.setStyleSheet("color: #FFAA00; border: none; font-weight: bold;")  # Orange
            
            # Run async link
            self._run_async(self._link_device())
            
            self.log("✅ Device linked successfully!", "info")
            self.log("You can now send Signal messages via AI!", "info")
            
            if self.signal_status:
                self.signal_status.setText("Device Connected")
                self.signal_status.setStyleSheet("color: #00FF00; border: none; font-weight: bold;")  # Green
        
        except Exception as e:
            self.log(f"❌ Link failed: {e}", "error")
            if self.signal_status:
                self.signal_status.setText("Not Connected")
                self.signal_status.setStyleSheet("color: #FF6666; border: none; font-weight: bold;")  # Red
    
    async def _link_device(self):
        """Link device via QR code"""
        print("\n" + "=" * 60)
        print("  SIGNAL DEVICE LINKING")
        print("=" * 60)
        print("\n📱 Scan this QR code with Signal app:\n")
        
        async with Bot(self.phone_number) as bot:
            await bot.link(device_name="AI Assistant")
        
        print("\n✅ Device linked successfully!")
        print("=" * 60 + "\n")