"""
Home Assistant Plugin
WITH SELF-CONTAINED GUI - Plugin creates its own frame!
Default HAOS URL: http://192.168.1.100:8123 (editable by user)
"""

import requests

# DEFAULT HAOS CONFIGURATION
DEFAULT_HAOS_URL = "http://192.168.1.100:8123"

# HAOS Domain Templates
HAOS_DOMAIN_TEMPLATES = {
    "light": {
        "actions": ["turn_on", "turn_off", "toggle"],
        "parameters": {
            "turn_on": {
                "brightness": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 255,
                    "description": "Brightness level (0-255)"
                },
                "rgb_color": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0, "maximum": 255},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "RGB color [red, green, blue]"
                }
            }
        }
    },
    "switch": {
        "actions": ["turn_on", "turn_off", "toggle"],
        "parameters": {}
    },
    "climate": {
        "actions": ["set_temperature", "set_hvac_mode"],
        "parameters": {
            "set_temperature": {
                "temperature": {
                    "type": "number",
                    "minimum": 10,
                    "maximum": 35,
                    "description": "Target temperature in Celsius"
                }
            },
            "set_hvac_mode": {
                "hvac_mode": {
                    "type": "string",
                    "enum": ["heat", "cool", "auto", "off"],
                    "description": "HVAC mode"
                }
            }
        }
    },
    "cover": {
        "actions": ["open_cover", "close_cover", "stop_cover"],
        "parameters": {}
    }
}


class HomeAssistantPlugin(BasePlugin):
    """Home Assistant integration with self-contained GUI"""
    
    def __init__(self, plugin_dir, config_manager):
        super().__init__(plugin_dir, config_manager)
        self.entities = []
        self.tools_cache = []
    
    def activate(self):
        self.log("Activating...")
        
        # Set default HAOS URL if not configured
        if not self.get_config("haos_url", ""):
            self.set_config("haos_url", DEFAULT_HAOS_URL)
            self.log(f"Set default HAOS URL: {DEFAULT_HAOS_URL}", "info")
        
        # Discover entities
        self.entities = self._discover_entities()
        
        if self.entities:
            self.log(f"Discovered {len(self.entities)} entities", "info")
        else:
            self.log("No entities discovered - check HAOS config", "warning")
        
        # Generate tools
        self.tools_cache = self._generate_tools()
        
        self.log("Activated", "info")
        return True
    
    def deactivate(self):
        self.entities = []
        self.tools_cache = []
        return True
    
    # ============ GUI METHODS ============
    
    def get_frame_size(self):
        """Standard 380x80 frame"""
        return (380, 80)
    
    def create_gui_frame(self, parent, x, y):
        """Create Home Assistant GUI frame - SELF-CONTAINED!"""
        from PyQt5.QtWidgets import QGroupBox, QLabel, QLineEdit
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
        
        ENTRY_STYLE = """
            QLineEdit {
                background-color: #121212;
                color: #00FF00;
                border: 1px solid #FFFFFF;
                border-radius: 5px;
                padding: 1px;
            }
        """
        
        # Create frame
        frame = QGroupBox("Home Assistant", parent)
        frame.setGeometry(x, y, 380, 80)
        frame.setStyleSheet(GROUP_STYLE)
        
        # Logo
        logo = QLabel(frame)
        logo.setGeometry(8, 38, 32, 32)
        
        # Try to load HAOS logo
        plugin_graphics = os.path.join(self.plugin_dir, "Graphics", "HAOS.png")
        if os.path.exists(plugin_graphics):
            pixmap = QPixmap(plugin_graphics)
            logo.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo.setText("🏠")
            logo.setStyleSheet("color: #FFFFFF; border: none; font-size: 16pt;")
        
        # HAOS URL
        url_label = QLabel("= Server Address =", frame)
        url_label.setGeometry(75, 30, 100, 20)
        url_label.setStyleSheet(LABEL_STYLE)
        
        # Get saved URL or use default
        saved_url = self.get_config("haos_url", "")
        if not saved_url:
            # First time - set default
            saved_url = DEFAULT_HAOS_URL
            self.set_config("haos_url", DEFAULT_HAOS_URL)
        
        url_entry = QLineEdit(frame)
        url_entry.setGeometry(46, 50, 160, 20)
        url_entry.setStyleSheet(ENTRY_STYLE)
        url_entry.setPlaceholderText("homeassistant.local:8123")
        url_entry.setText(saved_url)
        url_entry.textChanged.connect(lambda t: self.set_config("haos_url", t))
        
        # Access Token
        token_label = QLabel("= Token =", frame)
        token_label.setGeometry(260, 30, 80, 20)
        token_label.setStyleSheet(LABEL_STYLE)
        
        token_entry = QLineEdit(frame)
        token_entry.setGeometry(212, 50, 160, 20)
        token_entry.setStyleSheet(ENTRY_STYLE)
        token_entry.setText(self.get_config("haos_token", ""))
        token_entry.setEchoMode(QLineEdit.Password)
        token_entry.textChanged.connect(lambda t: self.set_config("haos_token", t))
        
        return frame
    
    # ============ MCP TOOLS ============
    
    def get_tools(self):
        """Return HAOS tools"""
        return self.tools_cache
    
    def get_prompt_section(self):
        """Return detailed prompt section for Home Assistant"""
        if not self.entities:
            return f"""=== HOME ASSISTANT ===
HAOS not configured or no entities discovered.

Default server: {DEFAULT_HAOS_URL}
Configure access token in GUI to enable smart home control.
"""
        
        prompt = """=== HOME ASSISTANT (SMART HOME) ===
HAOS tools are dynamically generated based on available entities.
Tool naming format: haos_<domain>_<entity_name>_<action>

SUPPORTED DOMAINS:
- light: turn_on, turn_off, toggle (supports: brightness, rgb_color)
- switch: turn_on, turn_off, toggle
- climate: set_temperature, set_hvac_mode
- cover: open_cover, close_cover, stop_cover

"""
        
        # Add examples from actual entities (limit to 5 examples)
        examples = []
        for entity in self.entities[:5]:
            entity_id = entity['entity_id']
            domain, name = entity_id.split('.')
            friendly_name = entity['attributes'].get('friendly_name', name.replace('_', ' ').title())
            
            if domain == 'light':
                examples.append(f'- haos_light_{name}_turn_on: Turn on {friendly_name} (arguments: brightness, rgb_color)')
            elif domain == 'switch':
                examples.append(f'- haos_switch_{name}_toggle: Toggle {friendly_name}')
            elif domain == 'climate':
                examples.append(f'- haos_climate_{name}_set_temperature: Set {friendly_name} temperature (arguments: temperature)')
            elif domain == 'cover':
                examples.append(f'- haos_cover_{name}_open_cover: Open {friendly_name}')
        
        if examples:
            prompt += "EXAMPLE ENTITIES:\n"
            prompt += "\n".join(examples)
            prompt += "\n\n"
        
        prompt += """SMART HOME USAGE EXAMPLES:

User: "Turn on the living room light at 50%"
→ {"id": "call_1", "tool": "haos_light_living_room_turn_on", "arguments": {"brightness": 127}}

User: "Make the bedroom light red"
→ {"id": "call_2", "tool": "haos_light_bedroom_turn_on", "arguments": {"rgb_color": [255, 0, 0]}}

User: "Set bedroom temperature to 22 degrees"
→ {"id": "call_3", "tool": "haos_climate_bedroom_set_temperature", "arguments": {"temperature": 22}}

User: "Turn off all lights"
→ Multiple calls: haos_light_*_turn_off for each light
"""
        
        return prompt
    
    def handle_tool_call(self, tool_name, arguments):
        """Execute HAOS tool"""
        try:
            result = self._execute_haos(tool_name, arguments)
            
            if result.get("ok"):
                return {
                    "content": [{"type": "text", "text": f"Success: {result.get('message', 'Command executed')}"}]
                }
            else:
                return {
                    "content": [{"type": "text", "text": f"Error: {result.get('error', 'Unknown error')}"}],
                    "isError": True
                }
                
        except Exception as e:
            self.log(f"Error in {tool_name}: {e}", "error")
            return {
                "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                "isError": True
            }
    
    # ============ HAOS DISCOVERY ============
    
    def _discover_entities(self):
        """Discover entities from HAOS"""
        haos_url = self.get_config("haos_url", "")
        haos_token = self.get_config("haos_token", "")
        
        if not (haos_url and haos_token):
            self.log("HAOS not configured", "warning")
            return []
        
        try:
            if not haos_url.startswith(("http://", "https://")):
                haos_url = "http://" + haos_url
            
            url = haos_url.rstrip("/") + "/api/states"
            headers = {"Authorization": f"Bearer {haos_token}"}
            
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            entities = response.json()
            
            # Filter controllable
            controllable = []
            for entity in entities:
                domain = entity['entity_id'].split('.')[0]
                if domain in HAOS_DOMAIN_TEMPLATES:
                    controllable.append(entity)
            
            self.log(f"Discovered {len(controllable)} entities", "info")
            return controllable
            
        except Exception as e:
            self.log(f"Discovery failed: {e}", "error")
            return []
    
    def _generate_tools(self):
        """Generate MCP tools from entities"""
        if not self.entities:
            return []
        
        tools = []
        
        for entity in self.entities:
            entity_id = entity['entity_id']
            domain, name = entity_id.split('.')
            friendly_name = entity['attributes'].get('friendly_name', name.replace('_', ' ').title())
            
            template = HAOS_DOMAIN_TEMPLATES.get(domain)
            if not template:
                continue
            
            for action in template['actions']:
                tool_name = f"haos_{domain}_{name}_{action}"
                
                action_text = action.replace('_', ' ').title()
                description = f"{action_text} - {friendly_name}"
                
                params = template['parameters'].get(action, {})
                if params:
                    param_names = ', '.join(params.keys())
                    description += f" (supports: {param_names})"
                
                input_schema = {
                    "type": "object",
                    "properties": params,
                    "required": []
                }
                
                tools.append({
                    "name": tool_name,
                    "description": description,
                    "inputSchema": input_schema
                })
        
        self.log(f"Generated {len(tools)} tools", "info")
        return tools
    
    # ============ HAOS EXECUTION ============
    
    def _execute_haos(self, tool_name, arguments):
        """Execute HAOS command"""
        haos_url = self.get_config("haos_url", "")
        haos_token = self.get_config("haos_token", "")
        
        if not (haos_url and haos_token):
            return {"ok": False, "error": "HAOS not configured"}
        
        try:
            # Parse tool name
            parts = tool_name.split('_')
            
            if len(parts) < 4:
                return {"ok": False, "error": f"Invalid tool name: {tool_name}"}
            
            domain = parts[1]
            action = parts[-1]
            entity_name = '_'.join(parts[2:-1])
            entity_id = f"{domain}.{entity_name}"
            
            # Map action to service
            service = self._map_action_to_service(action)
            
            if not service:
                return {"ok": False, "error": f"Unknown action: {action}"}
            
            # Call service
            return self._call_service(haos_url, haos_token, domain, service, entity_id, arguments)
            
        except Exception as e:
            self.log(f"Execution error: {e}", "error")
            return {"ok": False, "error": str(e)}
    
    def _map_action_to_service(self, action):
        """Map action to HAOS service"""
        action_map = {
            "turn_on": "turn_on",
            "turn_off": "turn_off",
            "toggle": "toggle",
            "open_cover": "open_cover",
            "close_cover": "close_cover",
            "stop_cover": "stop_cover",
            "set_temperature": "set_temperature",
            "set_hvac_mode": "set_hvac_mode"
        }
        return action_map.get(action)
    
    def _call_service(self, haos_url, haos_token, domain, service, entity_id, arguments):
        """Call HAOS service API"""
        try:
            if not haos_url.startswith(("http://", "https://")):
                haos_url = "http://" + haos_url
            
            url = f"{haos_url.rstrip('/')}/api/services/{domain}/{service}"
            
            headers = {
                "Authorization": f"Bearer {haos_token}",
                "Content-Type": "application/json"
            }
            
            payload = {"entity_id": entity_id}
            payload.update(arguments)
            
            self.log(f"Calling {domain}/{service} on {entity_id}", "debug")
            
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            response.raise_for_status()
            
            return {
                "ok": True,
                "message": f"Command sent to {entity_id}",
                "response": response.json()
            }
            
        except Exception as e:
            self.log(f"Service call failed: {e}", "error")
            return {"ok": False, "error": str(e)}