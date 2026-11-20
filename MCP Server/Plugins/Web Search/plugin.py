"""
Web Search Plugin
Web search via Tavily, page fetch, YouTube search (through Tavily) and browser URL opening.
No Google account or OAuth needed - only a Tavily API key, entered in the plugin GUI.
"""

import os
import json
import webbrowser
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# === Tunable constants (calibrate empirically) ===
TAVILY_SEARCH_URL    = "https://api.tavily.com/search"
SEARCH_TIMEOUT_SEC   = 15
TEST_TIMEOUT_SEC     = 8
FETCH_TIMEOUT_SEC    = 10
MAX_RESULTS_DEFAULT  = 5
MAX_RESULTS_CAP      = 5       # === Keeps the prompt small for local models ===
SNIPPET_MAX_CHARS    = 400
YT_SNIPPET_MAX_CHARS = 200
FETCH_MAX_CHARS      = 5000
FETCH_USER_AGENT     = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


class WebSearchPlugin(BasePlugin):
    """Web Search - Tavily search, page fetch, YouTube search, open URL."""

    def __init__(self, plugin_dir, config_manager):
        super().__init__(plugin_dir, config_manager)

        # === Runtime state ===
        self.api_key = ""

        # === GUI elements ===
        self.status_label = None

    # ============ LIFECYCLE ============

    def activate(self):
        self.log("Activating...")

        self.api_key = (self.get_config("tavily_api_key", "") or "").strip()
        if not self.api_key:
            self.log("Tavily API key not configured - search tools disabled", "warning")

        self.log("Activated", "info")
        return True

    def deactivate(self):
        self.api_key = ""
        return True

    # ============ GUI METHODS ============

    def get_frame_size(self):
        """Standard 380x80 frame"""
        return (380, 80)

    def create_gui_frame(self, parent, x, y):
        """Create Web Search GUI frame (same layout as the Telegram plugin)"""
        from PyQt5.QtWidgets import QGroupBox, QLabel, QLineEdit, QPushButton
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtCore import Qt

        # === Styles ===
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

        # === Frame ===
        frame = QGroupBox("Web Search", parent)
        frame.setGeometry(x, y, 380, 80)
        frame.setStyleSheet(GROUP_STYLE)

        # === Logo (PNG if present, emoji fallback) ===
        logo = QLabel(frame)
        logo.setGeometry(8, 38, 32, 32)

        plugin_graphics = os.path.join(self.plugin_dir, "Graphics", "Web Search.png")
        if os.path.exists(plugin_graphics):
            pixmap = QPixmap(plugin_graphics)
            logo.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo.setText("🌐")
            logo.setStyleSheet("color: #FFFFFF; border: none; font-size: 16pt;")

        # === API key label ===
        key_label = QLabel("= Tavily API Key =", frame)
        key_label.setGeometry(80, 30, 120, 20)
        key_label.setStyleSheet(LABEL_STYLE)

        # === API key entry ===
        key_entry = QLineEdit(frame)
        key_entry.setGeometry(46, 50, 160, 20)
        key_entry.setStyleSheet(ENTRY_STYLE)
        key_entry.setPlaceholderText("    Paste from tavily.com")
        key_entry.setEchoMode(QLineEdit.Password)
        key_entry.setText(self.api_key or (self.get_config("tavily_api_key", "") or ""))
        key_entry.textChanged.connect(self._on_key_changed)

        # === Status ===
        self.status_label = QLabel("", frame)
        self.status_label.setGeometry(263, 30, 100, 20)
        if self.api_key:
            self._set_status("Key Saved", "#00FF00")
        else:
            self._set_status("No Key", "#FF6666")

        # === Test button ===
        test_btn = QPushButton("Test Connection", frame)
        test_btn.setGeometry(212, 50, 160, 20)
        test_btn.setStyleSheet(BUTTON_STYLE)
        test_btn.clicked.connect(self._on_test_clicked)

        return frame

    def _set_status(self, text, color):
        if self.status_label:
            self.status_label.setText(text)
            self.status_label.setStyleSheet(f"color: {color}; border: none; font-weight: bold;")

    def _on_key_changed(self, text):
        """Save the key on every edit (same pattern as the Telegram bot token)"""
        text = (text or "").strip()
        self.api_key = text
        self.set_config("tavily_api_key", text)

        if text:
            self._set_status("Key Saved", "#00FF00")
        else:
            self._set_status("No Key", "#FF6666")

    def _on_test_clicked(self):
        """Run a 1-result search (costs 1 Tavily credit)"""
        if not self.api_key:
            self.log("Please enter the Tavily API key first!", "error")
            self._set_status("No Key", "#FF6666")
            return

        self.log("Testing Tavily connection...", "info")
        data, error = self._tavily_request("test", 1, timeout=TEST_TIMEOUT_SEC)

        if error:
            self.log(f"❌ Tavily test failed: {error}", "error")
            self._set_status("Test Failed", "#FF6666")
        else:
            self.log("✅ Tavily connected successfully!", "info")
            self._set_status("Connected", "#00FF00")

    # ============ MCP TOOLS ============

    def get_tools(self):
        """Return tools - the ones that call Tavily appear only when a key is set"""
        tools = []

        if self.api_key:
            tools.extend([
                {
                    "name": "web_search",
                    "description": "Search the web (Tavily) and return titles, URLs and snippets",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query":       {"type": "string"},
                            "max_results": {"type": "integer", "default": MAX_RESULTS_DEFAULT}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "youtube_search",
                    "description": "Search YouTube videos and return titles and URLs",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query":       {"type": "string"},
                            "max_results": {"type": "integer", "default": MAX_RESULTS_DEFAULT}
                        },
                        "required": ["query"]
                    }
                }
            ])

        tools.extend([
            {
                "name": "web_fetch",
                "description": "Fetch and extract text from a web page URL",
                "inputSchema": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"]
                }
            },
            {
                "name": "open_url",
                "description": "Open an http/https URL in the default web browser",
                "inputSchema": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"]
                }
            }
        ])

        return tools

    def get_prompt_section(self):
        """Return the prompt section - Tavily-based tools documented only when a key is set"""
        prompt = "=== WEB SEARCH ===\n\n"

        if self.api_key:
            prompt += """- web_search: Search the web (arguments: query, max_results)
- youtube_search: Search YouTube videos (arguments: query, max_results)
"""

        prompt += """- web_fetch: Fetch and extract text content from any URL (arguments: url)
- open_url: Open an http/https URL in the user's browser (arguments: url)
"""

        if self.api_key:
            prompt += """
SEARCH EXAMPLES:
User: "Search for Python tutorials"
→ {"id": "call_1", "tool": "web_search", "arguments": {"query": "Python tutorials", "max_results": 5}}

User: "What's on this page: https://example.com"
→ {"id": "call_2", "tool": "web_fetch", "arguments": {"url": "https://example.com"}}

YOUTUBE EXAMPLES:
User: "Find cat videos on YouTube"
→ {"id": "call_1", "tool": "youtube_search", "arguments": {"query": "funny cats", "max_results": 5}}

User: "Play the first video"
→ {"id": "call_2", "tool": "open_url", "arguments": {"url": "https://www.youtube.com/watch?v=abc123"}}
"""
        else:
            prompt += """
NOTE: web_search and youtube_search are unavailable until a Tavily API key is set in the Web Search plugin.

FETCH EXAMPLE:
User: "What's on this page: https://example.com"
→ {"id": "call_1", "tool": "web_fetch", "arguments": {"url": "https://example.com"}}
"""

        return prompt

    def handle_tool_call(self, tool_name, arguments):
        """Route tool calls - every tool returns {"ok": bool, ...} like Windows Tools"""
        try:
            arguments = arguments or {}

            if tool_name == "web_search":
                result = self._web_search(arguments)
            elif tool_name == "youtube_search":
                result = self._youtube_search(arguments)
            elif tool_name == "web_fetch":
                result = self._web_fetch(arguments)
            elif tool_name == "open_url":
                result = self._open_url(arguments)
            else:
                result = {"ok": False, "error": f"Unknown tool: {tool_name}"}

            text = json.dumps(result, indent=2, ensure_ascii=False)
            if result.get("ok"):
                return {"content": [{"type": "text", "text": text}]}
            return {"content": [{"type": "text", "text": text}], "isError": True}

        except Exception as e:
            self.log(f"Error in {tool_name}: {e}", "error")
            return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "isError": True}

    # ============ HELPERS ============

    @staticmethod
    def _is_http_url(url):
        """True only for well-formed http/https URLs (blocks file://, javascript:, etc.)"""
        try:
            parsed = urlparse(url)
        except Exception:
            return False
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)

    @staticmethod
    def _clamp_results(value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = MAX_RESULTS_DEFAULT
        return max(1, min(value, MAX_RESULTS_CAP))

    @staticmethod
    def _truncate(text, limit):
        text = " ".join((text or "").split())
        if len(text) > limit:
            return text[:limit].rstrip() + "..."
        return text

    def _tavily_request(self, query, max_results, include_domains=None, timeout=SEARCH_TIMEOUT_SEC):
        """
        Single Tavily search call (basic depth = 1 credit).
        Returns: (data_dict, None) on success or (None, error_message) on failure.
        """
        if not self.api_key:
            return None, "Tavily API key is not configured. Enter it in the Web Search plugin."

        payload = {
            "query":        query,
            "search_depth": "basic",
            "max_results":  max_results
        }
        if include_domains:
            payload["include_domains"] = include_domains

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json"
        }

        try:
            response = requests.post(TAVILY_SEARCH_URL, json=payload, headers=headers, timeout=timeout)
        except requests.exceptions.Timeout:
            return None, "Tavily request timed out."
        except requests.exceptions.RequestException as e:
            return None, f"Could not reach Tavily: {e}"

        if response.status_code == 401:
            return None, "Tavily rejected the API key (HTTP 401). Check the key in the Web Search plugin."
        if response.status_code in (429, 432, 433):
            return None, f"Tavily rate limit or credit quota reached (HTTP {response.status_code})."
        if response.status_code != 200:
            return None, f"Tavily returned HTTP {response.status_code}."

        try:
            return response.json(), None
        except ValueError:
            return None, "Tavily returned an invalid response."

    # ============ TOOL IMPLEMENTATIONS ============

    def _web_search(self, args):
        query = (args.get("query") or "").strip()
        if not query:
            return {"ok": False, "error": "Missing 'query'."}

        max_results = self._clamp_results(args.get("max_results", MAX_RESULTS_DEFAULT))
        data, error = self._tavily_request(query, max_results)
        if error:
            return {"ok": False, "error": error}

        results = []
        for item in data.get("results", [])[:max_results]:
            results.append({
                "title":   (item.get("title") or "").strip(),
                "url":     item.get("url", ""),
                "snippet": self._truncate(item.get("content", ""), SNIPPET_MAX_CHARS)
            })

        return {"ok": True, "results": results}

    def _youtube_search(self, args):
        """YouTube search through Tavily, restricted to youtube.com and filtered to video pages"""
        query = (args.get("query") or "").strip()
        if not query:
            return {"ok": False, "error": "Missing 'query'."}

        max_results = self._clamp_results(args.get("max_results", MAX_RESULTS_DEFAULT))

        # === Over-fetch: channel/playlist pages get filtered out below (credit cost is per request) ===
        data, error = self._tavily_request(query, min(10, max_results * 2), include_domains=["youtube.com"])
        if error:
            return {"ok": False, "error": error}

        videos = []
        for item in data.get("results", []):
            url = item.get("url", "")
            if "youtube.com/watch" not in url or "v=" not in url:
                continue

            title = (item.get("title") or "").strip()
            if title.endswith(" - YouTube"):
                title = title[:-len(" - YouTube")]

            videos.append({
                "title":       title,
                "url":         url,
                "description": self._truncate(item.get("content", ""), YT_SNIPPET_MAX_CHARS)
            })
            if len(videos) >= max_results:
                break

        if not videos:
            return {"ok": False, "error": "No YouTube videos found for this query."}

        return {"ok": True, "videos": videos}

    def _web_fetch(self, args):
        url = (args.get("url") or "").strip()
        if not self._is_http_url(url):
            return {"ok": False, "error": "Invalid URL - only http/https URLs are allowed."}

        try:
            response = requests.get(url, timeout=FETCH_TIMEOUT_SEC, headers={"User-Agent": FETCH_USER_AGENT})
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "").lower()
            if content_type and not any(t in content_type for t in ("text/", "html", "xml", "json")):
                return {"ok": False, "error": f"Unsupported content type: {content_type}"}

            soup = BeautifulSoup(response.content, "html.parser")
            for tag in soup(["script", "style"]):
                tag.decompose()

            text   = soup.get_text()
            lines  = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text   = "\n".join(chunk for chunk in chunks if chunk)

            truncated = len(text) > FETCH_MAX_CHARS
            if truncated:
                text = text[:FETCH_MAX_CHARS] + "\n\n[Truncated...]"

            return {"ok": True, "url": url, "truncated": truncated, "text": text}

        except requests.exceptions.Timeout:
            return {"ok": False, "error": "Fetch timed out."}
        except Exception as e:
            return {"ok": False, "error": f"Fetch failed: {str(e)}"}

    def _open_url(self, args):
        url = (args.get("url") or "").strip()
        if not self._is_http_url(url):
            return {"ok": False, "error": "Invalid URL - only http/https URLs are allowed."}

        try:
            if not webbrowser.open(url):
                return {"ok": False, "error": "Could not open the default browser."}
            return {"ok": True, "message": "Opening URL in the browser..."}
        except Exception as e:
            return {"ok": False, "error": str(e)}
