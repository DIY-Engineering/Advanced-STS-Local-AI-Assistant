"""
MCP RPC 2.0 Server 0.1.1 Beta
All core classes merged into a single file.
Plugins raman separate in Plugins/ pentru extensibilitate maxima.

Run: python "MCP RPC 2.0 Server 0.1.1 Beta.py"         (GUI mode)
Run: python "MCP RPC 2.0 Server 0.1.1 Beta.py" --no-gui (CLI mode)
"""

import sys
import json
import os
import http.server
import socketserver
import logging
import requests
import importlib.util
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel,
                             QPushButton, QLineEdit, QGroupBox, QMessageBox,
                             QTextEdit, QGridLayout)
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap


# ====== PATHS ======


BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
PLUGINS_DIR = os.path.join(BASE_DIR, "Plugins")
GRAPHICS_DIR = os.path.join(BASE_DIR, "Graphics")


# ====== STYLES ======


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
        padding: 0 -2px;
        color: #FFFFFF;
        left: 10px;
        top: 8px;
        background-color: #191919;
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
    QPushButton:hover   { background-color: #8C8C8C; }
    QPushButton:pressed { background-color: #666666; }
"""

START_BUTTON_STYLE = """
    QPushButton {
        background-color: #00FF00;
        color: #000000;
        border-radius: 10px;
        font-weight: bold;
        font-size: 9pt;
    }
    QPushButton:hover { background-color: #00CC00; }
"""

STOP_BUTTON_STYLE = """
    QPushButton {
        background-color: #FF0000;
        color: #FFFFFF;
        border-radius: 10px;
        font-weight: bold;
        font-size: 9pt;
    }
    QPushButton:hover { background-color: #CC0000; }
"""

ENTRY_STYLE = """
    QLineEdit {
        background-color: #121212;
        color: #00FF00;
        border: 1px solid #FFFFFF;
        border-radius: 5px;
        padding: 1px;
    }
"""

LABEL_STYLE     = "color: #FFFFFF; border: none;"

TEXT_EDIT_STYLE = """
    QTextEdit {
        background-color: #111111;
        color: #FFFFFF;
        border: 1px solid #FFFFFF;
        border-radius: 5px;
        font-family: 'Courier New';
        font-size: 9pt;
    }
"""

# ====== GLOBAL INSTANCES ======

_config_manager  = None
_plugin_manager  = None
_server_instance = None   # === Reference to active server (graceful shutdown) ===

# ====== CONFIG MANAGER ======

class ConfigManager:
    """Manages configuration for MCP Server and plugins"""

    DEFAULT_CONFIG = {
        "server_host": "127.0.0.1",
        "server_port": 8765,
        "plugins": {}
    }

    def __init__(self, config_file=None):
        if config_file is None:
            config_file = os.path.join(BASE_DIR, "MCP Config.json")
        self.config_file = config_file
        self.config = self.DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self._deep_merge(self.config, json.load(f))
                logging.info("Config loaded")
            else:
                logging.info("No config file found, using defaults")
                self.save()
        except Exception as e:
            logging.error(f"Config load error: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.config_file) or '.', exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logging.error(f"Config save error: {e}")
            return False

    def get(self, key, default=None):
        """Get value — suporta dot notation: 'plugins.windows_tools.enabled'"""
        if '.' in key:
            value = self.config
            for k in key.split('.'):
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return value
        return self.config.get(key, default)

    def set(self, key, value):
        """Set value — suporta dot notation"""
        if '.' in key:
            keys   = key.split('.')
            current = self.config
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]
            current[keys[-1]] = value
        else:
            self.config[key] = value

    def _deep_merge(self, base, update):
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

# ====== BASE PLUGIN ======

class BasePlugin(ABC):
    """
    Abstract base class pentru toate plugin-urile MCP Server.
    Fiecare plugin traieste in Plugins/<NumePlugin>/plugin.py
    si mosteneste aceasta clasa.
    """

    def __init__(self, plugin_dir: str, config_manager: ConfigManager):
        self.plugin_dir     = plugin_dir
        self.config_manager = config_manager
        self.manifest       = self._load_manifest()
        self.enabled        = self.manifest.get("enabled", True)

        self.name         = self.manifest.get("name", "unknown")
        self.version      = self.manifest.get("version", "0.1.1 Beta")
        self.display_name = self.manifest.get("display_name", self.name)
        self.description  = self.manifest.get("description", "")
        self.author       = self.manifest.get("author", "Nechifor Marian")

        logging.info(f"Loaded plugin: {self.display_name} v{self.version}")

    def _load_manifest(self) -> Dict:
        manifest_path = os.path.join(self.plugin_dir, "manifest.json")
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logging.error(f"manifest.json not found in {self.plugin_dir}")
            return {}
        except json.JSONDecodeError as e:
            logging.error(f"Invalid manifest.json: {e}")
            return {}

    # ====== MCP Methods (MANDATORY) ======

    @abstractmethod
    def activate(self) -> bool:
        """Apelat la activarea plugin-ului"""
        pass

    @abstractmethod
    def deactivate(self) -> bool:
        """Apelat la dezactivarea plugin-ului"""
        pass

    @abstractmethod
    def get_tools(self) -> List[Dict]:
        """Returneaza lista de MCP tools"""
        pass

    @abstractmethod
    def handle_tool_call(self, tool_name: str, arguments: Dict) -> Dict:
        """Executa tool-ul primit"""
        pass

    # ====== Prompt section =====

    def get_prompt_section(self) -> str:
        """
        Returneaza sectiunea de prompt pentru acest plugin.
        Override in plugin pentru documentatie detaliata cu exemple.
        """
        if not self.enabled:
            return ""
        tools = self.get_tools()
        if not tools:
            return ""
        section = f"=== {self.display_name.upper()} ===\n\n"
        for tool in tools:
            section += f"- {tool['name']}: {tool.get('description', 'No description')}\n"
            if 'inputSchema' in tool and 'properties' in tool['inputSchema']:
                props = tool['inputSchema']['properties']
                if props:
                    section += f"  (arguments: {', '.join(props.keys())})\n"
        section += "\n"
        return section

    # ====== GUI Methods ======

    def get_frame_size(self) -> Tuple[int, int]:
        """Dimensiunea frame-ului GUI al plugin-ului (default 380x80)"""
        return (380, 80)

    def create_gui_frame(self, parent, x: int, y: int):
        """
        Creeaza frame-ul Qt al plugin-ului (QGroupBox).
        Override in plugin pentru GUI custom.
        Returneaza None daca plugin-ul e headless.
        """
        return None

    # ====== Helpers ======

    def get_config(self, key: str, default: Any = None) -> Any:
        return self.config_manager.get(f"plugins.{self.name}.{key}", default)

    def set_config(self, key: str, value: Any) -> bool:
        self.config_manager.set(f"plugins.{self.name}.{key}", value)
        return self.config_manager.save()

    def log(self, message: str, level: str = "info"):
        msg = f"[{self.display_name}] {message}"
        getattr(logging, level, logging.info)(msg)

# ====== PLUGIN MANAGER ======

class PluginManager:
    """Discover, load si gestioneaza toate plugin-urile"""

    def __init__(self, plugins_dir: str, config_manager: ConfigManager):
        self.plugins_dir    = plugins_dir
        self.config_manager = config_manager
        self.plugins: Dict[str, BasePlugin] = {}
        logging.info("Plugin Manager initialized")

    def discover_plugins(self) -> List[str]:
        if not os.path.exists(self.plugins_dir):
            logging.warning(f"Plugins directory not found: {self.plugins_dir}")
            os.makedirs(self.plugins_dir, exist_ok=True)
            return []
        dirs = [
            item for item in os.listdir(self.plugins_dir)
            if os.path.isdir(os.path.join(self.plugins_dir, item))
            and os.path.exists(os.path.join(self.plugins_dir, item, "manifest.json"))
        ]
        logging.info(f"Discovered {len(dirs)} plugin(s)")
        return dirs

    def load_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        plugin_dir  = os.path.join(self.plugins_dir, plugin_name)
        plugin_file = os.path.join(plugin_dir, "plugin.py")

        if not os.path.exists(plugin_file):
            logging.error(f"plugin.py not found in {plugin_name}")
            return None

        try:
            spec   = importlib.util.spec_from_file_location(f"plugins.{plugin_name}", plugin_file)
            module = importlib.util.module_from_spec(spec)

            # === Injet BasePlugin in plugin module to eliminate the need to import-it ===
            module.BasePlugin = BasePlugin

            sys.modules[f"plugins.{plugin_name}"] = module
            spec.loader.exec_module(module)

            # === Find Class wich inherits BasePlugin ===
            plugin_class = next(
                (getattr(module, n) for n in dir(module)
                 if isinstance(getattr(module, n), type)
                 and issubclass(getattr(module, n), BasePlugin)
                 and getattr(module, n) is not BasePlugin),
                None
            )

            if not plugin_class:
                logging.error(f"No BasePlugin subclass found in {plugin_name}")
                return None

            plugin = plugin_class(plugin_dir, self.config_manager)

            if plugin.enabled:
                if plugin.activate():
                    logging.info(f"Plugin activated: {plugin.display_name}")
                else:
                    logging.warning(f"Plugin activation failed: {plugin.display_name}")

            return plugin

        except Exception as e:
            logging.error(f"Failed to load plugin {plugin_name}: {e}")
            import traceback
            logging.debug(traceback.format_exc())
            return None

    def load_all_plugins(self):
        logging.info("Loading all plugins...")
        for plugin_name in self.discover_plugins():
            plugin = self.load_plugin(plugin_name)
            if plugin:
                self.plugins[plugin.name] = plugin
        enabled = sum(1 for p in self.plugins.values() if p.enabled)
        logging.info(f"Loaded {len(self.plugins)} plugins ({enabled} enabled)")

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        return self.plugins.get(name)

    def get_all_tools(self) -> List[Dict]:
        tools = []
        for plugin in self.plugins.values():
            if plugin.enabled:
                try:
                    tools.extend(plugin.get_tools())
                except Exception as e:
                    logging.error(f"Error getting tools from {plugin.name}: {e}")
        return tools

    def route_tool_call(self, tool_name: str, arguments: Dict) -> Dict:
        for plugin in self.plugins.values():
            if not plugin.enabled:
                continue
            try:
                if tool_name in [t["name"] for t in plugin.get_tools()]:
                    logging.info(f"Routing {tool_name} to {plugin.display_name}")
                    return plugin.handle_tool_call(tool_name, arguments)
            except Exception as e:
                logging.error(f"Error checking plugin {plugin.name}: {e}")
        return {
            "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
            "isError": True
        }

    def get_plugin_list(self) -> List[Dict]:
        return [{
            "name": p.name,
            "display_name": p.display_name,
            "version": p.version,
            "description": p.description,
            "author": p.author,
            "enabled": p.enabled
        } for p in self.plugins.values()]

# ====== MCP JSON-RPC 2.0 HANDLER ======

class MCPHandler(http.server.BaseHTTPRequestHandler):
    """Secure Handler for MCP JSON-RPC 2.0 requests"""

    def log_message(self, format, *args):
        pass   # === Supress BaseHTTPRequestHandler log ===

    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            body    = self.rfile.read(content_length)
            request = json.loads(body.decode('utf-8'))

            logging.debug(f"Request: {request.get('method', 'unknown')}")
            response = self.process_jsonrpc(request)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            origin = self.headers.get('Origin', '')
            if self._is_allowed_origin(origin):
                self.send_header('Access-Control-Allow-Origin', origin)
            else:
                self.send_header('Access-Control-Allow-Origin', 'http://localhost')
            self.send_header('Access-Control-Allow-Credentials', 'true')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON")
        except Exception as e:
            logging.error(f"Request error: {e}")
            self._send_error(500, f"Internal error: {str(e)}")

    def do_OPTIONS(self):
        self.send_response(200)
        origin = self.headers.get('Origin', '')
        self.send_header('Access-Control-Allow-Origin',
                         origin if self._is_allowed_origin(origin) else 'http://localhost')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    def _is_allowed_origin(self, origin: str) -> bool:
        mode = _config_manager.get("network_mode", "localhost") if _config_manager else "localhost"
        if mode == "lan":
            return True
        return (origin.startswith('http://localhost') or
                origin.startswith('http://127.0.0.1'))

    def _send_error(self, status: int, message: str):
        resp = {"jsonrpc": "2.0", "error": {"code": -32603, "message": message}, "id": None}
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode('utf-8'))

    def process_jsonrpc(self, request: Dict) -> Dict:
        method     = request.get("method")
        params     = request.get("params", {})
        request_id = request.get("id")

        if request.get("jsonrpc") != "2.0":
            return {"jsonrpc": "2.0",
                    "error": {"code": -32600, "message": "Invalid Request: bad jsonrpc version"},
                    "id": request_id}

        dispatch = {
            "initialize":      lambda: self._handle_initialize(params),
            "prompts/list":    lambda: self._handle_prompts_list(),
            "prompts/get":     lambda: self._handle_prompts_get(params),
            "tools/list":      lambda: self._handle_tools_list(),
            "tools/call":      lambda: self._handle_tools_call(params),
            "server/status":   lambda: self._handle_server_status(),
            "server/shutdown": lambda: self._handle_server_shutdown(),
        }

        if method not in dispatch:
            return {"jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                    "id": request_id}

        result = dispatch[method]()
        return {"jsonrpc": "2.0", "result": result, "id": request_id}

    # === Handlers ===

    def _handle_initialize(self, params):
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "prompts": {"listChanged": False},
                "tools":   {"listChanged": False}
            },
            "serverInfo": {"name": "MCP Server (Plugin-Based)", "version": "0.1.1 Beta"}
        }

    def _handle_prompts_list(self):
        return {"prompts": [{"name": "assistant_system_prompt",
                              "description": "System prompt",
                              "arguments": []}]}

    def _handle_prompts_get(self, params):
        if params.get("name") != "assistant_system_prompt":
            raise ValueError(f"Unknown prompt: {params.get('name')}")

        parts = ["AVAILABLE TOOLS:\n"]

        if _plugin_manager:
            for plugin in _plugin_manager.plugins.values():
                if plugin.enabled:
                    section = plugin.get_prompt_section()
                    if section:
                        parts.append(section)

        parts.append("\nTOOL CALL FORMAT: {\"id\": \"unique_id\", \"tool\": \"tool_name\", \"arguments\": {...}}")

        return {
            "description": "System prompt with all available tools",
            "messages": [{"role": "user",
                          "content": {"type": "text", "text": "\n".join(parts)}}]
        }

    def _handle_tools_list(self):
        tools = _plugin_manager.get_all_tools() if _plugin_manager else []
        logging.info(f"Listing {len(tools)} tools")
        return {"tools": tools}

    def _handle_tools_call(self, params):
        if not _plugin_manager:
            return {"content": [{"type": "text", "text": "Plugin manager not initialized"}],
                    "isError": True}
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        logging.info(f"Tool call: {tool_name}")
        return _plugin_manager.route_tool_call(tool_name, arguments)

    def _handle_server_status(self):
        plugins = list(_plugin_manager.plugins.values()) if _plugin_manager else []
        enabled = [p.display_name for p in plugins if p.enabled]
        return {
            "status": "running",
            "version": "0.1.1 Beta",
            "plugins_total": len(plugins),
            "plugins_enabled": len(enabled),
            "enabled_plugins": enabled
        }

    def _handle_server_shutdown(self):
        """Raspunde clientului, apoi opreste procesul dupa 0.3s"""
        import threading, time

        logging.info("Graceful shutdown requested")

        def _do_shutdown():
            time.sleep(0.3)
            if _server_instance:
                _server_instance.shutdown()
                _server_instance.server_close()
            os._exit(0)

        threading.Thread(target=_do_shutdown, daemon=True).start()
        return {"message": "Server shutting down gracefully", "ok": True}

# ====== THREADED TCP SERVER ======

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads      = True

# ====== SERVER THREAD (GUI mode) ======

class ServerThread(QThread):
    log_signal = pyqtSignal(str)

    def __init__(self, host: str, port: int):
        super().__init__()
        self.host    = host
        self.port    = port
        self.server  = None
        self.running = False

    def run(self):
        global _server_instance
        try:
            self.server      = ThreadedTCPServer((self.host, self.port), MCPHandler)
            _server_instance = self.server
            self.running     = True
            self.log_signal.emit(f"Server started on {self.host}:{self.port}")
            self.log_signal.emit("Network: Localhost only (configurable in settings)")
            self.server.serve_forever()
        except Exception as e:
            self.log_signal.emit(f"Server error: {e}")
            self.running = False

    def stop(self):
        self.running = False
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        self.log_signal.emit("Server stopped")

# ====== MAIN GUI ======

class MCPServerGUI(QMainWindow):

    def __init__(self):
        super().__init__()

        global _config_manager, _plugin_manager

        _config_manager = ConfigManager()
        _plugin_manager = PluginManager(PLUGINS_DIR, _config_manager)

        self.config_manager    = _config_manager
        self.plugin_manager    = _plugin_manager
        self.server_thread     = None
        self._headless_detected = False

        self.plugin_manager.load_all_plugins()

        self._init_ui()
        self._create_layout()
        self._setup_logging()

        QTimer.singleShot(300, self._check_headless_server)

    # ===== UI Setup ======

    def _init_ui(self):
        self.setWindowTitle("= MCP RPC 2.0 Server 0.1.1 Beta =")
        self.setStyleSheet("QMainWindow { background-color: #191919; }")
        central = QWidget()
        self.setCentralWidget(central)
        self.grid = QGridLayout(central)
        self.grid.setSpacing(6)
        self.grid.setContentsMargins(6, 6, 6, 6)

    def _create_layout(self):
        row, col = 0, 0

        # === MCP Server frame ===
        self.grid.addWidget(self._create_mcp_frame(), row, col)
        col += 1

        # === Plugin frames ===
        for info in self.plugin_manager.get_plugin_list():
            plugin = self.plugin_manager.get_plugin(info['name'])
            if not plugin:
                continue
            frame = plugin.create_gui_frame(self, 0, 0)
            if frame:
                frame.setFixedSize(380, 80)
                self.grid.addWidget(frame, row, col)
                self.log(f"Created GUI for: {plugin.display_name}")
                col += 1
                if col >= 2:
                    col = 0
                    row += 1

        if col > 0:
            row += 1

        # === Log frame (full width) ===
        self.grid.addWidget(self._create_log_frame(), row, 0, 1, 2)

        self.adjustSize()
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width()  - self.width())  // 2,
                  (screen.height() - self.height()) // 2)

    def _create_mcp_frame(self):
        frame = QGroupBox("MCP Server")
        frame.setFixedSize(380, 80)
        frame.setStyleSheet(GROUP_STYLE)

        logo = QLabel(frame)
        logo.setGeometry(8, 38, 32, 32)
        logo_path = os.path.join(GRAPHICS_DIR, "MCP.png")
        if os.path.exists(logo_path):
            logo.setPixmap(QPixmap(logo_path).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo.setText("MCP")
            logo.setStyleSheet(LABEL_STYLE)

        addr_label = QLabel("= Server Address =", frame)
        addr_label.setGeometry(75, 30, 120, 20)
        addr_label.setStyleSheet(LABEL_STYLE)

        self.address_entry = QLineEdit(frame)
        self.address_entry.setGeometry(46, 50, 160, 20)
        self.address_entry.setStyleSheet(ENTRY_STYLE)
        host = self.config_manager.get("server_host", "127.0.0.1")
        port = self.config_manager.get("server_port", 8765)
        self.address_entry.setText(f"http://{host}:{port}")

        load_btn = QPushButton("Load Config", frame)
        load_btn.setGeometry(212, 24, 77, 20)
        load_btn.setStyleSheet(BUTTON_STYLE)
        load_btn.clicked.connect(self._load_config)

        save_btn = QPushButton("Save Config", frame)
        save_btn.setGeometry(294, 24, 77, 20)
        save_btn.setStyleSheet(BUTTON_STYLE)
        save_btn.clicked.connect(self._save_config)

        self.start_stop_btn = QPushButton("Start Server", frame)
        self.start_stop_btn.setGeometry(212, 50, 160, 20)
        self.start_stop_btn.setStyleSheet(START_BUTTON_STYLE)
        self.start_stop_btn.clicked.connect(self._toggle_server)

        return frame

    def _create_log_frame(self):
        frame = QGroupBox("Debug Tools")
        frame.setFixedSize(766, 300)
        frame.setStyleSheet(GROUP_STYLE)

        logo = QLabel(frame)
        logo.setGeometry(8, 30, 32, 32)
        tools_path = os.path.join(GRAPHICS_DIR, "Tools.png")
        if os.path.exists(tools_path):
            logo.setPixmap(QPixmap(tools_path).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        lbl = QLabel("= Field Used For Testing JSON Commands =", frame)
        lbl.setGeometry(220, 24, 300, 20)
        lbl.setStyleSheet(LABEL_STYLE)

        for text, x, y, slot in [
            ("Discover", 598, 24, self._debug_discover),
            ("Commands", 681, 24, self._debug_commands),
            ("Health",   681, 50, self._debug_health),
            ("Invoke",   598, 50, self._debug_invoke),
        ]:
            btn = QPushButton(text, frame)
            btn.setGeometry(x, y, 77, 20)
            btn.setStyleSheet(BUTTON_STYLE)
            btn.clicked.connect(slot)

        self.quick_entry = QLineEdit(frame)
        self.quick_entry.setGeometry(48, 50, 544, 19)
        self.quick_entry.setStyleSheet(ENTRY_STYLE)

        self.log_text = QTextEdit(frame)
        self.log_text.setGeometry(8, 77, 750, 214)
        self.log_text.setStyleSheet(TEXT_EDIT_STYLE)
        self.log_text.setReadOnly(True)

        return frame

    def _setup_logging(self):
        log_widget = self.log_text

        class _GuiHandler(logging.Handler):
            def emit(self, record):
                msg = self.format(record)
                log_widget.append(msg)
                log_widget.verticalScrollBar().setValue(
                    log_widget.verticalScrollBar().maximum())

        handler = _GuiHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S'))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

    # ====== Server Actions ======

    def _check_headless_server(self):
        """La pornire verifica daca serverul headless ruleaza deja pe port"""
        import socket
        host = self.config_manager.get("server_host", "127.0.0.1")
        port = self.config_manager.get("server_port", 8765)
        try:
            with socket.create_connection((host, port), timeout=1):
                self.log(f"Detected headless server on {host}:{port}")
                self.start_stop_btn.setText("Stop Server")
                self.start_stop_btn.setStyleSheet(STOP_BUTTON_STYLE)
                self._headless_detected = True
        except (ConnectionRefusedError, OSError):
            self._headless_detected = False

    def _toggle_server(self):
        if self._headless_detected:
            self._stop_headless_server()
        elif self.server_thread is None or not self.server_thread.isRunning():
            self._start_server()
        else:
            self._stop_server()

    def _start_server(self):
        try:
            address = self.address_entry.text().strip()
            if "://" in address:
                address = address.split("://")[1]
            host, port = (address.split(":") + ["8765"])[:2]
            port = int(port)

            self.config_manager.set("server_host", host)
            self.config_manager.set("server_port", port)
            self.config_manager.save()

            self.server_thread = ServerThread(host, port)
            self.server_thread.log_signal.connect(self.log)
            self.server_thread.start()

            self.start_stop_btn.setText("Stop Server")
            self.start_stop_btn.setStyleSheet(STOP_BUTTON_STYLE)
            self.log(f"Server started on {host}:{port}")

        except Exception as e:
            self.log(f"Start error: {e}")
            QMessageBox.critical(self, "Error", str(e))

    def _stop_server(self):
        if self.server_thread:
            self.server_thread.stop()
            self.server_thread.wait()
        self.start_stop_btn.setText("Start Server")
        self.start_stop_btn.setStyleSheet(START_BUTTON_STYLE)
        self.log("Server stopped")

    def _stop_headless_server(self):
        host = self.config_manager.get("server_host", "127.0.0.1")
        port = self.config_manager.get("server_port", 8765)
        try:
            payload  = {"jsonrpc": "2.0", "id": 9999, "method": "server/shutdown", "params": {}}
            response = requests.post(f"http://{host}:{port}", json=payload, timeout=3)
            if response.status_code == 200:
                self.log("Headless server stopped via graceful shutdown")
        except Exception as e:
            self.log(f"Could not stop headless server: {e}")
        finally:
            self._headless_detected = False
            self.start_stop_btn.setText("Start Server")
            self.start_stop_btn.setStyleSheet(START_BUTTON_STYLE)

    def _load_config(self):
        self.config_manager.load()
        self.log("Config loaded")
        QMessageBox.information(self, "Config", "Configuration loaded!")

    def _save_config(self):
        self.config_manager.save()
        self.log("Config saved")
        QMessageBox.information(self, "Config", "Configuration saved!")

    def log(self, message: str):
        if hasattr(self, 'log_text'):
            self.log_text.append(message)
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum())
        else:
            print(message)

    # ====== Debug Methods ======

    def _rpc_call(self, method: str, params: Dict = None) -> Optional[str]:
        host = self.config_manager.get("server_host", "127.0.0.1")
        port = self.config_manager.get("server_port", 8765)
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
        try:
            r = requests.post(f"http://{host}:{port}", json=payload, timeout=5)
            return r.text
        except Exception as e:
            return f"Error: {e}"

    def _debug_discover(self):
        self.log(f"Discover:\n{self._rpc_call('prompts/get', {'name': 'assistant_system_prompt'})}\n")

    def _debug_commands(self):
        self.log(f"Commands:\n{self._rpc_call('tools/list')}\n")

    def _debug_health(self):
        self.log("Running health check...")
        running = self.server_thread and self.server_thread.isRunning()
        self.log(f"{'OK' if running else 'STOPPED'} - MCP Server")
        if self.plugin_manager:
            enabled = [p for p in self.plugin_manager.plugins.values() if p.enabled]
            self.log(f"OK - Plugins: {len(enabled)}/{len(self.plugin_manager.plugins)} enabled")
            for p in enabled:
                self.log(f"  + {p.display_name} v{p.version}")
        host = self.config_manager.get("server_host")
        port = self.config_manager.get("server_port")
        self.log(f"OK - Address: {host}:{port}\n")

    def _debug_invoke(self):
        txt = self.quick_entry.text().strip()
        if not txt:
            self.log("Enter JSON command first\n")
            return
        try:
            host = self.config_manager.get("server_host", "127.0.0.1")
            port = self.config_manager.get("server_port", 8765)
            r = requests.post(f"http://{host}:{port}", json=json.loads(txt), timeout=10)
            self.log(f"Invoke {r.status_code}:\n{r.text}\n")
        except json.JSONDecodeError:
            self.log("Invalid JSON format\n")
        except Exception as e:
            self.log(f"Invoke failed: {e}\n")

# ====== CLI MODE ======

def run_cli_mode():
    global _config_manager, _plugin_manager, _server_instance

    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    print("=" * 70)
    print("MCP Server v1.4 - CLI Mode")
    print("=" * 70)

    _config_manager = ConfigManager()
    _plugin_manager = PluginManager(PLUGINS_DIR, _config_manager)

    logging.info("Loading plugins...")
    _plugin_manager.load_all_plugins()

    host = _config_manager.get("server_host", "127.0.0.1")
    port = _config_manager.get("server_port", 8765)

    logging.info(f"Starting server on {host}:{port}...")

    try:
        server           = ThreadedTCPServer((host, port), MCPHandler)
        _server_instance = server
        logging.info(f"Server running on {host}:{port}")
        logging.info("Network: Localhost only (configurable)")
        logging.info("Press Ctrl+C to stop")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
        server.server_close()
        print("Goodbye!")

# ====== ENTRY POINT ======

def main():
    if "--no-gui" in sys.argv or "--cli" in sys.argv:
        run_cli_mode()
    else:
        app = QApplication(sys.argv)
        app.setFont(QFont("Segoe UI", 9))
        gui = MCPServerGUI()
        gui.show()
        sys.exit(app.exec_())

if __name__ == "__main__":
    main()
