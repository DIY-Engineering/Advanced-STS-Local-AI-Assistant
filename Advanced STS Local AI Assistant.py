import os
import subprocess
import tempfile
import threading
import time
import numpy as np
import pyaudio
import wave
import emoji
import torch
import glob
import gc
import traceback
import requests
import json
from datetime import datetime
import logging
import contextlib
import re
import logging.handlers
from faster_whisper import WhisperModel
from TTS.api import TTS
from TTS.utils.manage import ModelManager
from TTS.tts.configs.xtts_config import XttsConfig  
from TTS.tts.models.xtts import Xtts  
import queue
import sys
import shutil
import psutil
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings 

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QComboBox, 
                             QPushButton, QTextEdit, QSlider, QRadioButton, QLineEdit,
                             QGroupBox, QFileDialog, QMessageBox, QButtonGroup, QDialog)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer, QThread
from PyQt5.QtGui import QFont, QPalette, QColor, QPixmap, QPainter, QBrush, QTextCursor, QPen

# === Fix encoding for console ===
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ====== FOLDER STRUCTURE ======
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def create_folder_structure():
    """
    Creates all required folders at startup if they don't already exist.
    This ensures the project structure is always intact, regardless of
    where the script is run from or if folders were accidentally deleted.
    """
    folders = [
        "Chat History",
        "Coqui TTS",
        os.path.join("Coqui TTS", "Models"),
        os.path.join("Coqui TTS", "Samples"),
        "Debug Logs",
        "Dependencies",
        "Graphics",
        "MCP Server",
        os.path.join("MCP Server", "Graphics"),
        os.path.join("MCP Server", "Plugins"),
        "Profiles",
        "RAG Embedder",
        os.path.join("RAG Embedder", "MiniLM-L6-v2"),
        "RAG Vector Database",
        "Silero VAD",
        os.path.join("Silero VAD", "Models"),
        "System Prompt",
        "Whisper STT",
        os.path.join("Whisper STT", "Models"),
        os.path.join("Whisper STT", "Models", "tiny"),
        os.path.join("Whisper STT", "Models", "base"),
        os.path.join("Whisper STT", "Models", "small"),
        os.path.join("Whisper STT", "Models", "medium"),
        os.path.join("Whisper STT", "Models", "large-v3"),
    ]

    created = 0
    for folder in folders:
        full_path = os.path.join(BASE_DIR, folder)
        if not os.path.exists(full_path):
            os.makedirs(full_path, exist_ok=True)
            created += 1

    return created

# === Create all folders at startup ===
_created = create_folder_structure()

# ====== LOGGING CONFIG ======
MCP_SERVER_DIR  = os.path.join(BASE_DIR, "MCP Server")
MCP_SERVER_FILE = os.path.join(MCP_SERVER_DIR, "MCP Server.py")
LOG_DIR = os.path.join(BASE_DIR, "Debug Logs")

class Utf8StreamHandler(logging.StreamHandler):
    def __init__(self, stream=None):
        super().__init__(stream)
        if stream is None:
            self.stream = sys.stdout

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "Debug Log.txt"), mode='w', encoding="utf-8"),
        Utf8StreamHandler()
    ]
)

# ====== GLOBAL CONFIG ======
PROMPTS_DIR        = os.path.join(BASE_DIR, "System Prompt")
HISTORY_DIR        = os.path.join(BASE_DIR, "Chat History")
CHAT_LOG           = os.path.join(HISTORY_DIR, "Jarvis.txt") # === Jarvis is the Default Profile with hardcoded settings ===
SETTINGS_DIR       = os.path.join(BASE_DIR, "Profiles")
COQUI_MODELS_DIR   = os.path.join(BASE_DIR, "Coqui TTS", "Models")
COQUI_SAMPLES_DIR  = os.path.join(BASE_DIR, "Coqui TTS", "Samples")
WHISPER_MODELS_DIR = os.path.join(BASE_DIR, "Whisper STT", "Models")
GRAPHICS_DIR       = os.path.join(BASE_DIR, "Graphics")
RAG_EMBEDDER_DIR   = os.path.join(BASE_DIR, "RAG Embedder", "MiniLM-L6-v2")
RAG_DATABASE_DIR   = os.path.join(BASE_DIR, "RAG Vector Database")
# === All folders above are created at startup by "create_folder_structure()" ===
CHUNK = 512
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
VAD_THRESHOLD = 0.2
VAD_WINDOW_SIZE = 512
VAD_MIN_SPEECH_DURATION = 1.0
VAD_MIN_SILENCE_DURATION = 1.5

ModelManager.models_dir = COQUI_MODELS_DIR
logging.info(f"Folder structure initialized — {_created} new folder(s) created")
logging.info(f"Coqui TTS models will be stored in: {COQUI_MODELS_DIR}")

# ====== CSS STYLES ======
SCROLLBAR_STYLE = """
    QScrollBar:vertical {
        border: none;
        background: #191919;
        width: 6px;
        margin: 0px 0px 0px 0px;
        border-radius: 3px;
    }
    QScrollBar::handle:vertical {
        background: #555555;
        min-height: 20px;
        border-radius: 5px;
    }
    QScrollBar::handle:vertical:hover {
        background: #787878;
    }
    QScrollBar::add-line:vertical {
        height: 0px;
        subcontrol-position: bottom;
        subcontrol-origin: margin;
    }
    QScrollBar::sub-line:vertical {
        height: 0px;
        subcontrol-position: top;
        subcontrol-origin: margin;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }
"""

class LogEmitter(QObject):
    log_signal = pyqtSignal(str, str)

class VUMeter(QWidget):
    """Vintage Style VU-Meter with 14 LED"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.level = 0
        self.segment_width = 20
        self.segment_height = 10
        self.gap = 2
        self.num_segments = 14
        self.setMinimumSize(self.num_segments * (self.segment_width + self.gap), self.segment_height)
        
    def set_level(self, level):
        """Set VU-Meter Level (0-14)"""
        self.level = min(max(int(level), 0), 14)
        self.update()
    
    def paintEvent(self, event):
        """Draws VU-Meter Segments - Vintage LED Style"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)  # === Antialiass off for a crisper look ===
        
        for i in range(self.num_segments):
            x = i * (self.segment_width + self.gap)
            
            # === Determines color based on level and position ===
            if i < self.level:
                if i < 10:
                    color = QColor("#00FF00")  # Green
                elif i < 12:
                    color = QColor("#FFFF00")  # Yellow
                else:
                    color = QColor("#FF0000")  # Red
            else:
                color = QColor("#0A0A0A")  # Black (off) - Darker
            
            # === Draw the segment with a solid white frame ===
            painter.setPen(QPen(QColor("#FFFFFF"), 1, Qt.SolidLine))  # === Solid 1 pixel white frame ===
            painter.setBrush(QBrush(color, Qt.SolidPattern))  # === Fill solid ===
            painter.drawRect(x, 0, self.segment_width, self.segment_height)

class SystemMonitorWorker(QObject):
    """
    Worker thread for system resource monitoring.
    Runs independently from GUI thread — emits metrics via signal every 0.5s.
    GPU is queried every 4th tick (~2s) to avoid blocking on nvidia-smi.
    """
    metrics_ready = pyqtSignal(float, float, float, float, float, float)
    # args: cpu_percent, sram_percent, sram_total_gb,
    #       gpu_util, vram_percent, vram_total_gb

    def __init__(self):
        super().__init__()
        self._running = False
        self._tick = 0

        # === Cached GPU values — updated every 4th tick ===
        self._gpu_util     = -1.0   # -1 = N/A
        self._vram_percent = -1.0
        self._vram_total   = -1.0

    def start_monitoring(self):
        """Entry point — called by QThread.started signal"""
        self._running = True
        while self._running:
            try:
                # ====== CPU & RAM — every tick (0.5s) ======
                cpu_percent   = psutil.cpu_percent(interval=None)
                ram           = psutil.virtual_memory()
                sram_percent  = ram.percent
                sram_total_gb = ram.total / (1024 ** 3)

                # ====== GPU — every 4th tick (~2s) ======
                self._tick += 1
                if self._tick >= 4:
                    self._tick = 0
                    try:
                        output = subprocess.check_output(
                            ['nvidia-smi',
                             '--query-gpu=utilization.gpu,memory.used,memory.total',
                             '--format=csv,noheader,nounits'],
                            timeout=1
                        ).decode().strip()
                        parts = output.split(',')
                        gpu_util     = float(parts[0].strip())
                        vram_used    = float(parts[1].strip())
                        vram_total   = float(parts[2].strip())
                        vram_percent = (vram_used / vram_total * 100) if vram_total > 0 else 0
                        self._gpu_util     = gpu_util
                        self._vram_percent = vram_percent
                        self._vram_total   = vram_total / 1024  # MB → GB
                    except Exception:
                        pass  # Keep previous cached values

                self.metrics_ready.emit(
                    cpu_percent, sram_percent, sram_total_gb,
                    self._gpu_util, self._vram_percent, self._vram_total
                )

            except Exception as e:
                logging.error(f"SystemMonitorWorker error: {e}")

            time.sleep(0.5)

    def stop(self):
        self._running = False


class ProfileFrame(QWidget):
    """
    Custom widget — displays profile image inside a rounded frame.
    Frame: 64x64px, 2px white border, 10px corner radius.
    Image is drawn centered inside the frame with alpha transparency preserved.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(64, 64)
        self._pixmap = None

    def set_pixmap(self, pixmap):
        """Set the image to display — pass None to clear"""
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # === Draw rounded frame ===
        from PyQt5.QtGui import QPainterPath
        border    = 2
        radius    = 10
        rect      = self.rect().adjusted(border, border, -border, -border)

        # === Frame border ===
        pen = QPen(QColor("#FFFFFF"), border)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)

        # === Draw image clipped to rounded rect ===
        if self._pixmap and not self._pixmap.isNull():
            path = QPainterPath()
            path.addRoundedRect(
                rect.x() + 1, rect.y() + 1,
                rect.width() - 2, rect.height() - 2,
                radius - 1, radius - 1
            )
            painter.setClipPath(path)
            img_rect = rect.adjusted(1, 1, -1, -1)
            scaled = self._pixmap.scaled(
                img_rect.width(), img_rect.height(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )
            # === Center image in frame ===
            x = img_rect.x() + (img_rect.width()  - scaled.width())  // 2
            y = img_rect.y() + (img_rect.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)


class RefreshableComboBox(QComboBox):
    """QComboBox calls refresh function when open"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.refresh_callback = None

    def set_refresh_callback(self, callback):
        self.refresh_callback = callback

    def showPopup(self):
        if self.refresh_callback:
            # === Call refresh function before opening menu ===
            self.refresh_callback()
        super().showPopup()

class TextHandler(logging.Handler):
    def __init__(self, text_widget, emitter):
        super().__init__()
        self.text_widget = text_widget
        self.emitter = emitter

    def emit(self, record):
        try:
            msg = self.format(record)
            self.emitter.log_signal.emit(msg, record.levelname)
        except Exception as e:
            print(f"Error in TextHandler: {str(e)}")

class ProfileManager:
    """
    === ProfileManager — Profile JSON I/O and path management ===
    === Pure file I/O — no GUI widgets, no dialogs ===
    === GUI dialogs (QMessageBox/QFileDialog) and widget reads stay in AIAssistantGUI ===
    """

    RESERVED_PROFILE_NAMES = {"Jarvis"}

    def __init__(self, settings_dir, history_dir, rag_database_dir):
        self.settings_dir     = settings_dir
        self.history_dir      = history_dir
        self.rag_database_dir = rag_database_dir

    # ===================
    # === PROFILE I/O ===
    # ===================

    def save_profile(self, file_path, settings_dict):
        """Write settings dict as JSON to file_path."""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(settings_dict, f, indent=2, ensure_ascii=False)
        logging.info(f"Settings saved to {file_path}")

    def load_profile(self, file_path):
        """Read settings dict from JSON file_path. Returns None on failure."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading profile '{file_path}': {str(e)}")
            return None

    def list_profiles(self):
        """Return list of available profile names (without .json extension)."""
        try:
            if not os.path.exists(self.settings_dir):
                return []
            files = [f for f in os.listdir(self.settings_dir) if f.endswith('.json')]
            return [os.path.splitext(f)[0] for f in files]
        except Exception as e:
            logging.error(f"Error listing profiles: {str(e)}")
            return []

    def is_reserved_name(self, name):
        """Check if a profile name is reserved (e.g. 'Jarvis')."""
        return name in self.RESERVED_PROFILE_NAMES

    def validate_profile_name(self, file_path):
        """Returns True if profile name (from file_path) is NOT reserved."""
        name = os.path.splitext(os.path.basename(file_path))[0]
        return not self.is_reserved_name(name)

    # ====================
    # === PATH HELPERS ===
    # ====================

    def get_chat_log_path(self, profile_name):
        """Return chat log .txt path for a given profile."""
        return os.path.join(self.history_dir, f"{profile_name}.txt")

    def get_rag_dir_path(self, profile_name):
        """Return RAG database directory path for a given profile."""
        return os.path.join(self.rag_database_dir, profile_name)

    def ensure_profile_directories(self, profile_name):
        """Create chat history and RAG directories for a profile if missing."""
        os.makedirs(self.history_dir, exist_ok=True)
        rag_dir = self.get_rag_dir_path(profile_name)
        os.makedirs(rag_dir, exist_ok=True)
        return rag_dir

    def delete_profile(self, profile_name):
        """Delete a profile's JSON file. Returns True on success."""
        if self.is_reserved_name(profile_name):
            logging.warning(f"Cannot delete reserved profile: {profile_name}")
            return False
        try:
            file_path = os.path.join(self.settings_dir, f"{profile_name}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"Profile deleted: {profile_name}")
                return True
            return False
        except Exception as e:
            logging.error(f"Error deleting profile '{profile_name}': {str(e)}")
            return False

    # =========================
    # === CHAT LOG PARSING ===
    # =========================

    def is_timestamp_line(self, line):
        """Check if line begins with a valid timestamp (YYYY-MM-DD HH:MM:SS)."""
        pattern = r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} '
        return bool(re.match(pattern, line))

    def parse_chat_file(self, lines, include_mcp=True):
        """
        Parses a list of chat log lines into a list of message dicts.
        Single source of truth for chat log parsing — pure function, no GUI dependency.

        Args:
            lines:       readlines() output from a chat log file
            include_mcp: if True, includes MCP Request/Response with visible=False
                         if False, includes only User/Assistant (no 'visible' key)
        Returns:
            List of message dicts, sorted chronologically
        """
        valid_roles = ["User", "Assistant", "MCP Request", "MCP Response"] if include_mcp else ["User", "Assistant"]
        messages = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            if self.is_timestamp_line(line):
                try:
                    parts = line.split(" ", 2)
                    if len(parts) >= 3:
                        timestamp = f"{parts[0]} {parts[1]}"
                        rest = parts[2]

                        if ": " in rest:
                            role, text = rest.split(": ", 1)

                            if role in valid_roles:
                                full_text = text
                                i += 1

                                # === Accumulate continuation lines ===
                                while i < len(lines):
                                    next_line = lines[i]
                                    if next_line.strip() and self.is_timestamp_line(next_line.strip()):
                                        break
                                    full_text += "\n" + next_line.rstrip()
                                    i += 1

                                full_text = full_text.strip()

                                entry = {"timestamp": timestamp, "role": role, "text": full_text}
                                if include_mcp:
                                    entry["visible"] = role not in ["MCP Request", "MCP Response"]
                                messages.append(entry)
                                continue

                except Exception as e:
                    logging.warning(f"Skipping malformed line: {line[:50]}... Error: {e}")

            i += 1

        messages.sort(key=lambda x: x.get('timestamp', ''))
        return messages


class RAGManager:
    """
    === RAGManager — ChromaDB + MiniLM-L6-v2 Semantic Memory ===
    === Handles: indexing, semantic search, recent conversation context ===
    === Decoupled from GUI via callbacks and config_getter ===
    """

    def __init__(self, show_warning_signal, get_chat_history, config_getter):
        """
        Args:
            show_warning_signal : pyqtSignal(str, str) — thread-safe warning dialog
            get_chat_history    : callable() -> list — returns current chat_history
            config_getter       : callable() -> dict — rag_memory_enabled, current_rag_dir
        """
        # === Callbacks ===
        self.show_warning    = show_warning_signal
        self.get_chat_history = get_chat_history
        self.get_config      = config_getter

        # === Internal state ===
        self.rag_embedder    = None
        self.rag_client      = None
        self.rag_collection  = None

        # === Threading ===
        self.rag_queue       = queue.Queue()
        self.rag_event       = threading.Event()
        self.rag_thread      = None

    # ==================
    # === PUBLIC API ===
    # ==================

    def start(self):
        """Initialize RAG system and start worker thread."""
        self.init_rag_system()
        self.rag_thread = threading.Thread(target=self.rag_worker, daemon=True)
        self.rag_thread.start()
        logging.info("RAG worker thread started.")

    def stop(self):
        """Graceful shutdown — signal worker thread to exit."""
        self.rag_event.set()
        self.rag_queue.put(None)

    def index_message(self, role, text, timestamp):
        """Queue a message for async indexing into ChromaDB."""
        self.rag_queue.put((role, text, timestamp))

    def switch_profile(self, new_rag_dir):
        """
        Switch RAG database to a different profile directory.
        Closes current client and reinitializes pointing to new path.
        """
        try:
            self.rag_collection = None
            self.rag_client     = None
            gc.collect()

            self.rag_client = chromadb.PersistentClient(
                path=new_rag_dir,
                settings=Settings(anonymized_telemetry=False, allow_reset=True)
            )
            self.rag_collection = self.rag_client.get_or_create_collection(
                name="chat_memory",
                metadata={"hnsw:space": "cosine"}
            )
            self._cleanup_orphaned_rag_folders(new_rag_dir)
            logging.info(f"RAG reinitialized → '{new_rag_dir}' | Docs: {self.rag_collection.count()}")

        except Exception as e:
            logging.error(f"RAG reinit error: {str(e)}")
            self.show_warning.emit("RAG Warning",
                f"RAG could not be reinitialized:\n{str(e)}")

    def document_count(self):
        """Return current number of documents in the RAG collection (0 if unavailable)."""
        try:
            return self.rag_collection.count() if self.rag_collection else 0
        except Exception:
            return 0

    def is_ready(self):
        """Return True if embedder + collection are both initialized."""
        return bool(self.rag_embedder and self.rag_collection is not None)

    def rebuild(self, chat_history=None, include_mcp=False):
        """
        Rebuild RAG database from chat history.
        Args:
            chat_history : list | None — defaults to self.get_chat_history() if not provided
            include_mcp  : bool — if True, also indexes "MCP Request"/"MCP Response" entries
        Returns: int — number of messages queued for indexing
        """
        try:
            if not self.rag_client:
                logging.warning("RAG client not initialized — cannot rebuild.")
                return 0

            allowed_roles = {"User", "Assistant"}
            if include_mcp:
                allowed_roles |= {"MCP Request", "MCP Response"}

            # === Clear existing documents ===
            self.rag_collection = self.rag_client.get_or_create_collection(
                name="chat_memory",
                metadata={"hnsw:space": "cosine"}
            )
            existing = self.rag_collection.get()
            existing_ids = existing.get('ids', [])
            if existing_ids:
                self.rag_collection.delete(ids=existing_ids)
                logging.info(f"Cleared {len(existing_ids)} existing documents")

            history = chat_history if chat_history is not None else self.get_chat_history()
            count = 0
            for entry in history:
                role      = entry.get("role", "")
                text      = entry.get("text", "").strip()
                timestamp = entry.get("timestamp", "")
                if role in allowed_roles and text:
                    self.index_message(role, text, timestamp)
                    count += 1

            logging.info(f"RAG rebuild queued: {count} messages")
            return count

        except Exception as e:
            logging.error(f"RAG rebuild error: {str(e)}")
            return 0

    def release_for_move(self):
        """
        Stop worker + release all ChromaDB file handles (client.reset()).
        Used before moving/deleting the RAG directory on disk (profile rename).
        Caller is responsible for restarting via start_worker() after the move.
        """
        # === Stop RAG worker thread ===
        if self.rag_thread and self.rag_thread.is_alive():
            self.rag_queue.put(None)
            self.rag_thread.join(timeout=2)
            logging.info("RAG worker thread stopped.")

        # === client.reset() — explicitly releases ALL file handles (mmap + SQLite WAL) ===
        # === This is the only reliable way to unlock chroma.sqlite3 and HNSW .bin files on Windows ===
        try:
            if self.rag_client is not None:
                self.rag_client.reset()
                logging.info("ChromaDB reset() called — all file handles released.")
        except Exception as e:
            logging.error(f"Error during ChromaDB reset: {str(e)}")
        finally:
            self.rag_collection = None
            self.rag_client     = None
            gc.collect()
            time.sleep(0.3)
            logging.info("ChromaDB client closed.")

    def start_worker(self):
        """Restart the RAG worker thread (after release_for_move + switch_profile)."""
        self.rag_event.clear()
        self.rag_thread = threading.Thread(target=self.rag_worker, daemon=True)
        self.rag_thread.start()
        logging.info("RAG worker thread restarted.")

    def clear(self):
        """
        Full RAG reset — stops worker, deletes + recreates collection,
        VACUUMs the SQLite file to reclaim disk space, restarts worker.
        Used by 'Clear Chat History' — encapsulates ChromaDB internals
        so GUI never touches rag_client / rag_collection directly.
        """
        cfg = self.get_config()
        current_rag_dir = cfg["current_rag_dir"]

        # === 1. Stop RAG worker thread — it holds a lock on chroma.sqlite3 ===
        try:
            if self.rag_thread and self.rag_thread.is_alive():
                self.rag_queue.put(None)
                self.rag_thread.join(timeout=2)
                logging.info("RAG worker thread stopped.")
        except Exception as e:
            logging.error(f"Error stopping RAG thread: {str(e)}")

        # === 2. Delete + recreate collection + explicit VACUUM ===
        # === ChromaDB holds a SQLite connection pool for the entire process lifetime. ===
        # === shutil.rmtree() will always fail with WinError 32 while the process runs. ===
        # === We delete the collection, recreate it fresh, then run VACUUM directly on ===
        # === chroma.sqlite3 via Python's sqlite3 module to reclaim the physical space. ===
        try:
            if self.rag_client is not None:
                self.rag_client.delete_collection("chat_memory")
                logging.info("RAG collection deleted.")

                self.rag_collection = self.rag_client.create_collection(
                    name="chat_memory",
                    metadata={"hnsw:space": "cosine"}
                )
                self._cleanup_orphaned_rag_folders(current_rag_dir)
                logging.info("Fresh RAG collection created.")

                # === VACUUM directly on chroma.sqlite3 to reclaim disk space ===
                # === SQLite marks deleted pages as free but keeps file size without VACUUM ===
                import sqlite3 as _sqlite3
                sqlite_path = os.path.join(current_rag_dir, "chroma.sqlite3")
                if os.path.exists(sqlite_path):
                    try:
                        conn = _sqlite3.connect(sqlite_path)
                        conn.execute("VACUUM")
                        conn.close()
                        size_kb = os.path.getsize(sqlite_path) / 1024
                        logging.info(f"SQLite VACUUM complete — file size: {size_kb:.1f} KB")
                    except Exception as ve:
                        logging.warning(f"VACUUM failed (non-critical): {str(ve)}")
            else:
                # === Client not available — full reinit as fallback ===
                self.switch_profile(current_rag_dir)
                logging.info("RAG reinitialized (fallback).")
        except Exception as e:
            logging.error(f"Error resetting RAG collection: {str(e)}")
            self.switch_profile(current_rag_dir)

        # === 3. Restart RAG worker thread ===
        try:
            self.rag_event.clear()
            self.rag_thread = threading.Thread(target=self.rag_worker, daemon=True)
            self.rag_thread.start()
            logging.info("RAG worker thread restarted.")
        except Exception as e:
            logging.error(f"Error restarting RAG thread: {str(e)}")

    # =====================
    # === WORKER THREAD ===
    # =====================

    def rag_worker(self):
        """Background thread for async vector indexing."""
        try:
            while not self.rag_event.is_set():
                try:
                    item = self.rag_queue.get(timeout=0.5)
                    if item is None:
                        break

                    role, text, timestamp = item

                    cfg = self.get_config()
                    if not cfg["rag_memory_enabled"] or not self.rag_embedder:
                        continue

                    # === Embedding generation ===
                    embedding = self.rag_embedder.encode(text).tolist()

                    # === Unique ID based on timestamp ===
                    doc_id = f"{role}_{timestamp.replace(' ', '_').replace(':', '-')}"

                    # === Add to ChromaDB ===
                    self.rag_collection.add(
                        embeddings=[embedding],
                        documents=[text],
                        metadatas=[{"role": role, "timestamp": timestamp}],
                        ids=[doc_id]
                    )

                    logging.info(f"RAG: Indexed {role} message (ID: {doc_id})")

                except queue.Empty:
                    continue
                except Exception as e:
                    logging.error(f"RAG Worker Error: {str(e)}")

        except Exception as e:
            logging.error(f"Critical RAG Worker Error: {str(e)}")

    # =============
    # === QUERY ===
    # =============

    def query(self, query_text, top_k=6, recent_lines=None):
        """
        Semantic memory query — returns relevant past messages.
        Args:
            query_text   : current user message
            top_k        : max messages to return
            recent_lines : set of normalized texts already in recent_context (dedup)
        Returns: formatted string with relevant past messages
        """
        try:
            cfg = self.get_config()
            if not cfg["rag_memory_enabled"] or not self.rag_embedder or self.rag_collection.count() == 0:
                return ""

            if recent_lines is None:
                recent_lines = set()

            query_embedding = self.rag_embedder.encode(query_text).tolist()

            results = self.rag_collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k * 3, self.rag_collection.count())
            )

            if not results['documents'] or not results['documents'][0]:
                return ""

            candidates = []
            seen_texts = set()

            for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
                role      = meta.get('role', 'Unknown')
                timestamp = meta.get('timestamp', '')

                if role not in ('User', 'Assistant'):
                    continue

                import re
                doc_clean = re.sub(r"[^\w\s,.!?'-]", '', doc, flags=re.UNICODE)
                doc_clean = ' '.join(doc_clean.split())

                if not doc_clean.strip() or len(doc_clean.strip()) < 5:
                    continue

                if len(doc_clean) > 150:
                    doc_clean = doc_clean[:150] + "..."

                doc_normalized = doc_clean.lower()[:80]
                if doc_normalized in recent_lines:
                    continue

                if doc_clean in seen_texts:
                    continue
                seen_texts.add(doc_clean)

                candidates.append((timestamp, role, doc_clean))

            candidates.sort(key=lambda x: x[0])

            pairs = []
            i = 0
            while i < len(candidates) and len(pairs) < (top_k // 2):
                ts, role, text = candidates[i]
                if role == 'User':
                    if i + 1 < len(candidates) and candidates[i + 1][1] == 'Assistant':
                        pairs.append((text, candidates[i + 1][2]))
                        i += 2
                    else:
                        i += 1
                else:
                    i += 1

            context_parts = []
            for user_text, assistant_text in pairs:
                context_parts.append(f"User: {user_text}")
                context_parts.append(f"Assistant: {assistant_text}")

            context = "\n".join(context_parts)

            max_chars = 2000
            if len(context) > max_chars:
                context = context[:max_chars]
                last_newline = context.rfind('\n')
                if last_newline > 0:
                    context = context[:last_newline]

            logging.info(f"RAG: {len(pairs)} pairs (~{len(context)//4} tokens)")
            return context

        except Exception as e:
            logging.error(f"RAG Query Error: {str(e)}")
            return ""

    def get_recent_conversation(self, max_pairs=3):
        """
        Extract last N User→Assistant pairs from chat history.
        Returns formatted string in chronological order.
        """
        try:
            chat_history = self.get_chat_history()
            if not chat_history:
                return ""

            import re
            pairs = []

            i = len(chat_history) - 1
            while i >= 0 and len(pairs) < max_pairs:
                entry = chat_history[i]
                role  = entry.get('role', '')
                text  = entry.get('text', '').strip()

                if role == 'Assistant' and text and len(text) >= 5:
                    assistant_text = re.sub(r"[^\w\s,.!?\-\'\"\{\}\[\]:/\\]", '', text, flags=re.UNICODE)
                    assistant_text = ' '.join(assistant_text.split())
                    if len(assistant_text) > 150:
                        assistant_text = assistant_text[:150] + "..."

                    j = i - 1
                    while j >= 0:
                        prev = chat_history[j]
                        if prev.get('role') == 'User':
                            user_text = prev.get('text', '').strip()
                            user_text = re.sub(r"[^\w\s,.!?'-]", '', user_text, flags=re.UNICODE)
                            user_text = ' '.join(user_text.split())
                            if len(user_text) > 150:
                                user_text = user_text[:150] + "..."
                            if len(user_text) >= 5:
                                pairs.append((user_text, assistant_text))
                            i = j - 1
                            break
                        j -= 1
                    else:
                        i -= 1
                else:
                    i -= 1

            pairs.reverse()

            context_parts = []
            for user_text, assistant_text in pairs:
                context_parts.append(f"User: {user_text}")
                context_parts.append(f"Assistant: {assistant_text}")

            result = "\n".join(context_parts)
            logging.info(f"Recent: {len(pairs)} pairs (~{len(result)//4} tokens)")
            return result

        except Exception as e:
            logging.error(f"Error getting recent conversation: {str(e)}")
            return ""

    # ================
    # === INTERNAL ===
    # ================

    def init_rag_system(self):
        """Load MiniLM embedder and initialize ChromaDB."""
        try:
            cfg = self.get_config()
            logging.info("Loading RAG Embedder Model (MiniLM-L6-v2)...")
            self.rag_embedder = SentenceTransformer(RAG_EMBEDDER_DIR)
            logging.info("RAG Embedder loaded successfully.")

            self.rag_client = chromadb.PersistentClient(
                path=cfg["current_rag_dir"],
                settings=Settings(anonymized_telemetry=False, allow_reset=True)
            )
            self.rag_collection = self.rag_client.get_or_create_collection(
                name="chat_memory",
                metadata={"hnsw:space": "cosine"}
            )
            self._cleanup_orphaned_rag_folders(cfg["current_rag_dir"])
            logging.info(f"RAG Database initialized. Documents: {self.rag_collection.count()}")

        except Exception as e:
            logging.error(f"RAG Initialization Error: {str(e)}")
            self.show_warning.emit("RAG Warning",
                f"RAG system could not be initialized:\n{str(e)}\n\nContinuing without RAG memory.")

    def _cleanup_orphaned_rag_folders(self, rag_dir):
        """Remove orphaned ChromaDB UUID folders — fixes WinError 32 on Windows."""
        if not self.rag_collection or not os.path.exists(rag_dir):
            return
        try:
            active_uuid = str(self.rag_collection.id)
            for item in os.listdir(rag_dir):
                item_path = os.path.join(rag_dir, item)
                if os.path.isdir(item_path) and item != active_uuid:
                    try:
                        shutil.rmtree(item_path)
                        logging.info(f"Removed orphaned RAG folder: {item}")
                    except Exception as e:
                        logging.warning(f"Could not remove orphaned folder '{item}': {e}")
        except Exception as e:
            logging.warning(f"Orphaned folder cleanup failed: {e}")


class AudioProcessor:
    """
    === AudioProcessor — VAD + PyAudio Input + Faster-Whisper STT ===
    === Handles microphone capture, speech detection and transcription ===
    === Decoupled from GUI via callbacks and config_getter ===
    """

    def __init__(self,
                 vu_input_signal,
                 on_speech_detected,
                 stop_tts_callback,
                 is_tts_active,
                 is_real_talk,
                 show_error_signal,
                 config_getter):
        """
        Args:
            vu_input_signal    : pyqtSignal(int) — VU meter for microphone
            on_speech_detected : callable(frames) — called with audio frames when speech ends
            stop_tts_callback  : callable() — interrupt TTS on barge-in
            is_tts_active      : callable() -> bool — is TTS currently playing?
            is_real_talk       : callable() -> bool — is Real Talk mode enabled?
            show_error_signal  : pyqtSignal(str, str) — thread-safe error dialog
            config_getter      : callable() -> dict — all audio/STT config params
        """
        # === Callbacks & signals ===
        self.vu_input_signal    = vu_input_signal
        self.on_speech_detected = on_speech_detected
        self.stop_tts           = stop_tts_callback
        self.is_tts_active      = is_tts_active
        self.is_real_talk       = is_real_talk
        self.show_error         = show_error_signal
        self.get_config         = config_getter

        # === VAD state ===
        self.vad_model          = None

        # === PyAudio state ===
        self.audio_pyaudio      = None
        self.audio_stream       = None

        # === Whisper state ===
        self.faster_whisper_model    = None
        self.current_whisper_model   = None
        self.current_whisper_device  = None
        self.whisper_compute_type    = None

        # === Threading ===
        self.stop_event         = threading.Event()
        self.recording_paused   = False
        self.resume_event       = threading.Event()

    # ==================
    # === PUBLIC API ===
    # ==================

    def start(self, device_index):
        """Start audio recording on a new thread."""
        self.stop_event.clear()
        self.recording_paused = False
        thread = threading.Thread(
            target=self.record_audio_continuous,
            args=(device_index,),
            daemon=True
        )
        thread.start()
        return thread

    def stop(self):
        """Signal recording to stop."""
        self.stop_event.set()
        self.resume_event.set()  # === Unblock any paused wait ===

    def pause_mic(self):
        """Pause microphone — called after speech detected (Standard Mode)."""
        self.recording_paused = True
        logging.info("Microphone PAUSED.")
        self.vu_input_signal.emit(0)

    def resume_mic(self):
        """Resume microphone — called after TTS completes."""
        self.recording_paused = False
        self.resume_event.set()
        logging.info("Microphone RESUMED.")

    def load_devices(self):
        """Return (mics, outputs) — lists of available audio devices."""
        mics    = []
        outputs = []
        try:
            p = pyaudio.PyAudio()
            logging.info("Loading audio input devices")
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                if dev.get('maxInputChannels', 0) > 0:
                    mics.append(f"{i}: {dev['name']}")
            logging.info(f"Microphones loaded: {mics}")

            logging.info("Loading audio output devices")
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                if dev.get('maxOutputChannels', 0) > 0:
                    outputs.append(f"{i}: {dev['name']}")
            logging.info(f"Output devices loaded: {outputs}")
            p.terminate()
        except Exception as e:
            logging.error(f"Error loading audio devices: {str(e)}")
        return mics, outputs

    def cleanup(self):
        """Release PyAudio stream and instance."""
        with contextlib.suppress(Exception):
            if self.audio_stream and self.audio_stream.is_active():
                self.audio_stream.stop_stream()
                self.audio_stream.close()
        with contextlib.suppress(Exception):
            if self.audio_pyaudio:
                self.audio_pyaudio.terminate()
        self.audio_stream  = None
        self.audio_pyaudio = None

    def release_whisper(self):
        """Unload Whisper model and free VRAM."""
        if self.faster_whisper_model is not None:
            del self.faster_whisper_model
            self.faster_whisper_model   = None
            self.current_whisper_model  = None
            self.current_whisper_device = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logging.info("Whisper model released from memory.")

    # ==================
    # === SILERO VAD ===
    # ==================

    def init_silero_vad(self):
        """Load Silero VAD model from local path."""
        cfg = self.get_config()
        logging.info("Loading Silero VAD model")
        try:
            vad_model_path = os.path.join(BASE_DIR, "Silero VAD", "Models", "silero_vad.jit")
            if not os.path.exists(vad_model_path):
                raise FileNotFoundError(f"Silero VAD model not found at {vad_model_path}")

            self.vad_model = torch.jit.load(vad_model_path, map_location=cfg["vad_device"])
            self.vad_model.eval()
            logging.info(f"Silero VAD loaded on {cfg['vad_device']}")

        except Exception as e:
            logging.error(f"Silero VAD Error: {str(e)}")
            self.show_error.emit("Silero VAD Error",
                f"Could not load VAD model:\n\n{str(e)}\n\n"
                f"Expected location:\n{os.path.join(BASE_DIR, 'Silero VAD', 'Models', 'silero_vad.jit')}"
            )

    # ============================
    # === AUDIO RECORDING LOOP ===
    # ============================

    def record_audio_continuous(self, device_index):
        """Main audio capture loop — runs on dedicated thread."""
        try:
            self.audio_pyaudio = pyaudio.PyAudio()
            self.audio_stream  = self.audio_pyaudio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=CHUNK
            )
            logging.info("Recording started.")

            frames                 = []
            recording_active       = False
            speech_detected_frames = 0
            silence_detected_frames = 0

            cfg = self.get_config()
            min_speech_frames  = int(cfg["vad_min_speech_duration"] * RATE / VAD_WINDOW_SIZE)
            min_silence_frames = int(cfg["vad_min_silence_duration"] * RATE / VAD_WINDOW_SIZE)

            if self.vad_model is None:
                self.init_silero_vad()

            while not self.stop_event.is_set():
                cfg = self.get_config()

                # === PAUSE LOGIC — discard buffer to prevent echo ===
                if self.recording_paused and not self.is_real_talk():
                    time.sleep(0.05)
                    self.vu_input_signal.emit(0)
                    if self.audio_stream:
                        try:
                            to_read = self.audio_stream.get_read_available()
                            if to_read > 0:
                                self.audio_stream.read(to_read, exception_on_overflow=False)
                        except:
                            pass
                    continue

                try:
                    audio_data = np.frombuffer(
                        self.audio_stream.read(CHUNK, exception_on_overflow=False),
                        dtype=np.int16
                    )

                    # === Apply mic volume ===
                    mic_volume_factor = cfg["mic_volume"] / 100.0
                    audio_data  = (audio_data * mic_volume_factor).astype(np.int16)
                    audio_float = audio_data.astype(np.float32) / 32768.0

                    # === VU meter ===
                    rms   = np.sqrt(np.mean(audio_float ** 2))
                    level = min(int(rms * 100), 14)
                    self.vu_input_signal.emit(level)

                    # === VAD analysis ===
                    vad_buffer = audio_float
                    if len(vad_buffer) >= VAD_WINDOW_SIZE:
                        audio_chunk = vad_buffer[:VAD_WINDOW_SIZE]
                        if len(audio_chunk) == VAD_WINDOW_SIZE and self.vad_model:
                            audio_tensor = torch.tensor(
                                audio_chunk, dtype=torch.float32
                            ).unsqueeze(0).to(cfg["vad_device"])
                            with torch.no_grad():
                                speech_prob = self.vad_model(audio_tensor, RATE).item()
                        else:
                            speech_prob = 0.0

                        # === BARGE-IN (Real Talk mode) ===
                        if speech_prob > cfg["vad_threshold"]:
                            if self.is_real_talk() and self.is_tts_active():
                                logging.info("REAL TALK: Barge-in detected! Stopping TTS...")
                                self.stop_tts()
                                time.sleep(0.05)
                                frames                  = []
                                recording_active        = True
                                speech_detected_frames  = 0
                                silence_detected_frames = 0

                        if speech_prob > cfg["vad_threshold"]:
                            if not recording_active:
                                logging.info("Speech started...")
                                recording_active = True
                            frames.append(audio_data.tobytes())
                            speech_detected_frames  += 1
                            silence_detected_frames  = 0
                        else:
                            if recording_active:
                                frames.append(audio_data.tobytes())
                                silence_detected_frames += 1
                                if (silence_detected_frames >= min_silence_frames and
                                        speech_detected_frames >= min_speech_frames):
                                    # === END OF SPEECH ===
                                    logging.info("End of speech detected.")

                                    if not self.is_real_talk():
                                        self.pause_mic()
                                        # === Flush buffer to clear last ms of silence ===
                                        if self.audio_stream:
                                            try:
                                                self.audio_stream.read(
                                                    self.audio_stream.get_read_available(),
                                                    exception_on_overflow=False
                                                )
                                            except: pass

                                    # === Dispatch to processing thread ===
                                    segment_frames = frames.copy()
                                    proc_thread = threading.Thread(
                                        target=self.on_speech_detected,
                                        args=(segment_frames,),
                                        daemon=True
                                    )
                                    proc_thread.start()

                                    frames                  = []
                                    recording_active        = False
                                    speech_detected_frames  = 0
                                    silence_detected_frames = 0
                            else:
                                frames = []

                except Exception as e:
                    logging.error(f"Error reading audio stream: {str(e)}")
                    break

        except Exception as e:
            logging.error(f"Recording error: {str(e)}")
            self.show_error.emit("Recording Error", f"Recording error: {str(e)}")
        finally:
            self.cleanup()
            if self.is_real_talk() and not self.stop_event.is_set():
                logging.info("Real Talk: restarting recording loop...")

    # ===================
    # === WHISPER STT ===
    # ===================

    def transcribe_audio(self, audio_array):
        """Transcribe audio using Faster-Whisper (local models only)."""
        logging.info("Transcribing audio with Faster-Whisper")
        cfg = self.get_config()

        try:
            model_name  = cfg["whisper_model"]
            device      = cfg["whisper_device"]

            model_changed  = (self.current_whisper_model  != model_name)
            device_changed = (self.current_whisper_device != device)

            if self.faster_whisper_model is None or model_changed or device_changed:
                # === Release old model ===
                if self.faster_whisper_model is not None:
                    logging.info(f"Unloading old Whisper model: {self.current_whisper_model}")
                    self.release_whisper()

                # === Find local model path ===
                model_path = self._get_whisper_model_path(model_name)
                if not model_path:
                    error_msg = f"Whisper model '{model_name}' not found in local directory!"
                    logging.error(error_msg)
                    self.show_error.emit("Model Error",
                        f"{error_msg}\n\nExpected:\n{WHISPER_MODELS_DIR}\\{model_name}\\model.bin"
                    )
                    return None

                # === Compute type ===
                compute_type = "int8" if device == "cpu" else "int8"

                logging.info(f"Loading Faster-Whisper: {model_name} from {model_path}")
                logging.info(f"Device: {device} | Compute: {compute_type}")

                try:
                    self.faster_whisper_model = WhisperModel(
                        model_path,
                        device=device,
                        compute_type=compute_type,
                        download_root=None,
                        local_files_only=True
                    )
                    self.current_whisper_model  = model_name
                    self.current_whisper_device = device
                    self.whisper_compute_type   = compute_type
                    logging.info("Faster-Whisper loaded successfully!")

                except Exception as load_error:
                    logging.error(f"Failed to load Whisper model: {str(load_error)}")
                    self.show_error.emit("Model Load Error",
                        f"Could not load Whisper model '{model_name}':\n\n{str(load_error)}\n\n"
                        f"Verify model files exist in:\n{model_path}"
                    )
                    return None

            # === Transcribe ===
            language = cfg["whisper_language"] if cfg["whisper_language"] != "auto" else None
            audio_duration = len(audio_array) / RATE

            logging.info(f"Processing audio with duration {int(audio_duration//60):02}:{audio_duration%60:05.3f}")

            segments, info = self.faster_whisper_model.transcribe(
                audio_array,
                language=language,
                beam_size=5,
                vad_filter=False,
                word_timestamps=False
            )

            transcription = " ".join([segment.text for segment in segments]).strip()

            if language is None:
                logging.info(f"Detected language: {info.language} ({info.language_probability:.0%})")

            if transcription:
                logging.info(f"Transcription: {transcription}")

            return transcription if transcription else None

        except Exception as e:
            logging.error(f"Transcription error: {str(e)}")
            logging.error(traceback.format_exc())
            return None

    # ========================
    # === INTERNAL HELPERS ===
    # ========================

    def _get_whisper_model_path(self, model_name):
        """Find local Whisper model directory."""
        model_dir = os.path.join(WHISPER_MODELS_DIR, model_name)
        if os.path.exists(model_dir) and os.path.exists(os.path.join(model_dir, "model.bin")):
            return model_dir
        return None


class TTSEngine:
    """
    === TTSEngine — Coqui XTTS-v2 Text-to-Speech Engine ===
    === Handles model loading, audio generation and playback ===
    === Decoupled from GUI — communicates via callbacks and threading.Events ===
    """

    def __init__(self, vu_output_signal, volume_getter, language_getter, output_device_getter):
        """
        Args:
            vu_output_signal      : pyqtSignal(int) — for VU meter updates
            volume_getter         : callable() → int — returns current volume level (0-100)
            language_getter       : callable() → str — returns current whisper language
            output_device_getter  : callable() → int|None — returns output device index
        """
        # === Callbacks & signals from GUI ===
        self.vu_output_signal      = vu_output_signal
        self.get_volume            = volume_getter
        self.get_language          = language_getter
        self.get_output_device     = output_device_getter

        # === Model state ===
        self.coqui_model           = None
        self.speaker_latents       = None
        self.coqui_device          = "cuda" if torch.cuda.is_available() else "cpu"

        # === TTS parameters (updated from GUI sliders) ===
        self.coqui_temperature       = 0.7
        self.coqui_speed             = 1.0
        self.coqui_stream_chunk_size = 350
        self.selected_coqui_sample   = ""

        # === Threading primitives ===
        self.tts_queue     = queue.Queue()
        self.tts_event     = threading.Event()   # === Shutdown signal ===
        self.stop_tts_flag = threading.Event()   # === Interrupt current playback ===
        self.tts_lock      = threading.Lock()
        self.tts_active    = False

        # === PyAudio stream reference (for stop_playback) ===
        self.current_tts_stream = None

    # ==================
    # === PUBLIC API ===
    # ==================

    def start(self):
        """Start the TTS worker thread."""
        self.tts_thread = threading.Thread(target=self.tts_worker, daemon=True)
        self.tts_thread.start()
        logging.info("TTS worker thread started.")

    def stop(self):
        """Graceful shutdown — signal worker thread to exit."""
        self.tts_event.set()
        self.tts_queue.put(None)

    def speak(self, text, completion_event=None):
        """
        Queue text for TTS playback.

        Args:
            text             : str — text to speak
            completion_event : threading.Event | None
                               If provided, .set() called after full playback + drain.
                               Pass None for fire-and-forget (e.g. manual text input).
        """
        self.tts_queue.put((text, completion_event))

    def stop_playback(self):
        """Interrupt current TTS playback immediately (barge-in / user interrupt)."""
        self.stop_tts_flag.set()

        # === Flush pending queue ===
        with self.tts_queue.mutex:
            self.tts_queue.queue.clear()

        # === Stop PyAudio stream ===
        with self.tts_lock:
            if self.current_tts_stream and self.current_tts_stream.is_active():
                try:
                    self.current_tts_stream.stop_stream()
                except:
                    pass

        self.tts_active = False
        self.vu_output_signal.emit(0)
        logging.info("TTS stop signal sent.")

    def invalidate_latents(self):
        """Force recalculation of speaker latents on next synthesis (call on voice sample change)."""
        self.speaker_latents = None

    def load_samples(self):
        """Return list of available .wav sample names from COQUI_SAMPLES_DIR."""
        try:
            if not os.path.exists(COQUI_SAMPLES_DIR):
                raise FileNotFoundError(f"Coqui samples directory not found: {COQUI_SAMPLES_DIR}")
            samples      = glob.glob(os.path.join(COQUI_SAMPLES_DIR, "*.wav"))
            sample_names = [os.path.basename(s) for s in samples]
            logging.info(f"Coqui samples loaded: {sample_names}")
            return sample_names
        except Exception as e:
            logging.error(f"Coqui load_samples error: {str(e)}")
            return []

    def release_gpu_memory(self):
        """Unload model and free VRAM."""
        if self.coqui_model is not None:
            del self.coqui_model
            self.coqui_model     = None
            self.speaker_latents = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logging.info("TTS GPU memory released.")

    # ================================
    # === INTERNAL — WORKER THREAD ===
    # ================================

    def tts_worker(self):
        p      = None
        stream = None
        PLAYBACK_CHUNK = 1024
        SAMPLE_RATE    = 24000

        try:
            p = pyaudio.PyAudio()
            output_device_index = self.get_output_device()

            # === frames_per_buffer forces stream.write() to block for actual audio duration ===
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                output=True,
                output_device_index=output_device_index,
                frames_per_buffer=PLAYBACK_CHUNK
            )
            self.current_tts_stream = stream
            logging.info("TTS Stream initialized.")

            while not self.tts_event.is_set():
                completion_event = None
                try:
                    item = self.tts_queue.get(timeout=0.1)
                    if item is None:
                        break
                    text, completion_event = item

                    if self.stop_tts_flag.is_set():
                        self.stop_tts_flag.clear()
                        if completion_event: completion_event.set()
                        continue

                    self.tts_active = True
                    self.stop_tts_flag.clear()
                    logging.info(f"Processing TTS: {text[:70]}...")

                    if not stream.is_active():
                        stream.start_stream()

                    # === Load model if not in memory ===
                    self._ensure_model_loaded()

                    # === Recalculate latents if voice sample changed ===
                    self._ensure_latents()

                    # === Generate audio stream ===
                    text_for_tts = emoji.demojize(text)
                    language     = self.get_language()
                    if language == "auto":
                        language = "en"

                    audio_chunks = self.coqui_model.inference_stream(
                        text=text_for_tts,
                        language=language,
                        gpt_cond_latent=self.speaker_latents[0],
                        speaker_embedding=self.speaker_latents[1],
                        stream_chunk_size=self.coqui_stream_chunk_size,
                        temperature=self.coqui_temperature,
                        enable_text_splitting=True,
                        speed=self.coqui_speed
                    )

                    # === Playback queue — decouples GPU generation from audio playback ===
                    playback_queue = queue.Queue(maxsize=0)
                    playback_done  = threading.Event()

                    def playback_thread_func():
                        try:
                            while True:
                                chunk = playback_queue.get()

                                if chunk is None:  # === Sentinel — end of audio ===
                                    break

                                if self.stop_tts_flag.is_set():
                                    # === Flush remaining chunks and exit immediately ===
                                    while not playback_queue.empty():
                                        try: playback_queue.get_nowait()
                                        except: pass
                                    break

                                # === Emit VU BEFORE write — synchronized with actual playback ===
                                audio_float = chunk.astype(np.float32) / 32768.0
                                rms         = np.sqrt(np.mean(audio_float ** 2))
                                level       = min(int(rms * 100), 14)
                                self.vu_output_signal.emit(level)

                                with self.tts_lock:
                                    if stream.is_stopped(): stream.start_stream()
                                    stream.write(chunk.tobytes())

                        except Exception as e:
                            logging.error(f"Playback thread error: {e}")
                        finally:
                            # === Guaranteed — playback_done always set even on exception ===
                            playback_done.set()

                    pb_thread = threading.Thread(target=playback_thread_func, daemon=True)
                    pb_thread.start()

                    # === GPU generates chunks and feeds the playback queue ===
                    for audio_chunk in audio_chunks:
                        if self.stop_tts_flag.is_set():
                            logging.info("TTS interrupted.")
                            break

                        audio_data_full = (audio_chunk.squeeze().cpu().numpy() * 32767).astype(np.int16)
                        volume_factor   = self.get_volume() / 100.0
                        audio_data_full = (audio_data_full * volume_factor).astype(np.int16)

                        for i in range(0, len(audio_data_full), PLAYBACK_CHUNK):
                            if self.stop_tts_flag.is_set():
                                break
                            playback_queue.put(audio_data_full[i:i + PLAYBACK_CHUNK])

                    # === Send sentinel — signals end of generation ===
                    playback_queue.put(None)

                    # === Wait for playback thread to fully finish ===
                    if not playback_done.wait(timeout=45):
                        logging.warning("Playback timeout!")

                    # === Final hardware buffer drain ===
                    with self.tts_lock:
                        if stream and stream.is_active():
                            try:
                                stream.stop_stream()
                                time.sleep(0.1)  # === Small hardware drain margin ===
                                stream.start_stream()
                            except:
                                pass

                except queue.Empty:
                    continue
                except Exception as e:
                    logging.error(f"TTS Error: {str(e)}")
                    self.coqui_model = None  # === Force model reload on next request ===
                finally:
                    self.tts_active = False
                    self.stop_tts_flag.clear()
                    self.vu_output_signal.emit(0)
                    # === completion_event.set() called AFTER full hardware drain ===
                    if completion_event is not None:
                        completion_event.set()
                        logging.info("TTS completion signaled — audio fully played.")

        except Exception as e:
            logging.error(f"Critical TTS Worker Error: {str(e)}")
        finally:
            with self.tts_lock:
                if stream:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except:
                        pass
                if p:
                    p.terminate()

    # ========================
    # === INTERNAL HELPERS ===
    # ========================

    def _ensure_model_loaded(self):
        """Load XTTS model if not already in memory."""
        if self.coqui_model is None:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            config = XttsConfig()
            config.load_json(os.path.join(COQUI_MODELS_DIR, "config.json"))
            self.coqui_model = Xtts.init_from_config(config)
            self.coqui_model.load_checkpoint(config, checkpoint_dir=COQUI_MODELS_DIR, eval=True)
            self.coqui_model.to(self.coqui_device)
            logging.info("XTTS Model Loaded.")

    def _ensure_latents(self):
        """Calculate speaker latents if not cached."""
        if self.speaker_latents is None:
            speaker_wav                        = os.path.join(COQUI_SAMPLES_DIR, self.selected_coqui_sample)
            gpt_cond_latent, speaker_embedding = self.coqui_model.get_conditioning_latents(audio_path=[speaker_wav])
            self.speaker_latents               = (gpt_cond_latent, speaker_embedding)
            logging.info(f"XTTS Latents Recalculated for: {self.selected_coqui_sample}")


class LLMClient:
    """
    === LLMClient — LM Studio + MCP Communication Engine ===
    === Handles: LLM queries, MCP JSON-RPC 2.0, tool chain execution ===
    === Fully decoupled from GUI via callbacks and config_getter ===
    """

    def __init__(self,
                 show_warning_signal,
                 append_log_callback,
                 get_system_prompt,
                 get_recent_conv,
                 query_rag_callback,
                 on_mcp_connected_callback,
                 config_getter):
        """
        Args:
            show_warning_signal        : pyqtSignal(str, str) — thread-safe warning dialog
            append_log_callback        : callable(role, text, visible=True) — chat history log
            get_system_prompt          : callable() -> str — current system prompt text
            get_recent_conv            : callable(max_pairs) -> str — recent conversation context
            query_rag_callback         : callable(query, top_k, recent_lines) -> str — RAG query
            on_mcp_connected_callback  : callable(mcp_system_prompt) — called after MCP connects, updates GUI
            config_getter              : callable() -> dict — all LLM/MCP config params
        """
        # === Callbacks & signals ===
        self.show_warning          = show_warning_signal
        self.append_log            = append_log_callback
        self.get_system_prompt     = get_system_prompt
        self.get_recent_conv       = get_recent_conv
        self.query_rag             = query_rag_callback
        self.on_mcp_connected      = on_mcp_connected_callback
        self.get_config            = config_getter

        # === Internal state ===
        self.mcp_connected         = False
        self.mcp_system_prompt     = None
        self.mcp_request_id        = 0
        self.mcp_server_process    = None  # === Headless MCP server subprocess ===

    # =========================
    # === LM STUDIO QUERIES ===
    # =========================

    def query(self, prompt):
        """
        Main LLM query — injects system prompt, RAG memory and recent context.
        Used for all standard user interactions.
        """
        logging.info("Thinking: Processing prompt with LM Studio")

        cfg = self.get_config()

        if not cfg["model"] or "No loaded models" in cfg["model"]:
            logging.warning("Query aborted: No model loaded.")
            self.show_warning.emit(
                "LM Studio Warning",
                "Warning: No models loaded.\nPlease load a model in LM Studio to proceed."
            )
            return None

        try:
            system_prompt  = self.get_system_prompt()
            memory_context = ""

            if cfg["rag_memory_enabled"]:
                # === RECENT: always 3 pairs for continuity ===
                recent_context = self.get_recent_conv(max_pairs=3)

                # === Build dedup set from recent ===
                recent_lines = set()
                if recent_context:
                    for line in recent_context.splitlines():
                        text = line.split(": ", 1)[-1].strip().lower()[:80]
                        if text:
                            recent_lines.add(text)

                # === RAG: 2 extra pairs, deduplicated ===
                rag_context = self.query_rag(prompt, top_k=4, recent_lines=recent_lines)

                if rag_context:
                    memory_context += "=== SEMANTIC MEMORY ===\n"
                    memory_context += rag_context + "\n\n"
                    logging.info("📚 RAG: 2 semantic pairs injected (deduplicated)")

                if recent_context:
                    memory_context += "=== RECENT CONTEXT ===\n"
                    memory_context += recent_context + "\n"
                    logging.info("🕐 Recent: 3 pairs injected (continuity)")

            else:
                # === RAG OFF: only 3 recent pairs ===
                recent_context = self.get_recent_conv(max_pairs=3)
                if recent_context:
                    memory_context += "=== RECENT CONVERSATION ===\n"
                    memory_context += recent_context + "\n"
                    logging.info("🕐 Recent: 3 pairs injected (RAG disabled)")

            # === Inject memory into system prompt ===
            if memory_context:
                system_prompt += f"\n\n{memory_context}"

            # === Inject thinking flag ===
            if cfg["thinking_enabled"]:
                prompt = "/think\n" + prompt
            else:
                prompt = "/no_think\n" + prompt

            # === Debug logging ===
            logging.debug("=" * 60)
            logging.debug(f"📤 USER PROMPT:\n{prompt}")
            logging.debug("=" * 60)

            base_url = cfg["lm_server"].rstrip('/')
            chat_url = f"{base_url}/v1/chat/completions"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": prompt}
            ]

            payload = {
                "model":              cfg["model"],
                "messages":           messages,
                "temperature":        cfg["temperature"],
                "max_tokens":         max(cfg["max_tokens"], 512),
                "top_k":              cfg["top_k"],
                "repetition_penalty": cfg["repetition_penalty"],
                "min_p":              cfg["min_p"],
                "top_p":              cfg["top_p"]
            }

            response = requests.post(chat_url, json=payload)
            if response.status_code != 200:
                logging.error(f"LM Studio HTTP {response.status_code}: {response.text[:500]}")
                return None

            data = response.json()
            return data['choices'][0]['message']['content'].strip()

        except Exception as e:
            logging.error(f"LM Studio error: {str(e)}")
            self.show_warning.emit("LM Studio Error", f"Communication error:\n{str(e)}")
            return None

    def query_chain(self, follow_up_prompt):
        """
        Dedicated LLM call for MCP chain execution.
        No system prompt, no memory context — clean focused call.
        """
        logging.info("Thinking: MCP chain follow-up query")

        cfg = self.get_config()

        if not cfg["model"] or "No loaded models" in cfg["model"]:
            logging.warning("Chain query aborted: No model loaded.")
            return None

        try:
            # === Inject thinking flag ===
            if cfg["thinking_enabled"]:
                follow_up_prompt = "/think\n" + follow_up_prompt
            else:
                follow_up_prompt = "/no_think\n" + follow_up_prompt

            base_url = cfg["lm_server"].rstrip('/')
            chat_url = f"{base_url}/v1/chat/completions"

            messages = [{"role": "user", "content": follow_up_prompt}]

            payload = {
                "model":              cfg["model"],
                "messages":           messages,
                "temperature":        cfg["temperature"],
                "max_tokens":         max(cfg["max_tokens"], 512),
                "top_k":              cfg["top_k"],
                "repetition_penalty": cfg["repetition_penalty"],
                "min_p":              cfg["min_p"],
                "top_p":              cfg["top_p"]
            }

            response = requests.post(chat_url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content'].strip()

        except Exception as e:
            logging.error(f"Chain LLM error: {str(e)}")
            return None

    def list_models(self, timeout=3):
        """
        Fetch available models from LM Studio's /v1/models endpoint.
        Returns: list of model id strings, or None on failure (server not reachable).
        Pure network call — GUI is responsible for populating/handling the dropdown.
        """
        try:
            cfg      = self.get_config()
            base_url = cfg["lm_server"].rstrip('/')
            response = requests.get(f"{base_url}/v1/models", timeout=timeout)

            if response.status_code == 200:
                data = response.json()
                return [model["id"] for model in data.get("data", [])]

            return None

        except Exception:
            return None

    # ===============================
    # === MCP JSON-RPC 2.0 CLIENT ===
    # ===============================

    def mcp_request(self, method, params=None):
        """Low-level JSON-RPC 2.0 request — no business logic."""
        try:
            cfg = self.get_config()
            base_url = cfg["mcp_server"].rstrip('/')
            self.mcp_request_id += 1

            payload = {
                "jsonrpc": "2.0",
                "id":      self.mcp_request_id,
                "method":  method,
                "params":  params if params else {}
            }

            logging.debug(f"[MCP →] id={self.mcp_request_id} method={method}\n"
                          f"        params={json.dumps(params, indent=2, ensure_ascii=False) if params else '{}'}")

            response = requests.post(base_url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                logging.debug(f"[MCP ←] id={self.mcp_request_id} ERROR:\n"
                              f"        {json.dumps(data['error'], indent=2, ensure_ascii=False)}")
                logging.error(f"❌ MCP Error: {data['error']['message']}")
                return None

            logging.debug(f"[MCP ←] id={self.mcp_request_id} method={method} OK\n"
                          f"        result={json.dumps(data.get('result'), indent=2, ensure_ascii=False)}")

            return data.get("result")

        except Exception as e:
            logging.debug(f"[MCP ✗] id={self.mcp_request_id} method={method} EXCEPTION: {e}")
            logging.error(f"🔴 MCP request failed: {str(e)}")
            return None

    def mcp_request_with_retry(self, method, params=None, retries=3, delay=1):
        """MCP request with retry logic."""
        for attempt in range(retries):
            try:
                result = self.mcp_request(method, params)
                if result:
                    return result
                if attempt < retries - 1:
                    logging.warning(f"⚠️ MCP request failed (attempt {attempt+1}/{retries}), retrying in {delay}s...")
                    time.sleep(delay)
            except Exception as e:
                if attempt < retries - 1:
                    logging.warning(f"⚠️ MCP request error (attempt {attempt+1}/{retries}): {e}, retrying...")
                    time.sleep(delay)
                else:
                    logging.error(f"❌ MCP request failed after {retries} attempts: {e}")
        return None

    def initialize_mcp_connection(self):
        """Connect to MCP server and fetch system prompt."""
        try:
            cfg = self.get_config()
            logging.info("🔄 Connecting to MCP server...")

            # === Step 1: Initialize ===
            init_result = self.mcp_request_with_retry("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "Advanced-STS-Local-AI-Assistant", "version": "0.1.8 Beta"}
            })

            if not init_result:
                raise Exception("Initialize failed")

            # === Step 2: Get system prompt ===
            prompt_result = self.mcp_request_with_retry("prompts/get", {
                "name": "assistant_system_prompt"
            })

            if not prompt_result:
                raise Exception("Failed to get system prompt")

            messages = prompt_result.get("messages", [])
            if messages:
                self.mcp_system_prompt = messages[0]["content"]["text"]
                self.mcp_connected     = True
                logging.info(f"✅ MCP connected ({len(self.mcp_system_prompt)} chars prompt)")

                # === Notify GUI to update prompt_text ===
                self.on_mcp_connected(self.mcp_system_prompt)
                return True

            raise Exception("No prompt in response")

        except Exception as e:
            logging.error(f"❌ MCP connection failed: {str(e)}")
            self.mcp_connected = False
            cfg = self.get_config()
            self.show_warning.emit(
                "MCP Connection Failed",
                f"Could not connect to MCP server:\n{str(e)}\n\n"
                f"Server: {cfg['mcp_server']}\n\n"
                f"MCP features will be disabled."
            )
            return False

    def start_mcp_server_headless(self):
        """Start MCP server as background subprocess."""
        try:
            if self.mcp_server_process and self.mcp_server_process.poll() is None:
                logging.info("[MCP] Server already running")
                return

            if not os.path.exists(MCP_SERVER_FILE):
                logging.error(f"[MCP] Server file not found: {MCP_SERVER_FILE}")
                return

            self.mcp_server_process = subprocess.Popen(
                [sys.executable, MCP_SERVER_FILE, "--no-gui"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            logging.info(f"[MCP] Headless server started (PID: {self.mcp_server_process.pid})")
            time.sleep(2)

        except Exception as e:
            logging.error(f"[MCP] Failed to start server: {str(e)}")

    def stop_mcp_server_headless(self):
        """Stop MCP server subprocess."""
        if self.mcp_server_process:
            try:
                self.mcp_server_process.terminate()
                self.mcp_server_process.wait(timeout=5)
                logging.info("[MCP] Headless server stopped")
            except Exception as e:
                logging.error(f"[MCP] Error stopping server: {str(e)}")
            finally:
                self.mcp_server_process = None

    # ==========================
    # === MCP CHAIN EXECUTOR ===
    # ==========================

    def mcp_chain_executor(self, user_query, initial_response):
        """
        Multi-step tool calling loop.
        Executes tools, feeds results back to LLM until final text answer.
        """
        if not self.mcp_connected:
            logging.warning("⚠️ MCP not connected, returning initial response")
            return self.extract_text_response(initial_response)

        logging.info("🔗 Starting MCP chain execution...")

        cfg = self.get_config()

        conversation = [
            {"role": "user",      "content": user_query},
            {"role": "assistant", "content": initial_response}
        ]

        # === Safe defaults — prevents UnboundLocalError on early exit ===
        clean_response = ""
        results        = []

        for iteration in range(cfg["mcp_max_iterations"]):
            logging.info(f"🔄 MCP Iteration {iteration+1}/{cfg['mcp_max_iterations']}")

            last_response = conversation[-1]["content"]
            tool_calls    = self.parse_tool_calls(last_response)

            if not tool_calls:
                logging.info("✅ MCP chain complete - no more tool calls")
                break

            logging.info(f"🔧 Executing {len(tool_calls)} tool(s)...")
            results = []

            for idx, tool_call in enumerate(tool_calls, 1):
                logging.info(f"\n📋 Tool Call #{idx}:")
                logging.info(json.dumps(tool_call, indent=2, ensure_ascii=False))

                self.append_log("MCP Request",  json.dumps(tool_call, ensure_ascii=False), visible=False)

                result = self.execute_mcp_tool(tool_call)

                self.append_log("MCP Response", json.dumps(result, ensure_ascii=False), visible=False)

                results.append({"tool": tool_call.get("tool"), "result": result})

                status = "✅" if result.get("ok") else "❌"
                logging.info(f"  {status} Executed: {tool_call.get('tool')}\n")

            follow_up_prompt = self.build_mcp_follow_up_prompt(user_query, results)
            next_response    = self.query_chain(follow_up_prompt)

            if not next_response:
                logging.error("❌ AI returned None, stopping chain")
                break

            conversation.append({"role": "user",      "content": follow_up_prompt})
            conversation.append({"role": "assistant", "content": next_response})

        # === Extract final clean text response ===
        final_response = conversation[-1]["content"]
        clean_response = self.extract_text_response(final_response)

        if not clean_response and results:
            last_result = results[-1]
            tool_name   = last_result.get("tool", "")
            result_data = last_result.get("result", {})
            if result_data.get("ok"):
                clean_response = f"Done — {tool_name} completed successfully."
            else:
                clean_response = f"Something went wrong with {tool_name}."
        elif not clean_response:
            clean_response = "Done."

        logging.info(f"✅ MCP chain finished after {len(conversation)//2} iterations")
        return clean_response

    def build_mcp_follow_up_prompt(self, original_query, tool_results):
        """
        Build follow-up prompt for MCP chain execution.
        Workflow instructions are loaded dynamically from every *.md "skill" file
        in /MCP Skills/ - one file per plugin (e.g. "Windows Tools.md", "Google Services.md").
        Installing a new plugin just means dropping its skill file in that folder;
        no code change needed here to pick it up.

        Note: this function's code runs top to bottom like any Python function,
        but the ORDER OF THE TEXT SEEN BY THE MODEL is decided only by the final
        `return header + workflows_text + footer` line below — not by where each
        piece is built above it. header/footer/workflows_text are just plain
        strings sitting in memory until that line glues them together.
        """
        results_text = ""
        for item in tool_results:
            tool_name = item['tool']
            result    = item['result']
            if result.get("ok"):
                results_text += f"\n✅ {tool_name}:\n{json.dumps(result.get('data', result), indent=2)}\n"
            else:
                results_text += f"\n❌ {tool_name} FAILED:\n{result.get('error', 'Unknown error')}\n"

        separator = "=" * 60

        # === Fixed protocol header ( not specific to any plugin ) ===

        header = f"""TOOL EXECUTION RESULTS
{separator}

Original user query: "{original_query}"

Tool execution results:
{results_text}

{separator}
INSTRUCTIONS:
{separator}

You are in the middle of a multi-step tool execution flow.
Read the results above carefully, then decide what to do next.

GOLDEN RULE:
→ If you need to call ANOTHER tool — respond with JSON only, nothing else.
→ If you have ALL the information needed — respond in plain text, NO JSON.
→ If a tool returned an error — DO NOT invent your own recovery steps.
  Only retry with a DIFFERENT tool call if a workflow below explicitly says so.
  Otherwise, just tell the user what went wrong in plain text.

{separator}
WORKFLOWS:
{separator}

"""

        # === Fixed protocol footer ( not specific to any plugin ) ===

        footer = f"""

{separator}
RESPONSE FORMAT REMINDER:
{separator}

NEXT TOOL CALL   → JSON only:  {{"id": "call_N", "tool": "tool_name", "arguments": {{...}}}}
FINAL ANSWER     → Plain text only. Never mix JSON and text in the same response.

NOW respond based on the results above:"""

        # === Load every skill file from /MCP Skills/ — one per installed plugin ===
        # === Alphabetical order keeps the assembled prompt deterministic ===

        skills_dir   = os.path.join(BASE_DIR, "MCP Skills")
        skill_blocks = []

        if os.path.exists(skills_dir):
            skill_files = sorted(f for f in os.listdir(skills_dir) if f.lower().endswith(".md"))
            for filename in skill_files:
                try:
                    with open(os.path.join(skills_dir, filename), "r", encoding="utf-8") as f:
                        content = f.read()
                    content = content.replace("\\_", "_")  # === Markdown auto-escapes underscores ===
                    skill_blocks.append(content.strip())
                except Exception as e:
                    logging.warning(f"Could not load skill file '{filename}': {e}")

        workflows_text = "\n\n".join(skill_blocks)

        # === Only HERE does the order of header/workflows_text/footer actually matter ===
        return header + workflows_text + footer

    def execute_mcp_tool(self, tool_call):
        """Execute a single MCP tool call via JSON-RPC."""
        try:
            tool_name = tool_call.get("tool", "")
            arguments = tool_call.get("arguments", {})

            logging.info(f"🔧 Calling MCP tool: {tool_name}")

            result = self.mcp_request("tools/call", {
                "name":      tool_name,
                "arguments": arguments
            })

            if not result:
                return {"ok": False, "error": "MCP request failed"}

            content_blocks = result.get("content", [])
            if content_blocks:
                text_content = content_blocks[0].get("text", "")
                try:
                    data = json.loads(text_content)
                    if isinstance(data, dict):
                        return data
                    elif isinstance(data, list):
                        return {"ok": True, "data": data}
                    else:
                        return {"ok": True, "data": data}
                except json.JSONDecodeError:
                    return {"ok": True, "data": text_content}

            return {"ok": False, "error": "No content in response"}

        except Exception as e:
            logging.error(f"🔴 Tool execution error: {str(e)}")
            return {"ok": False, "error": str(e)}

    # ============================
    # === JSON PARSING HELPERS ===
    # ============================

    def extract_json_blocks(self, text: str):
        """Extract complete JSON objects from text using brace matching."""
        blocks = []
        stack  = 0
        start  = None

        for i, ch in enumerate(text):
            if ch == "{":
                if stack == 0:
                    start = i
                stack += 1
            elif ch == "}":
                stack -= 1
                if stack == 0 and start is not None:
                    blocks.append(text[start:i+1])
                    start = None
        return blocks

    def sanitize_json_string(self, s: str) -> str:
        """Clean up common LLM JSON formatting issues."""
        s = s.strip()
        # === Remove markdown code blocks ===
        if s.startswith("```"):
            lines = s.split("\n")
            s = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
        if s.endswith("```"):
            s = s[:-3].strip()
        # === Remove trailing commas before } or ] ===
        import re
        s = re.sub(r',\s*([}\]])', r'\1', s)
        return s

    def validate_and_parse_json(self, block: str):
        """Parse JSON block with sanitization fallback."""
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            try:
                return json.loads(self.sanitize_json_string(block))
            except json.JSONDecodeError:
                return None

    def parse_tool_calls(self, response: str):
        """Extract valid tool calls from LLM response."""
        if not response:
            return []

        tool_calls = []
        blocks     = self.extract_json_blocks(response)

        for block in blocks:
            parsed = self.validate_and_parse_json(block)
            if not parsed:
                continue
            if "tool" in parsed and "arguments" in parsed:
                if "id" not in parsed:
                    parsed["id"] = f"call_{len(tool_calls)+1}"
                tool_calls.append(parsed)

        if tool_calls:
            logging.info(f"✅ Parsed tool call: {tool_calls[0].get('tool')} (id: {tool_calls[0].get('id')})")
            logging.info(f"📦 Total tool calls parsed: {len(tool_calls)}")

        return tool_calls

    def extract_text_response(self, response):
        """Remove JSON tool calls from response, return clean text."""
        json_blocks = self.extract_json_blocks(response)
        clean_text  = response
        for block in json_blocks:
            clean_text = clean_text.replace(block, "")
        clean_text = " ".join(clean_text.split()).strip()
        return clean_text if clean_text else ""


class AIAssistantGUI(QMainWindow):
    # ===== THREAD SAFETY SIGNALS =====
    show_warning_signal  = pyqtSignal(str, str)
    vu_input_signal      = pyqtSignal(int)   # === VU Meter microphone — thread-safe ===
    vu_output_signal     = pyqtSignal(int)   # === VU Meter TTS output — thread-safe ===
    chat_update_signal   = pyqtSignal(str, str, str)  # === Thread-safe chat update: role, text, color ===

    def __init__(self):
        super().__init__()
        
        # ====== INITIALIZE GUI ======
        self.setWindowTitle("= Advanced STS Local AI Assistant 0.1.8 Beta =")
        self.setGeometry(0, 0, 1326, 663)
        self.setFixedSize(1326, 663)
        
        # === Connect the warning signal to the safe function ===
        self.show_warning_signal.connect(self.show_thread_safe_warning)
        self.vu_input_signal.connect(lambda lvl: self.vu_meter_input.set_level(lvl))
        self.vu_output_signal.connect(lambda lvl: self.vu_meter_output.set_level(lvl))
        self.chat_update_signal.connect(self._append_chat_safe)  # === Thread-safe chat update ===

        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - 1326) // 2
        y = (screen.height() - 663) // 2
        self.move(x, y)
        
        self.setStyleSheet("QMainWindow { background-color: #191919; }")
        
        # === Variables ===
        self.selected_mic = ""
        self.selected_output_device = ""
        self.selected_lm_model = ""
        self.selected_coqui_sample = ""
        self.volume_level = 100
        self.mic_volume = 100
        self.coqui_temperature = 0.7
        self.coqui_top_p = 0.95
        self.coqui_top_k = 50
        self.coqui_speed = 1.0
        self.coqui_stream_chunk_size = 200
        self.vad_threshold = VAD_THRESHOLD
        self.vad_min_speech_duration = VAD_MIN_SPEECH_DURATION
        self.vad_min_silence_duration = VAD_MIN_SILENCE_DURATION
        self.vad_device = "cuda" if torch.cuda.is_available() else "cpu"
        self.is_recording = False
        self.audio_thread = None
        self.audio_data = None
        self.whisper_language = "en" 
        self.whisper_device = "cuda" if torch.cuda.is_available() else "cpu"  
        self.whisper_model = "small"
        self.whisper_compute_type = "int8"  # === Set int8/float16/float32 depending on your hardware support ===
        self.chat_text = None
        self.debug_text = None
        self.vu_level_input = 0
        self.vu_level_output = 0
        self.wake_word = "Jarvis"
        self.wake_word_enabled = False
        self.use_mcp_server = False
        # === MCP state owned by self.llm (LLMClient) ===
        self.mcp_request_id = 0           
        self.mcp_max_iterations = 5       
        self.real_talk_enabled = False
        self.rag_memory_enabled = False
        self.current_profile_name = None  # === No profile loaded => using Jarvis (default) ===
        self.profile_modified = False     # === Dirty flag — True when unsaved changes exist ===
        self.current_chat_log = CHAT_LOG  # === Starts Generic ===
        self.current_rag_dir = os.path.join(RAG_DATABASE_DIR, "Jarvis")  # === Jarvis is the default profile with hardcoded settings ===
        self.current_coqui_device = "cuda" if torch.cuda.is_available() else "cpu"
        self.current_vad_device = self.vad_device
        self.lm_server = "http://127.0.0.1:1234"
        self.mcp_server = "http://127.0.0.1:8765"
        self.chat_history = []
        self.image_references = []
        self.temperature = 0.7
        self.max_tokens = 512
        self.top_k = 40
        self.repetition_penalty = 1.1
        self.min_p = 0.05
        self.top_p = 0.95
        self.thinking_enabled = False  # === Think/No Think flag for LLM calls ===

        # === TTSEngine — handles all Coqui TTS generation and playback ===
        self.tts = TTSEngine(
            vu_output_signal     = self.vu_output_signal,
            volume_getter        = lambda: self.volume_level,
            language_getter      = lambda: self.whisper_language,
            output_device_getter = self._get_tts_output_device_index
        )

        # === ProfileManager — handles profile JSON I/O and path management ===
        self.profiles = ProfileManager(
            settings_dir      = SETTINGS_DIR,
            history_dir       = HISTORY_DIR,
            rag_database_dir  = RAG_DATABASE_DIR
        )

        # === RAGManager — handles ChromaDB semantic memory and recent conversation ===
        self.rag = RAGManager(
            show_warning_signal = self.show_warning_signal,
            get_chat_history    = lambda: self.chat_history,
            config_getter       = self._get_rag_config
        )

        # === LLMClient — handles LM Studio queries, MCP and tool chain execution ===
        self.llm = LLMClient(
            show_warning_signal       = self.show_warning_signal,
            append_log_callback       = self.append_log,
            get_system_prompt         = lambda: self.prompt_text.toPlainText().strip(),
            get_recent_conv           = self.rag.get_recent_conversation,
            query_rag_callback        = self.rag.query,
            on_mcp_connected_callback = self._on_mcp_connected,
            config_getter             = self._get_llm_config
        )

        # === AudioProcessor — handles VAD, microphone capture and Whisper STT ===
        self.audio = AudioProcessor(
            vu_input_signal    = self.vu_input_signal,
            on_speech_detected = self.process_audio_segment,
            stop_tts_callback  = self.stop_tts_stream,
            is_tts_active      = lambda: self.tts.tts_active,
            is_real_talk       = lambda: self.real_talk_enabled,
            show_error_signal  = self.show_warning_signal,
            config_getter      = self._get_audio_config
        )
        self.audio.init_silero_vad()
        self.create_gui()
        self.setup_debug_logging()
        self._load_audio_devices()
        self._load_audio_devices()
        # === Load TTS voice samples into dropdown ===
        samples = self.tts.load_samples()
        if hasattr(self, 'coqui_dropdown'):
            self.coqui_dropdown.addItems(samples)
            if samples:
                self.tts.selected_coqui_sample = samples[0]
        
        # === We use Timer to not block the GUI at startup ===
        QTimer.singleShot(500, self.load_lm_models)
        
        self.auto_refresh_lm_models()
        self.load_initial_chat_history()
        self.ensure_default_profile() # === Ensures that always is an active profile ===
        # === NOTE: MCP init triggered via radio signal in _apply_settings_to_gui ===
        # === No explicit call here — would cause double init on startup ===
        logging.info("Starting application")

        self.tts.start()
        self.rag.start()

        # === System Monitor — dedicated worker thread, 0.5s refresh ===
        self.monitor_worker = SystemMonitorWorker()
        self.monitor_thread = QThread()
        self.monitor_worker.moveToThread(self.monitor_thread)
        self.monitor_thread.started.connect(self.monitor_worker.start_monitoring)
        self.monitor_worker.metrics_ready.connect(self.update_resources)
        self.monitor_thread.start()

    def show_thread_safe_warning(self, title, message):
        """This function runs on the Main Thread and displays the message without crashing the application."""
        QMessageBox.warning(self, title, message)

    def create_gui(self):
        # === Modified stylesheet to allow EXACT positioning of title ===
        group_style = """
            QGroupBox {
                background-color: #191919;
                border: 2px solid #FFFFFF;
                border-radius: 10px;
                margin-top: 15px; 
                font-weight: bold;
                color: #FFFFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #FFFFFF;
                left: 10px;
                top: 8px;
                background-color: #191919;
            }
        """
        
        self.button_style = button_style = """
            QPushButton {
                background-color: #787878;
                color: #FFFFFF;
                border-radius: 10px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #8C8C8C;
            }
            QPushButton:pressed {
                background-color: #666666;
            }
        """
        
        combo_style = """
            QComboBox {
                background-color: #121212;
                color: #FFFFFF;
                border: 1px solid #FFFFFF;
                border-radius: 5px;
                padding: 1px 3px 3px 3px;  /* top right bottom left */
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #121212;
                color: #FFFFFF;
                selection-background-color: #3C3C3C;
                padding-top: 2px;  /* Also move the text in the list 2px up */
            }
        """        
        slider_style = """
            QSlider::groove:horizontal {
                background: #3C3C3C;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
        """
      
        # ====== AUDIO INPUT FRAME ======
        mic_frame = QGroupBox("Audio Input", self)
        mic_frame.setGeometry(6, -6, 326, 118)
        mic_frame.setStyleSheet(group_style)
        
        mic_label = QLabel("Select Microphone", mic_frame)
        mic_label.setGeometry(10, 20, 150, 20)
        mic_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.mic_dropdown = QComboBox(mic_frame)
        self.mic_dropdown.setGeometry(9, 42, 307, 20)
        self.mic_dropdown.setStyleSheet(combo_style)
        
        # === VU Meter Input ===
        self.vu_meter_input = VUMeter(mic_frame)
        self.vu_meter_input.setGeometry(9, 70, 310, 20)
        self.vu_meter_input.setStyleSheet("background-color: #191919;")
        
        mic_volume_label = QLabel("Microphone Volume", mic_frame)
        mic_volume_label.setGeometry(10, 86, 120, 20)
        mic_volume_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.mic_volume_slider = QSlider(Qt.Horizontal, mic_frame)
        self.mic_volume_slider.setGeometry(115, 88, 160, 20)
        self.mic_volume_slider.setRange(0, 100)
        self.mic_volume_slider.setValue(self.mic_volume)
        self.mic_volume_slider.setStyleSheet(slider_style)
        self.mic_volume_slider.valueChanged.connect(self.update_mic_volume_label)
        self.connect_dirty_flag(self.mic_volume_slider)
        
        self.mic_volume_value_label = QLabel(str(self.mic_volume), mic_frame)
        self.mic_volume_value_label.setGeometry(290, 86, 50, 20)
        self.mic_volume_value_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        # ====== AUDIO OUTPUT FRAME ======
        audio_output_frame = QGroupBox("Audio Output", self)
        audio_output_frame.setGeometry(6, 538, 326, 118)
        audio_output_frame.setStyleSheet(group_style)
        
        output_label = QLabel("Select Output Device", audio_output_frame)
        output_label.setGeometry(10, 20, 150, 20)
        output_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.output_device_dropdown = QComboBox(audio_output_frame)
        self.output_device_dropdown.setGeometry(9, 42, 307, 20)
        self.output_device_dropdown.setStyleSheet(combo_style)
        
        # === VU Meter Output ===
        self.vu_meter_output = VUMeter(audio_output_frame)
        self.vu_meter_output.setGeometry(9, 70, 310, 20)
        self.vu_meter_output.setStyleSheet("background-color: #191919;")
        
        volume_label = QLabel("Output Volume", audio_output_frame)
        volume_label.setGeometry(10, 86, 115, 20)
        volume_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.volume_slider = QSlider(Qt.Horizontal, audio_output_frame)
        self.volume_slider.setGeometry(115, 88, 160, 20)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.volume_level)
        self.volume_slider.setStyleSheet(slider_style)
        self.volume_slider.valueChanged.connect(self.update_volume_label)
        self.connect_dirty_flag(self.volume_slider)
        
        self.volume_value_label = QLabel(str(self.volume_level), audio_output_frame)
        self.volume_value_label.setGeometry(290, 86, 50, 20)
        self.volume_value_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        # ====== WHISPER STT SETTINGS ======
        stt_frame = QGroupBox("Faster-Whisper STT Settings", self)
        stt_frame.setGeometry(6, 224, 326, 110)
        stt_frame.setStyleSheet(group_style)
        
        # === Language ===
        language_label = QLabel("Language", stt_frame)
        language_label.setGeometry(26, 20, 80, 20)
        language_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.whisper_lang_group = QButtonGroup(stt_frame)
        
        radio_auto = QRadioButton("Auto Detect", stt_frame)
        radio_auto.setGeometry(10, 40, 100, 20)
        radio_auto.setStyleSheet("color: #FFFFFF;")
        radio_auto.toggled.connect(lambda checked: setattr(self, 'whisper_language', 'auto') if checked else None)
        self.whisper_lang_group.addButton(radio_auto, 0)
        
        radio_en = QRadioButton("English", stt_frame)
        radio_en.setGeometry(10, 60, 100, 20)
        radio_en.setStyleSheet("color: #FFFFFF;")
        radio_en.setChecked(True)
        radio_en.toggled.connect(lambda checked: setattr(self, 'whisper_language', 'en') if checked else None)
        self.whisper_lang_group.addButton(radio_en, 1)
        
        radio_ro = QRadioButton("Romanian", stt_frame)
        radio_ro.setGeometry(10, 80, 100, 20)
        radio_ro.setStyleSheet("color: #FFFFFF;")
        radio_ro.toggled.connect(lambda checked: setattr(self, 'whisper_language', 'ro') if checked else None)
        self.whisper_lang_group.addButton(radio_ro, 2)
        
        # === Device ===
        device_label = QLabel("Device", stt_frame)
        device_label.setGeometry(120, 20, 60, 20)
        device_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.whisper_device_group = QButtonGroup(stt_frame)
        
        radio_gpu_whisper = QRadioButton("GPU", stt_frame)
        radio_gpu_whisper.setGeometry(115, 40, 60, 20)
        radio_gpu_whisper.setStyleSheet("color: #FFFFFF;")
        radio_gpu_whisper.setChecked(torch.cuda.is_available())
        radio_gpu_whisper.toggled.connect(lambda checked: self.on_device_change("whisper", "cuda") if checked else None)
        self.whisper_device_group.addButton(radio_gpu_whisper, 0)
        
        radio_cpu_whisper = QRadioButton("CPU", stt_frame)
        radio_cpu_whisper.setGeometry(115, 60, 60, 20)
        radio_cpu_whisper.setStyleSheet("color: #FFFFFF;")
        radio_cpu_whisper.setChecked(not torch.cuda.is_available())
        radio_cpu_whisper.toggled.connect(lambda checked: self.on_device_change("whisper", "cpu") if checked else None)
        self.whisper_device_group.addButton(radio_cpu_whisper, 1)
        
        # === Model ===
        model_label = QLabel("Model", stt_frame)
        model_label.setGeometry(230, 20, 60, 20)
        model_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.whisper_model_group = QButtonGroup(stt_frame)
        
        radio_tiny = QRadioButton("Tiny", stt_frame)
        radio_tiny.setGeometry(185, 40, 60, 20)
        radio_tiny.setStyleSheet("color: #FFFFFF;")
        radio_tiny.toggled.connect(lambda checked: setattr(self, 'whisper_model', 'tiny') if checked else None)
        self.whisper_model_group.addButton(radio_tiny, 0)
        
        radio_base = QRadioButton("Base", stt_frame)
        radio_base.setGeometry(185, 60, 60, 20)
        radio_base.setStyleSheet("color: #FFFFFF;")
        radio_base.toggled.connect(lambda checked: setattr(self, 'whisper_model', 'base') if checked else None)
        self.whisper_model_group.addButton(radio_base, 1)
        
        radio_small = QRadioButton("Small", stt_frame)
        radio_small.setGeometry(185, 80, 60, 20)
        radio_small.setStyleSheet("color: #FFFFFF;")
        radio_small.setChecked(True)
        radio_small.toggled.connect(lambda checked: setattr(self, 'whisper_model', 'small') if checked else None)
        self.whisper_model_group.addButton(radio_small, 2)
        
        radio_medium = QRadioButton("Medium", stt_frame)
        radio_medium.setGeometry(240, 40, 80, 20)
        radio_medium.setStyleSheet("color: #FFFFFF;")
        radio_medium.toggled.connect(lambda checked: setattr(self, 'whisper_model', 'medium') if checked else None)
        self.whisper_model_group.addButton(radio_medium, 3)
        
        radio_large = QRadioButton("Large", stt_frame)
        radio_large.setGeometry(240, 60, 80, 20)
        radio_large.setStyleSheet("color: #FFFFFF;")
        radio_large.toggled.connect(lambda checked: setattr(self, 'whisper_model', 'large') if checked else None)
        self.whisper_model_group.addButton(radio_large, 4)
        
        # ====== SILERO VAD SETTINGS ======
        vad_frame = QGroupBox("Silero VAD Settings", self)
        vad_frame.setGeometry(6, 106, 326, 125)
        vad_frame.setStyleSheet(group_style)
        
        threshold_label = QLabel("Threshold", vad_frame)
        threshold_label.setGeometry(33, 22, 80, 20)
        threshold_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.threshold_slider = QSlider(Qt.Horizontal, vad_frame)
        self.threshold_slider.setGeometry(115, 24, 160, 20)
        self.threshold_slider.setRange(0, 100)
        self.threshold_slider.setValue(int(self.vad_threshold * 100))
        self.threshold_slider.setStyleSheet(slider_style)
        self.threshold_slider.valueChanged.connect(self.update_threshold_label)
        self.connect_dirty_flag(self.threshold_slider)
        
        self.threshold_value_label = QLabel(f"{self.vad_threshold:.2f}", vad_frame)
        self.threshold_value_label.setGeometry(290, 22, 50, 20)
        self.threshold_value_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        min_speech_label = QLabel("Min Speech", vad_frame)
        min_speech_label.setGeometry(30, 46, 80, 20)
        min_speech_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.min_speech_slider = QSlider(Qt.Horizontal, vad_frame)
        self.min_speech_slider.setGeometry(115, 48, 160, 20)
        self.min_speech_slider.setRange(1, 20)
        self.min_speech_slider.setValue(int(self.vad_min_speech_duration * 10))
        self.min_speech_slider.setStyleSheet(slider_style)
        self.min_speech_slider.valueChanged.connect(self.update_min_speech_label)
        self.connect_dirty_flag(self.min_speech_slider)
        
        self.min_speech_value_label = QLabel(f"{self.vad_min_speech_duration:.1f}", vad_frame)
        self.min_speech_value_label.setGeometry(290, 46, 50, 20)
        self.min_speech_value_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        min_silence_label = QLabel("Min Silence", vad_frame)
        min_silence_label.setGeometry(30, 70, 80, 20)
        min_silence_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.min_silence_slider = QSlider(Qt.Horizontal, vad_frame)
        self.min_silence_slider.setGeometry(115, 72, 160, 20)
        self.min_silence_slider.setRange(1, 20)
        self.min_silence_slider.setValue(int(self.vad_min_silence_duration * 10))
        self.min_silence_slider.setStyleSheet(slider_style)
        self.min_silence_slider.valueChanged.connect(self.update_min_silence_label)
        self.connect_dirty_flag(self.min_silence_slider)
        
        self.min_silence_value_label = QLabel(f"{self.vad_min_silence_duration:.1f}", vad_frame)
        self.min_silence_value_label.setGeometry(290, 70, 50, 20)
        self.min_silence_value_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        vad_device_label = QLabel("Device", vad_frame)
        vad_device_label.setGeometry(40, 95, 60, 20)
        vad_device_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.vad_device_group = QButtonGroup(vad_frame)
        
        radio_gpu_vad = QRadioButton("GPU", vad_frame)
        radio_gpu_vad.setGeometry(160, 95, 60, 20)
        radio_gpu_vad.setStyleSheet("color: #FFFFFF;")
        radio_gpu_vad.setChecked(torch.cuda.is_available())
        radio_gpu_vad.toggled.connect(lambda checked: self.on_device_change("vad", "cuda") if checked else None)
        self.vad_device_group.addButton(radio_gpu_vad, 0)
        
        radio_cpu_vad = QRadioButton("CPU", vad_frame)
        radio_cpu_vad.setGeometry(210, 95, 60, 20)
        radio_cpu_vad.setStyleSheet("color: #FFFFFF;")
        radio_cpu_vad.setChecked(not torch.cuda.is_available())
        radio_cpu_vad.toggled.connect(lambda checked: self.on_device_change("vad", "cpu") if checked else None)
        self.vad_device_group.addButton(radio_cpu_vad, 1)
        
        # ====== COQUI TTS SETTINGS ======
        tts_frame = QGroupBox("Coqui XTTS-V2 Settings", self)
        tts_frame.setGeometry(6, 326, 326, 220)
        tts_frame.setStyleSheet(group_style)
        
        coqui_label = QLabel("Select Voice Sample", tts_frame)
        coqui_label.setGeometry(10, 20, 150, 20)
        coqui_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.coqui_dropdown = QComboBox(tts_frame)
        self.coqui_dropdown.setGeometry(9, 42, 307, 20)
        self.coqui_dropdown.setStyleSheet(combo_style)
        self.coqui_dropdown.currentTextChanged.connect(self.update_coqui_sample)
        
        temperature_label = QLabel("Temperature", tts_frame)
        temperature_label.setGeometry(28, 64, 90, 20)
        temperature_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.coqui_temperature_slider = QSlider(Qt.Horizontal, tts_frame)
        self.coqui_temperature_slider.setGeometry(115, 66, 160, 20)
        self.coqui_temperature_slider.setRange(0, 100)
        self.coqui_temperature_slider.setValue(int(self.coqui_temperature * 100))
        self.coqui_temperature_slider.setStyleSheet(slider_style)
        self.coqui_temperature_slider.valueChanged.connect(self.update_coqui_temperature_label)
        self.connect_dirty_flag(self.coqui_temperature_slider)
        
        self.coqui_temperature_value_label = QLabel(f"{self.coqui_temperature:.2f}", tts_frame)
        self.coqui_temperature_value_label.setGeometry(290, 64, 50, 20)
        self.coqui_temperature_value_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        top_p_label = QLabel("Top P", tts_frame)
        top_p_label.setGeometry(46, 88, 60, 20)
        top_p_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.coqui_top_p_slider = QSlider(Qt.Horizontal, tts_frame)
        self.coqui_top_p_slider.setGeometry(115, 90, 160, 20)
        self.coqui_top_p_slider.setRange(0, 100)
        self.coqui_top_p_slider.setValue(int(self.coqui_top_p * 100))
        self.coqui_top_p_slider.setStyleSheet(slider_style)
        self.coqui_top_p_slider.valueChanged.connect(self.update_coqui_top_p_label)
        self.connect_dirty_flag(self.coqui_top_p_slider)
        
        self.coqui_top_p_value_label = QLabel(f"{self.coqui_top_p:.2f}", tts_frame)
        self.coqui_top_p_value_label.setGeometry(290, 88, 50, 20)
        self.coqui_top_p_value_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        top_k_label = QLabel("Top K", tts_frame)
        top_k_label.setGeometry(46, 113, 60, 20)
        top_k_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.coqui_top_k_slider = QSlider(Qt.Horizontal, tts_frame)
        self.coqui_top_k_slider.setGeometry(115, 115, 160, 20)
        self.coqui_top_k_slider.setRange(1, 100)
        self.coqui_top_k_slider.setValue(self.coqui_top_k)
        self.coqui_top_k_slider.setStyleSheet(slider_style)
        self.coqui_top_k_slider.valueChanged.connect(self.update_coqui_top_k_label)
        self.connect_dirty_flag(self.coqui_top_k_slider)
        
        self.coqui_top_k_value_label = QLabel(str(self.coqui_top_k), tts_frame)
        self.coqui_top_k_value_label.setGeometry(290, 113, 50, 20)
        self.coqui_top_k_value_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        speed_label = QLabel("Speed", tts_frame)
        speed_label.setGeometry(46, 138, 60, 20)
        speed_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.coqui_speed_slider = QSlider(Qt.Horizontal, tts_frame)
        self.coqui_speed_slider.setGeometry(115, 140, 160, 20)
        self.coqui_speed_slider.setRange(5, 20)
        self.coqui_speed_slider.setValue(int(self.coqui_speed * 10))
        self.coqui_speed_slider.setStyleSheet(slider_style)
        self.coqui_speed_slider.valueChanged.connect(self.update_coqui_speed_label)
        self.connect_dirty_flag(self.coqui_speed_slider)
        
        self.coqui_speed_value_label = QLabel(f"{self.coqui_speed:.1f}", tts_frame)
        self.coqui_speed_value_label.setGeometry(290, 138, 50, 20)
        self.coqui_speed_value_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        chunk_size_label = QLabel("Chunk Size", tts_frame)
        chunk_size_label.setGeometry(35, 163, 80, 20)
        chunk_size_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.coqui_stream_chunk_size_slider = QSlider(Qt.Horizontal, tts_frame)
        self.coqui_stream_chunk_size_slider.setGeometry(115, 165, 160, 20)
        self.coqui_stream_chunk_size_slider.setRange(100, 300)
        self.coqui_stream_chunk_size_slider.setSingleStep(5)
        self.coqui_stream_chunk_size_slider.setValue(self.coqui_stream_chunk_size)
        self.coqui_stream_chunk_size_slider.setStyleSheet(slider_style)
        self.coqui_stream_chunk_size_slider.valueChanged.connect(self.update_coqui_chunk_size_label)
        self.connect_dirty_flag(self.coqui_stream_chunk_size_slider)
        
        self.coqui_chunk_size_value_label = QLabel(str(self.coqui_stream_chunk_size), tts_frame)
        self.coqui_chunk_size_value_label.setGeometry(290, 163, 50, 20)
        self.coqui_chunk_size_value_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        coqui_device_label = QLabel("Device", tts_frame)
        coqui_device_label.setGeometry(44, 190, 60, 20)
        coqui_device_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.coqui_device_group = QButtonGroup(tts_frame)
        
        radio_gpu_coqui = QRadioButton("GPU", tts_frame)
        radio_gpu_coqui.setGeometry(160, 190, 60, 20)
        radio_gpu_coqui.setStyleSheet("color: #FFFFFF;")
        radio_gpu_coqui.setChecked(torch.cuda.is_available())
        radio_gpu_coqui.toggled.connect(lambda checked: self.on_device_change("coqui", "cuda") if checked else None)
        self.coqui_device_group.addButton(radio_gpu_coqui, 0)
        
        radio_cpu_coqui = QRadioButton("CPU", tts_frame)
        radio_cpu_coqui.setGeometry(210, 190, 60, 20)
        radio_cpu_coqui.setStyleSheet("color: #FFFFFF;")
        radio_cpu_coqui.setChecked(not torch.cuda.is_available())
        radio_cpu_coqui.toggled.connect(lambda checked: self.on_device_change("coqui", "cpu") if checked else None)
        self.coqui_device_group.addButton(radio_cpu_coqui, 1)
        
        # ====== CHAT HISTORY ======
        chat_frame = QGroupBox("Chat History", self)
        chat_frame.setGeometry(338, -6, 650, 340)
        chat_frame.setStyleSheet(group_style)
        
        self.chat_text = QTextEdit(chat_frame)
        self.chat_text.setGeometry(8, 24, 634, 256)
        self.chat_text.setReadOnly(True)
        self.chat_text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # === Apply Scrollbar Style ===
        self.chat_text.setStyleSheet("""
            QTextEdit {
                background-color: #121212;
                color: #FFFFFF;
                border: 1px solid #FFFFFF;
                border-radius: 5px;
                font-family: 'Segoe UI';
                font-size: 10pt;
            }
        """ + SCROLLBAR_STYLE)

        # === Manual text input field ===
        self.chat_input = QTextEdit(chat_frame)
        self.chat_input.setGeometry(8, 286, 528, 20)
        self.chat_input.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_input.setStyleSheet("""
            QTextEdit {
                background-color: #121212;
                color: #00FF00;
                border: 1px solid #FFFFFF;
                border-radius: 5px;
                font-family: 'Segoe UI';
                font-size: 10pt;
            }
        """)

        # === Send button ===
        send_btn = QPushButton("Send Message", chat_frame)
        send_btn.setGeometry(542, 286, 100, 20)
        send_btn.setStyleSheet(self.button_style)
        send_btn.clicked.connect(self.send_manual_query)
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: #00FF00;
                color: #000000;
                border-radius: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
            QPushButton:pressed {
                background-color: #1B5E20;
            }
        """)
        
        load_history_btn = QPushButton("Load History", chat_frame)
        load_history_btn.setGeometry(436, 312, 100, 20)
        load_history_btn.setStyleSheet(button_style)
        load_history_btn.clicked.connect(self.load_chat_history)
        
        save_history_btn = QPushButton("Save History", chat_frame)
        save_history_btn.setGeometry(542, 312, 100, 20)
        save_history_btn.setStyleSheet(button_style)
        save_history_btn.clicked.connect(self.save_chat_history)
        
        clear_history_btn = QPushButton("Clear History", chat_frame)
        clear_history_btn.setGeometry(330, 312, 100, 20)
        clear_history_btn.setStyleSheet(button_style)
        clear_history_btn.clicked.connect(self.clear_chat_history)
        
        rebuild_rag_btn = QPushButton("Rebuild RAG", chat_frame)
        rebuild_rag_btn.setGeometry(223, 312, 100, 20)
        rebuild_rag_btn.setStyleSheet(button_style)
        rebuild_rag_btn.clicked.connect(self.rebuild_rag_database)

        rag_label = QLabel("RAG Memory", chat_frame)
        rag_label.setGeometry(10, 310, 120, 20)
        rag_label.setStyleSheet("color: #FFFFFF; border: none; font-weight: bold; font-size: 9pt;")

        self.rag_group = QButtonGroup(chat_frame)

        radio_rag_on = QRadioButton("On", chat_frame)
        radio_rag_on.setGeometry(100, 312, 40, 20)
        radio_rag_on.setStyleSheet("color: #FFFFFF;")
        radio_rag_on.toggled.connect(lambda checked: setattr(self, 'rag_memory_enabled', True) if checked else None)
        self.rag_group.addButton(radio_rag_on, 0)

        radio_rag_off = QRadioButton("Off", chat_frame)
        radio_rag_off.setGeometry(140, 312, 40, 20)
        radio_rag_off.setStyleSheet("color: #FFFFFF;")
        radio_rag_off.setChecked(True)
        radio_rag_off.toggled.connect(lambda checked: setattr(self, 'rag_memory_enabled', False) if checked else None)
        self.rag_group.addButton(radio_rag_off, 1)
        
        # ====== DEBUG CONSOLE ======
        debug_frame = QGroupBox("Debug Console", self)
        debug_frame.setGeometry(338, 326, 650, 330)
        debug_frame.setStyleSheet(group_style)
        
        self.debug_text = QTextEdit(debug_frame)
        self.debug_text.setGeometry(8, 24, 634, 298)
        self.debug_text.setReadOnly(True)
        self.debug_text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # === Apply Scrollbar Style ===
        self.debug_text.setStyleSheet("""
            QTextEdit {
                background-color: #121212;
                color: #A5A5A5;
                border: 1px solid #FFFFFF;
                border-radius: 5px;
                font-family: 'Segoe UI';
                font-size: 10pt;
            }
        """ + SCROLLBAR_STYLE)
        
        # ====== LM STUDIO SETTINGS ======
        lm_frame = QGroupBox("LM Studio Settings", self)
        lm_frame.setGeometry(994, -6, 326, 340)
        lm_frame.setStyleSheet(group_style)
        
        lm_label = QLabel("Select AI Model", lm_frame)
        lm_label.setGeometry(10, 20, 150, 20)
        lm_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        # === Using Custom Combo Box ===
        self.lm_model_dropdown = RefreshableComboBox(lm_frame)
        self.lm_model_dropdown.setGeometry(9, 42, 307, 20)
        self.lm_model_dropdown.setStyleSheet(combo_style)
        self.lm_model_dropdown.currentTextChanged.connect(lambda text: setattr(self, 'selected_lm_model', text))
        # === We connect the refresh callback ===
        self.lm_model_dropdown.set_refresh_callback(self.load_lm_models)

        # === Thinking label + radio buttons ===
        thinking_label = QLabel("Thinking", lm_frame)
        thinking_label.setGeometry(194, 20, 55, 20)
        thinking_label.setStyleSheet("color: #FFFFFF; border: none;")

        self.thinking_group = QButtonGroup(lm_frame)

        self.radio_think_on = QRadioButton("On", lm_frame)
        self.radio_think_on.setGeometry(240, 20, 40, 20)
        self.radio_think_on.setStyleSheet("color: #FFFFF;")
        self.radio_think_on.toggled.connect(lambda checked: setattr(self, 'thinking_enabled', True) if checked else None)
        self.thinking_group.addButton(self.radio_think_on, 0)

        self.radio_think_off = QRadioButton("Off", lm_frame)
        self.radio_think_off.setGeometry(280, 20, 45, 20)
        self.radio_think_off.setStyleSheet("color: #FFFFFF;")
        self.radio_think_off.toggled.connect(lambda checked: setattr(self, 'thinking_enabled', False) if checked else None)
        self.thinking_group.addButton(self.radio_think_off, 1)
        self.radio_think_off.setChecked(True)  # === Default: No Think ===
        
        prompt_label = QLabel("System Prompt", lm_frame)
        prompt_label.setGeometry(10, 64, 150, 20)
        prompt_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.prompt_text = QTextEdit(lm_frame)
        self.prompt_text.setGeometry(10, 86, 306, 100)
        self.prompt_text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # === Apply scrollbar style ===
        self.prompt_text.setStyleSheet("""
            QTextEdit {
                background-color: #121212;
                color: #FFFF96;
                border: 1px solid #FFFFFF;
                border-radius: 5px;
                font-family: Arial;
                font-size: 10pt;
            }
        """ + SCROLLBAR_STYLE)
        
       # === System Prompt === 
        
        self.prompt_text.setPlainText("Your name is Jarvis. You are a local AI assistant running on user's PC\nFirst you ask the user for his name, then continue the conversation using his/her name\n\nPERSONALITY:\n- Act natural, like with a close friend\n- Keep responses concise and on point\n- A little humor is welcome when appropriate\n\nLANGUAGE:\n- Always respond in the same language the user is speaking\n- If the user switches language mid-conversation, switch with them immediately\n\nSPEECH TO TEXT AWARENESS:\n- The user interacts with you via microphone\n- If something seems misspelled or unclear, use context to figure out what the user meant\n- Never point out transcription mistakes to the user\n\nTEXT TO SPEECH:\n- You talk to the user thru a TTS system with the voice of Jarvis\n- DO NOT USE ANY special characters or emoji otherwise you may sound unnatural\n\nMEMORY & CONTEXT:\n- You have access to conversation history and user context via RAG\n- Use this context naturally and don't announce that you're using it\n\nMCP TOOL USE:\n- When the user activates tool use mode, you will receive the available tools and their JSON schema dynamically\n- You detect when you are in tool use mode when user ask you to take an action that may match any possible combination of tools from the MCP server\n- In tool use mode, respond ONLY with valid JSON, no extra text, no explanations\n- In tool use mode you DON'T output commands that may affect the integrity of the data on user's machine UNLESS explicitly asked\n- In normal conversation mode, never output raw JSON\n\nBOUNDARIES:\n- You refuse any request that involves harming people or property\n- You refuse to engage in explicit sexual conversations\n- Do so briefly and respectfully, without lecturing\n")
        
        save_prompt_btn = QPushButton("Save Prompt", lm_frame)
        save_prompt_btn.setGeometry(217, 312, 100, 20)
        save_prompt_btn.setStyleSheet(button_style)
        save_prompt_btn.clicked.connect(self.save_prompt)
        
        load_prompt_btn = QPushButton("Load Prompt", lm_frame)
        load_prompt_btn.setGeometry(112, 312, 100, 20)
        load_prompt_btn.setStyleSheet(button_style)
        load_prompt_btn.clicked.connect(self.load_prompt)
        
        wake_word_label = QLabel("Wake Word", lm_frame)
        wake_word_label.setGeometry(28, 284, 80, 20)
        wake_word_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.wake_word_entry = QLineEdit(lm_frame)
        self.wake_word_entry.setGeometry(114, 286, 45, 19)
        self.wake_word_entry.setText(self.wake_word)
        self.wake_word_entry.setStyleSheet("""
            QLineEdit {
                background-color: #121212;
                color: #FFFF96;
                border: 1px solid #FFFFFF;
                border-radius: 3px;
            }
        """)
        self.wake_word_entry.textChanged.connect(lambda text: setattr(self, 'wake_word', text))
        
        self.wake_word_group = QButtonGroup(lm_frame)
        
        radio_wake_on = QRadioButton("On", lm_frame)
        radio_wake_on.setGeometry(16, 313, 40, 20)
        radio_wake_on.setStyleSheet("color: #FFFFFF;")
        radio_wake_on.setChecked(self.wake_word_enabled)
        radio_wake_on.toggled.connect(lambda checked: setattr(self, 'wake_word_enabled', True) if checked else None)
        self.wake_word_group.addButton(radio_wake_on, 0)
        
        radio_wake_off = QRadioButton("Off", lm_frame)
        radio_wake_off.setGeometry(58, 313, 40, 20)
        radio_wake_off.setStyleSheet("color: #FFFFFF;")
        radio_wake_off.toggled.connect(lambda checked: setattr(self, 'wake_word_enabled', False) if checked else None)
        self.wake_word_group.addButton(radio_wake_off, 1)
        radio_wake_off.setChecked(not self.wake_word_enabled)  # === Set as OFF if wake_word_enabled is False ===
        
        max_tokens_label = QLabel("Max Tokens", lm_frame)
        max_tokens_label.setGeometry(185, 284, 80, 20)
        max_tokens_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.max_tokens_entry = QLineEdit(lm_frame)
        self.max_tokens_entry.setGeometry(270, 286, 45, 19)
        self.max_tokens_entry.setText(str(self.max_tokens))
        self.max_tokens_entry.setStyleSheet("""
            QLineEdit {
                background-color: #121212;
                color: #FFFF96;
                border: 1px solid #FFFFFF;
                border-radius: 3px;
            }
        """)
        self.max_tokens_entry.textChanged.connect(lambda text: setattr(self, 'max_tokens', int(text)) if text.isdigit() else None)
        
        temperature_label = QLabel("Temperature", lm_frame)
        temperature_label.setGeometry(25, 188, 90, 20)
        temperature_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.temperature_slider = QSlider(Qt.Horizontal, lm_frame)
        self.temperature_slider.setGeometry(115, 190, 160, 20)
        self.temperature_slider.setRange(0, 100)
        self.temperature_slider.setValue(int(self.temperature * 100))
        self.temperature_slider.setStyleSheet(slider_style)
        self.temperature_slider.valueChanged.connect(self.update_temperature_label)
        self.connect_dirty_flag(self.temperature_slider)
        
        self.temperature_value_label = QLabel(f"{self.temperature:.2f}", lm_frame)
        self.temperature_value_label.setGeometry(290, 188, 50, 20)
        self.temperature_value_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        top_k_label = QLabel("Top K Sampling", lm_frame)
        top_k_label.setGeometry(20, 260, 100, 20)
        top_k_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.top_k_entry = QLineEdit(lm_frame)
        self.top_k_entry.setGeometry(114, 262, 45, 19)
        self.top_k_entry.setText(str(self.top_k))
        self.top_k_entry.setStyleSheet("""
            QLineEdit {
                background-color: #121212;
                color: #FFFF96;
                border: 1px solid #FFFFFF;
                border-radius: 3px;
            }
        """)
        self.top_k_entry.textChanged.connect(lambda text: setattr(self, 'top_k', int(text)) if text.isdigit() else None)
        
        repetition_penalty_label = QLabel("Repeat Penalty", lm_frame)
        repetition_penalty_label.setGeometry(177, 260, 100, 20)
        repetition_penalty_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.repetition_penalty_entry = QLineEdit(lm_frame)
        self.repetition_penalty_entry.setGeometry(270, 262, 45, 19)
        self.repetition_penalty_entry.setText(str(self.repetition_penalty))
        self.repetition_penalty_entry.setStyleSheet("""
            QLineEdit {
                background-color: #121212;
                color: #FFFF96;
                border: 1px solid #FFFFFF;
                border-radius: 3px;
            }
        """)
        self.repetition_penalty_entry.textChanged.connect(lambda text: setattr(self, 'repetition_penalty', float(text)) if re.match(r'^\d*\.?\d*$', text) else None)
        
        min_p_label = QLabel("Min P Sampling", lm_frame)
        min_p_label.setGeometry(22, 234, 100, 20)
        min_p_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.min_p_slider = QSlider(Qt.Horizontal, lm_frame)
        self.min_p_slider.setGeometry(115, 238, 160, 20)
        self.min_p_slider.setRange(0, 100)
        self.min_p_slider.setValue(int(self.min_p * 100))
        self.min_p_slider.setStyleSheet(slider_style)
        self.min_p_slider.valueChanged.connect(self.update_min_p_label)
        self.connect_dirty_flag(self.min_p_slider)
        
        self.min_p_value_label = QLabel(f"{self.min_p:.2f}", lm_frame)
        self.min_p_value_label.setGeometry(290, 234, 50, 20)
        self.min_p_value_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        top_p_label = QLabel("Top P Sampling", lm_frame)
        top_p_label.setGeometry(20, 212, 100, 20)
        top_p_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        self.top_p_slider = QSlider(Qt.Horizontal, lm_frame)
        self.top_p_slider.setGeometry(115, 214, 160, 20)
        self.top_p_slider.setRange(0, 100)
        self.top_p_slider.setValue(int(self.top_p * 100))
        self.top_p_slider.setStyleSheet(slider_style)
        self.top_p_slider.valueChanged.connect(self.update_top_p_label)
        self.connect_dirty_flag(self.top_p_slider)
        
        self.top_p_value_label = QLabel(f"{self.top_p:.2f}", lm_frame)
        self.top_p_value_label.setGeometry(290, 212, 50, 20)
        self.top_p_value_label.setStyleSheet("color: #FFFFFF; border: none;")
        
        # ====== SYSTEM SETTINGS ======
        system_frame = QGroupBox("System Settings", self)
        system_frame.setGeometry(994, 326, 326, 330)
        system_frame.setStyleSheet(group_style)

        # === About button ===
        about_btn = QPushButton("About...", system_frame)
        about_btn.setGeometry(217, 23, 100, 20)
        about_btn.setStyleSheet(button_style)
        about_btn.clicked.connect(self.show_about)

        # === LM Studio launch button ===
        open_lmstudio_btn = QPushButton("LM Studio", system_frame)
        open_lmstudio_btn.setGeometry(217, 214, 100, 20)
        open_lmstudio_btn.setStyleSheet(button_style)
        open_lmstudio_btn.clicked.connect(self.open_lm_studio)

        # === MCP Settings button ===
        open_mcp_gui_btn = QPushButton("MCP Settings", system_frame)
        open_mcp_gui_btn.setGeometry(217, 252, 100, 20)
        open_mcp_gui_btn.setStyleSheet(button_style)
        open_mcp_gui_btn.clicked.connect(self.open_mcp_gui)
        
        # === Resource Monitor ===
        resource_frame = QGroupBox(system_frame)
        resource_frame.setGeometry(44, 133, 166, 62) 
        resource_frame.setStyleSheet("QGroupBox { border: 1px solid #FFFFFF; border-radius: 5px; background-color: #121212; }")
        resource_frame.setTitle("")

        # == Row 1: CPU și SRAM % ==
        self.cpu_sram_label = QLabel("CPU: 00.0%   SRAM: 00.0%", resource_frame)
        self.cpu_sram_label.setGeometry(6, 15, 280, 20)
        self.cpu_sram_label.setStyleSheet("color: #FFFFFF; border: none;")

        # == Row 2: GPU și VRAM % ==
        self.gpu_vram_label = QLabel("GPU: 00.0%   VRAM: 00.0%", resource_frame)
        self.gpu_vram_label.setGeometry(6, 28, 280, 20)
        self.gpu_vram_label.setStyleSheet("color: #FFFFFF; border: none;")

        # == Row 3: Total SRAM și VRAM în GB ==
        self.total_label = QLabel("SRAM: 0.0 GB   VRAM: 0.0 GB", resource_frame)
        self.total_label.setGeometry(6, 40, 280, 20)
        self.total_label.setStyleSheet("color: #FFFFFF; border: none;")

        # === Load images ===
        sys_label = QLabel(system_frame)
        sys_label.setGeometry(7, 163, 32, 32)
        sys_pixmap = QPixmap(os.path.join(GRAPHICS_DIR, "Graph.png"))
        if not sys_pixmap.isNull():
            sys_label.setPixmap(sys_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        lms_label = QLabel(system_frame)
        lms_label.setGeometry(7, 202, 32, 32)
        lms_pixmap = QPixmap(os.path.join(GRAPHICS_DIR, "LMS.png"))
        if not lms_pixmap.isNull():
            lms_label.setPixmap(lms_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        
        mcp_label = QLabel(system_frame)
        mcp_label.setGeometry(7, 240, 32, 32)
        mcp_pixmap = QPixmap(os.path.join(GRAPHICS_DIR, "MCP.png"))
        if not mcp_pixmap.isNull():
            mcp_label.setPixmap(mcp_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        
        save_settings_btn = QPushButton("Save Profile", system_frame)
        save_settings_btn.setGeometry(217, 277, 100, 20)
        save_settings_btn.setStyleSheet(button_style)
        save_settings_btn.clicked.connect(self.save_settings)
        
        load_settings_btn = QPushButton("Load Profile", system_frame)
        load_settings_btn.setGeometry(112, 277, 100, 20)
        load_settings_btn.setStyleSheet(button_style)
        load_settings_btn.clicked.connect(self.load_settings)
        
        reset_settings_btn = QPushButton("Reset Profile", system_frame)
        reset_settings_btn.setGeometry(7, 277, 100, 20)
        reset_settings_btn.setStyleSheet(button_style)
        reset_settings_btn.clicked.connect(self.load_default_settings)
        
        self.start_stop_button = QPushButton("Start", system_frame)
        self.start_stop_button.setGeometry(7, 302, 311, 20)
        self.start_stop_button.setStyleSheet("""
            QPushButton {
                background-color: #00FF00;
                color: #000000;
                border-radius: 10px;
                font-weight: bold;
                font-size: 11pt;
                padding: 0px;
            }
        """)
        self.start_stop_button.clicked.connect(self.toggle_recording)
        
        # === Profile Image Frame (64x64) ===
        self.profile_image_label = ProfileFrame(system_frame)
        self.profile_image_label.setGeometry(234, 48, 64, 64)

        # === Profile Name Label ===
        self.profile_name_label = QLabel("", system_frame)
        self.profile_name_label.setGeometry(192, 108, 148, 20)
        self.profile_name_label.setStyleSheet("color: #FFFF96; border: none; font-weight: bold; font-size: 10pt;")
        self.profile_name_label.setAlignment(Qt.AlignCenter)

        sys_mon_label = QLabel("= System Monitor =", system_frame)
        sys_mon_label.setGeometry(66, 128, 150, 20)
        sys_mon_label.setStyleSheet("color: #FFFFFF; border: none; font-weight: bold;")

        lm_server_label = QLabel("= LM Studio =", system_frame)
        lm_server_label.setGeometry(85, 197, 150, 20)
        lm_server_label.setStyleSheet("color: #FFFFFF; border: none; font-weight: bold;")
        
        self.lm_server_entry = QLineEdit(system_frame)
        self.lm_server_entry.setGeometry(44, 214, 166, 20)
        self.lm_server_entry.setText(self.lm_server)
        self.lm_server_entry.setStyleSheet("""
            QLineEdit {
                background-color: #121212;
                color: #00FF00;
                border: 1px solid #FFFFFF;
                border-radius: 3px;
            }
        """)
        self.lm_server_entry.textChanged.connect(lambda text: setattr(self, 'lm_server', text))
        
        mcp_server_label = QLabel("= MCP Server =", system_frame)
        mcp_server_label.setGeometry(80, 235, 150, 20)
        mcp_server_label.setStyleSheet("color: #FFFFFF; border: none; font-weight: bold;")
        
        self.mcp_server_entry = QLineEdit(system_frame)
        self.mcp_server_entry.setGeometry(44, 252, 166, 20)
        self.mcp_server_entry.setText(self.mcp_server)
        self.mcp_server_entry.setStyleSheet("""
            QLineEdit {
                background-color: #121212;
                color: #00FF00;
                border: 1px solid #FFFFFF;
                border-radius: 3px;
            }
        """)
        self.mcp_server_entry.textChanged.connect(lambda text: setattr(self, 'mcp_server', text))
        
        use_mcp_label = QLabel("MCP Server", system_frame)
        use_mcp_label.setGeometry(230, 161, 100, 20)
        use_mcp_label.setStyleSheet("color: #FFFFFF; border: none; font-weight: bold; font-size: 9pt;")
        
        self.mcp_group = QButtonGroup(system_frame)
        
        radio_mcp_yes = QRadioButton("On", system_frame)
        radio_mcp_yes.setGeometry(227, 180, 40, 20)
        radio_mcp_yes.setStyleSheet("color: #FFFFFF;")
        radio_mcp_yes.toggled.connect(lambda checked: self.update_system_prompt_with_mcp(checked))
        self.mcp_group.addButton(radio_mcp_yes, 0)
        
        radio_mcp_no = QRadioButton("Off", system_frame)
        radio_mcp_no.setGeometry(269, 180, 40, 20)
        radio_mcp_no.setStyleSheet("color: #FFFFFF;")
        radio_mcp_no.setChecked(True)
        self.mcp_group.addButton(radio_mcp_no, 1)
        
        real_talk_label = QLabel("Real Talk 🎧", system_frame)
        real_talk_label.setGeometry(230, 128, 80, 20)
        real_talk_label.setStyleSheet("color: #FFFFFF; border: none; font-weight: bold; font-size: 9pt;")
        
        self.real_talk_group = QButtonGroup(system_frame)
        
        radio_real_talk_yes = QRadioButton("On", system_frame)
        radio_real_talk_yes.setGeometry(227, 144, 40, 20)
        radio_real_talk_yes.setStyleSheet("color: #FFFFFF;")
        radio_real_talk_yes.toggled.connect(lambda checked: setattr(self, 'real_talk_enabled', True) if checked else None)
        self.real_talk_group.addButton(radio_real_talk_yes, 0)
        
        radio_real_talk_no = QRadioButton("Off", system_frame)
        radio_real_talk_no.setGeometry(269, 144, 40, 20)
        radio_real_talk_no.setStyleSheet("color: #FFFFFF;")
        radio_real_talk_no.setChecked(True)
        radio_real_talk_no.toggled.connect(lambda checked: setattr(self, 'real_talk_enabled', False) if checked else None)
        self.real_talk_group.addButton(radio_real_talk_no, 1)
        # === Centralized dirty flag connections ===
        # === Text fields ===
        self.wake_word_entry.textChanged.connect(self._mark_modified)
        self.max_tokens_entry.textChanged.connect(self._mark_modified)
        self.top_k_entry.textChanged.connect(self._mark_modified)
        self.repetition_penalty_entry.textChanged.connect(self._mark_modified)
        self.lm_server_entry.textChanged.connect(self._mark_modified)
        self.mcp_server_entry.textChanged.connect(self._mark_modified)
        # === Radio groups ===
        for radio in self.whisper_lang_group.buttons():
            radio.toggled.connect(self._mark_modified)
        for radio in self.whisper_device_group.buttons():
            radio.toggled.connect(self._mark_modified)
        for radio in self.whisper_model_group.buttons():
            radio.toggled.connect(self._mark_modified)
        for radio in self.vad_device_group.buttons():
            radio.toggled.connect(self._mark_modified)
        for radio in self.coqui_device_group.buttons():
            radio.toggled.connect(self._mark_modified)
        for radio in self.wake_word_group.buttons():
            radio.toggled.connect(self._mark_modified)
        for radio in self.mcp_group.buttons():
            radio.toggled.connect(self._mark_modified)
        for radio in self.real_talk_group.buttons():
            radio.toggled.connect(self._mark_modified)
        for radio in self.rag_group.buttons():
            radio.toggled.connect(self._mark_modified)

    def update_resources(self, cpu_percent, sram_percent, sram_total_gb,
                         gpu_util, vram_percent, vram_total_gb):
        """
        GUI slot — receives pre-computed metrics from SystemMonitorWorker via signal.
        Runs on GUI thread, only updates labels. No blocking calls here.
        gpu_util / vram_percent / vram_total_gb == -1.0 means N/A
        """
        try:
            # ====== CPU & SRAM ======
            cpu_str   = f"{cpu_percent:05.1f}%" if cpu_percent < 100 else "100%"
            sram_str  = f"{sram_percent:05.1f}%" if sram_percent < 100 else "100%"
            cpu_color  = self.get_usage_color(cpu_percent)
            sram_color = self.get_usage_color(sram_percent)

            self.cpu_sram_label.setText(
                f'CPU: <span style="color:{cpu_color};">{cpu_str}</span>   '
                f'SRAM: <span style="color:{sram_color};">{sram_str}</span>'
            )

            # ====== GPU & VRAM ======
            if gpu_util >= 0:
                gpu_util_str      = f"{gpu_util:05.1f}%"  if gpu_util     < 100 else "100%"
                vram_percent_str  = f"{vram_percent:05.1f}%" if vram_percent < 100 else "100%"
                gpu_color         = self.get_usage_color(gpu_util)
                vram_color        = self.get_usage_color(vram_percent)
            else:
                gpu_util_str     = "N/A"
                vram_percent_str = "N/A"
                gpu_color        = "#FFFFFF"
                vram_color       = "#FFFFFF"

            self.gpu_vram_label.setText(
                f'GPU: <span style="color:{gpu_color};">{gpu_util_str}</span>   '
                f'VRAM: <span style="color:{vram_color};">{vram_percent_str}</span>'
            )

            # ====== Total Memory ======
            vram_gb_str = f"{vram_total_gb:.1f} GB" if vram_total_gb >= 0 else "N/A"
            self.total_label.setText(
                f"SRAM: {sram_total_gb:.1f} GB   VRAM: {vram_gb_str}"
            )

        except Exception as e:
            logging.error(f"Error updating resources: {str(e)}")

    def get_usage_color(self, percent): # === Returns the color based on percentage ===
        if percent < 70:
            return "#00FF00"  # Green - Safe Zone
        elif percent < 90:
            return "#FFFF00"  # Yellow - Attention
        else:
            return "#FF0000"  # Red - Danger!

    def update_mic_volume_label(self, value):
        self.mic_volume = value
        self.mic_volume_value_label.setText(str(value))

    def update_volume_label(self, value):
        self.volume_level = value
        self.volume_value_label.setText(str(value))

    def update_threshold_label(self, value):
        self.vad_threshold = value / 100.0
        self.threshold_value_label.setText(f"{self.vad_threshold:.2f}")

    def update_min_speech_label(self, value):
        self.vad_min_speech_duration = value / 10.0
        self.min_speech_value_label.setText(f"{self.vad_min_speech_duration:.1f}")

    def update_min_silence_label(self, value):
        self.vad_min_silence_duration = value / 10.0
        self.min_silence_value_label.setText(f"{self.vad_min_silence_duration:.1f}")

    def update_coqui_temperature_label(self, value):
        self.coqui_temperature = value / 100.0
        self.coqui_temperature_value_label.setText(f"{self.coqui_temperature:.2f}")

    def update_coqui_top_p_label(self, value):
        self.coqui_top_p = value / 100.0
        self.coqui_top_p_value_label.setText(f"{self.coqui_top_p:.2f}")

    def update_coqui_top_k_label(self, value):
        self.coqui_top_k = value
        self.coqui_top_k_value_label.setText(str(value))

    def update_coqui_speed_label(self, value):
        self.coqui_speed = value / 10.0
        self.coqui_speed_value_label.setText(f"{self.coqui_speed:.1f}")

    def update_coqui_chunk_size_label(self, value):
        self.coqui_stream_chunk_size = value
        self.coqui_chunk_size_value_label.setText(str(value))

    def update_temperature_label(self, value):
        self.temperature = value / 100.0
        self.temperature_value_label.setText(f"{self.temperature:.2f}")

    def update_min_p_label(self, value):
        self.min_p = value / 100.0
        self.min_p_value_label.setText(f"{self.min_p:.2f}")

    def update_top_p_label(self, value):
        self.top_p = value / 100.0
        self.top_p_value_label.setText(f"{self.top_p:.2f}")

    def update_coqui_sample(self, text):
        self.tts.selected_coqui_sample = text
        self.tts.invalidate_latents()
        logging.info(f"Coqui sample changed to: {text} (Cache cleared)")

    def on_device_change(self, device_type, device):
        if device_type == "whisper":
            self.whisper_device = device
            self.audio.current_whisper_device = device
        elif device_type == "vad":
            self.vad_device = device
            self.current_vad_device = device
            self.audio.init_silero_vad()
        elif device_type == "coqui":
            self.tts.coqui_device = device
            self.current_coqui_device = device
            self.tts.invalidate_latents()

    def setup_debug_logging(self):
        self.log_emitter = LogEmitter()
        self.log_emitter.log_signal.connect(self.append_debug_log)
        handler = TextHandler(self.debug_text, self.log_emitter)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logging.getLogger().addHandler(handler)

    def append_debug_log(self, msg, level):
        colors = {
            "WARNING": "#FF00FF",  # Magenta
            "ERROR": "#FF0000",    # Red
            "CRITICAL": "#FF0000", # Red
            "DEBUG": "#FFFF00",    # Yellow
            "INFO": "#A5A5A5"      # Gray
        }
        color = colors.get(level, "#A5A5A5")
        cursor = self.debug_text.textCursor()
        cursor.movePosition(cursor.End)
        self.debug_text.setTextCursor(cursor)
        self.debug_text.setTextColor(QColor(color))
        self.debug_text.insertPlainText(msg + "\n")
        self.debug_text.verticalScrollBar().setValue(self.debug_text.verticalScrollBar().maximum())

    def _append_chat_safe(self, role, text, color):
        """Slot — always runs on main thread via signal. Safe to touch GUI widgets."""
        self.chat_text.setTextColor(QColor(color))
        self.chat_text.append(f"{role}: {text}\n")
        cursor = self.chat_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_text.setTextCursor(cursor)
        self.chat_text.verticalScrollBar().setValue(self.chat_text.verticalScrollBar().maximum())

    def stop_tts_stream(self):
        self.tts.stop_playback()
        QApplication.processEvents()

    def _get_tts_output_device_index(self):
        # === Returns output device index for TTSEngine ===
        try:
            output_device_str = self.output_device_dropdown.currentText()
            if "No output" in output_device_str:
                return None
            return int(output_device_str.split(":")[0])
        except:
            return None

    def _get_llm_config(self):
        # === Returns current LLM/MCP config dict for LLMClient ===
        return {
            "model":              self.selected_lm_model,
            "lm_server":          self.lm_server,
            "mcp_server":         self.mcp_server,
            "temperature":        self.temperature,
            "max_tokens":         self.max_tokens,
            "top_k":              self.top_k,
            "top_p":              self.top_p,
            "min_p":              self.min_p,
            "repetition_penalty": self.repetition_penalty,
            "thinking_enabled":   self.thinking_enabled,
            "rag_memory_enabled": self.rag_memory_enabled,
            "mcp_max_iterations": self.mcp_max_iterations,
        }

    def _load_audio_devices(self):
        # === Load mics and output devices via AudioProcessor ===
        mics, outputs = self.audio.load_devices()
        if hasattr(self, 'mic_dropdown'):
            self.mic_dropdown.clear()
            self.mic_dropdown.addItems(mics if mics else ["No microphones found"])
        if hasattr(self, 'output_device_dropdown'):
            self.output_device_dropdown.clear()
            self.output_device_dropdown.addItems(outputs if outputs else ["No output devices found"])

    def _get_rag_config(self):
        # === Returns RAG config dict for RAGManager ===
        return {
            "rag_memory_enabled": self.rag_memory_enabled,
            "current_rag_dir":    self.current_rag_dir,
        }

    def _get_audio_config(self):
        # === Returns current audio/STT config dict for AudioProcessor ===
        return {
            "vad_device":              self.vad_device,
            "vad_threshold":           self.vad_threshold,
            "vad_min_speech_duration": self.vad_min_speech_duration,
            "vad_min_silence_duration":self.vad_min_silence_duration,
            "mic_volume":              self.mic_volume,
            "whisper_model":           self.whisper_model,
            "whisper_device":          self.whisper_device,
            "whisper_language":        self.whisper_language,
        }

    def _on_mcp_connected(self, mcp_system_prompt):
        # === Called by LLMClient after successful MCP connection — updates GUI prompt_text ===
        if not mcp_system_prompt:
            return
        current_text = self.prompt_text.toPlainText()
        if "TOOL DEFINITIONS:" in current_text:
            return
        new_text = current_text.strip() + "\n\n" + mcp_system_prompt
        self.prompt_text.setPlainText(new_text)
        logging.info("MCP prompt added to UI")

    def toggle_recording(self):
        try:
            selected_mic = self.mic_dropdown.currentText()
            if "No microphones" in selected_mic:
                QMessageBox.critical(self, "Error", "Select a valid microphone!")
                return
            device_index = int(selected_mic.split(":")[0])
        except:
            QMessageBox.critical(self, "Error", "Select a valid microphone!")
            return
        if not self.is_recording:
            self.is_recording = True
            self.audio_thread = self.audio.start(device_index)
            self.start_stop_button.setText("Stop")
            self.start_stop_button.setStyleSheet("""
                QPushButton {
                    background-color: #FF0000;
                    color: #FFFFFF;
                    border-radius: 10px;
                    font-weight: bold;
                    font-size: 11pt;
                    padding: 0px;
                }
            """)
            logging.info("Recording started.")
        else:
            self.is_recording = False
            self.audio.stop()
            self.stop_tts_stream() 
            logging.info("Stopping recording...")

            def check_thread():
                if self.audio_thread and self.audio_thread.is_alive():
                    QTimer.singleShot(100, check_thread)
                else:
                    self.audio.cleanup()
                    self.audio_thread = None
                    logging.info("Audio thread stopped.")
                    self.start_stop_button.setText("Start")
                    self.start_stop_button.setStyleSheet("""
                        QPushButton {
                            background-color: #00FF00;
                            color: #000000;
                            border-radius: 10px;
                            font-weight: bold;
                            font-size: 11pt;
                            padding: 0px;
                        }
                    """)
                    self.vu_input_signal.emit(0)
                    self.vu_output_signal.emit(0)

            check_thread()

    def process_audio_segment(self, frames):
        try:
            audio_bytes = b''.join(frames)
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            transcription = self.audio.transcribe_audio(audio_array)

            if not transcription:
                return

            logging.info(f"Transcription: {transcription}")

            should_process    = False
            prompt_to_process = ""

            if not self.wake_word_enabled:
                should_process    = True
                prompt_to_process = transcription
                self.append_log("User", transcription)
            else:
                wake_word_str       = self.wake_word.strip().lower()
                transcription_lower = transcription.lower()
                if wake_word_str and wake_word_str in transcription_lower:
                    wake_index        = transcription_lower.index(wake_word_str)
                    prompt_to_process = transcription[wake_index:]
                    logging.info(f"Wake word detected: {prompt_to_process}")
                    self.append_log("User", prompt_to_process)
                    should_process = True
                else:
                    logging.info("Wake word not detected.")

            if should_process:
                initial_response = self.llm.query(prompt_to_process)
                if not initial_response:
                    return

                # === FORK: Simple Chat vs MCP workflow ===
                tool_calls = self.llm.parse_tool_calls(initial_response)

                if tool_calls and self.use_mcp_server:
                    logging.info("🔗 MCP workflow detected")
                    final_response_text = self.llm.mcp_chain_executor(prompt_to_process, initial_response)
                else:
                    logging.info("💬 Simple chat mode")
                    final_response_text = self.llm.extract_text_response(initial_response)

                if final_response_text:
                    logging.info(f"Assistant: {final_response_text}")
                    self.append_log("Assistant", final_response_text)

                    completion_event = threading.Event()
                    self.tts.speak(final_response_text, completion_event)

                    if not self.real_talk_enabled:
                        # === Wait for confirmed TTS completion from playback thread ===
                        completed = completion_event.wait(timeout=50)
                        if not completed:
                            logging.warning("TTS completion timeout!")

                        # === Safety margin for hardware audio subsystem ===
                        time.sleep(0.18)

                        # === Resume mic only after TTS fully finished ===
                        if self.audio.recording_paused:
                            self.audio.recording_paused = False
                            self.audio.resume_event.set()
                            logging.info("Microphone resumed after full TTS playback.")

        except Exception as e:
            logging.error(f"Error in process_audio_segment: {str(e)}")
        finally:
            # === Safety fallback — mic resumes even if an error occurred ===
            if not self.real_talk_enabled and self.audio.recording_paused:
                self.audio.resume_mic()

    def send_manual_query(self):
        """
        === Handles manual text input from chat input field ===
        === Routes through same pipeline as voice input ===
        """
        text = self.chat_input.toPlainText().strip()
        if not text:
            return

        # === Clear input field ===
        self.chat_input.clear()

        # === Route through same pipeline as voice ===
        logging.info(f"Manual input: {text}")
        self.append_log("User", text)

        # === Process in separate thread to avoid GUI freeze ===
        thread = threading.Thread(
            target=self._process_manual_query_thread,
            args=(text,),
            daemon=True
        )
        thread.start()

    def _process_manual_query_thread(self, text):
        """
        === Background thread for manual query processing ===
        === Wake word is bypassed — typing is already an intentional action ===
        """
        try:
            # === Manual input always bypasses wake word ===
            prompt_to_process = text

            initial_response = self.llm.query(prompt_to_process)
            if not initial_response:
                return

            tool_calls = self.llm.parse_tool_calls(initial_response)

            if tool_calls and self.use_mcp_server:
                logging.info("🔗 MCP workflow detected")
                final_response_text = self.llm.mcp_chain_executor(prompt_to_process, initial_response)
            else:
                logging.info("💬 Simple chat mode")
                final_response_text = self.llm.extract_text_response(initial_response)

            if final_response_text:
                logging.info(f"Assistant: {final_response_text}")
                self.append_log("Assistant", final_response_text)
                self.tts.speak(final_response_text, None)

        except Exception as e:
            logging.error(f"Error in manual query: {str(e)}")

    def switch_profile_paths(self, profile_name):
        """
        Switches the active Chat History file and RAG Database folder.
        Always requires a profile name — no more generic mode.
        """
        self.current_profile_name = profile_name
        self.current_chat_log     = self.profiles.get_chat_log_path(profile_name)
        self.current_rag_dir      = self.profiles.ensure_profile_directories(profile_name)
        logging.info(f"Profile paths switched → '{profile_name}'")

        self.update_profile_display(profile_name)

    def update_profile_display(self, profile_name):
        """
        Updates profile image (120x120 ProfileFrame) and name label.
        Looks for Graphics/<profile_name>.png — falls back to Graphics/Profile.png.
        """
        try:
            self.profile_name_label.setText(profile_name)

            img_path = os.path.join(GRAPHICS_DIR, f"{profile_name}.png")
            pixmap = QPixmap(img_path)
            if not pixmap.isNull():
                self.profile_image_label.set_pixmap(pixmap)
            else:
                # === Fallback to default profile image ===
                default_path = os.path.join(GRAPHICS_DIR, "Profile.png")
                default_pixmap = QPixmap(default_path)
                if not default_pixmap.isNull():
                    self.profile_image_label.set_pixmap(default_pixmap)
                else:
                    self.profile_image_label.set_pixmap(None)
                    logging.warning("⚠️ Profile.png not found in Graphics folder")
        except Exception as e:
            logging.error(f"update_profile_display error: {e}")

    def connect_dirty_flag(self, widget, signal_name="valueChanged"):
        """
        Helper — connects any widget signal to dirty flag.
        Avoids ugly lambdas in create_gui().
        """
        try:
            signal = getattr(widget, signal_name)
            signal.connect(self._mark_modified)
        except AttributeError:
            logging.warning(f"⚠️ Could not connect dirty flag on {widget.__class__.__name__}")

    def _mark_modified(self):
        """Sets dirty flag (simple and clean)"""
        self.profile_modified = True

    def _ask_save_if_modified(self):
        """
        If unsaved changes exist, shows a dialog asking whether to save.
        - Jarvis → offers Save As to a new profile
        - Any other profile → offers to save in place
        Returns:
            True  — caller can proceed (saved, or chose not to save)
            False — caller must abort (user clicked Cancel)
        """
        if not self.profile_modified:
            return True

        if self.current_profile_name == "Jarvis":
            # === Jarvis is hardcoded — offer Save As to new profile ===
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have modified the default Jarvis profile.\nSave changes to a new profile?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Yes:
                while True:
                    file_path, _ = QFileDialog.getSaveFileName(
                        self, "Save Profile As", SETTINGS_DIR, "JSON Files (*.json)"
                    )
                    if not file_path:
                        break  # user cancelled dialog
                    if not self._validate_profile_name(file_path):
                        continue  # reserved name → re-open dialog
                    try:
                        settings_dict = self._build_settings_dict()
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(settings_dict, f, indent=2, ensure_ascii=False)
                        new_name = os.path.splitext(os.path.basename(file_path))[0]
                        self.profile_modified = False
                        logging.info(f"✅ Jarvis changes saved as '{new_name}'")
                    except Exception as e:
                        logging.error(f"❌ Save As failed: {e}")
                    break
                return True
            elif reply == QMessageBox.No:
                self.profile_modified = False
                return True
            else:  # Cancel
                return False

        else:
            # === Named profile — save in place ===
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"Save changes to profile '{self.current_profile_name}'?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Yes:
                self.save_settings()
                return True
            elif reply == QMessageBox.No:
                self.profile_modified = False
                return True
            else:  # Cancel
                return False

    def ensure_default_profile(self):
        """
        If no profile is active at startup, automatically creates
        and activates the default 'Jarvis' profile with default values.
        """
        if self.current_profile_name is not None:
            return  # === Profile already active, nothing to do ===

        # === Jarvis is always hardcoded — never read from or written to JSON ===
        self.switch_profile_paths("Jarvis")
        self.load_default_settings(silent=True)
        logging.info("✅ Active profile at startup: 'Jarvis' (hardcoded defaults)")

    def _apply_settings_to_gui(self, settings):
        """Applies a settings dictionary to the GUI. Used by both load_settings and ensure_default_profile."""
    
        if 'selected_mic' in settings:
            idx = self.mic_dropdown.findText(settings['selected_mic'])
            if idx >= 0: self.mic_dropdown.setCurrentIndex(idx)

        if 'selected_output_device' in settings:
            idx = self.output_device_dropdown.findText(settings['selected_output_device'])
            if idx >= 0: self.output_device_dropdown.setCurrentIndex(idx)

        if 'selected_lm_model' in settings:
            text = settings['selected_lm_model']
            # === Delay because the dropdown populates async after 500ms ===
            QTimer.singleShot(800, lambda t=text: (
                self.lm_model_dropdown.setCurrentIndex(self.lm_model_dropdown.findText(t))
                if self.lm_model_dropdown.findText(t) >= 0 else None
            ))

        if 'selected_coqui_sample' in settings:
            text = settings['selected_coqui_sample']
            self.update_coqui_sample(text)
            idx = self.coqui_dropdown.findText(text)
            if idx >= 0: self.coqui_dropdown.setCurrentIndex(idx)

        if 'volume_level' in settings:
            self.volume_level = int(settings['volume_level'])
            self.volume_slider.setValue(self.volume_level)
        if 'mic_volume' in settings:
            self.mic_volume = int(settings['mic_volume'])
            self.mic_volume_slider.setValue(self.mic_volume)
        if 'coqui_temperature' in settings:
            self.coqui_temperature = float(settings['coqui_temperature'])
            self.coqui_temperature_slider.setValue(int(self.coqui_temperature * 100))
        if 'coqui_top_p' in settings:
            self.coqui_top_p = float(settings['coqui_top_p'])
            self.coqui_top_p_slider.setValue(int(self.coqui_top_p * 100))
        if 'coqui_top_k' in settings:
            self.coqui_top_k = int(settings['coqui_top_k'])
            self.coqui_top_k_slider.setValue(self.coqui_top_k)
        if 'coqui_speed' in settings:
            self.coqui_speed = float(settings['coqui_speed'])
            self.coqui_speed_slider.setValue(int(self.coqui_speed * 10))
        if 'coqui_stream_chunk_size' in settings:
            self.coqui_stream_chunk_size = int(settings['coqui_stream_chunk_size'])
            self.coqui_stream_chunk_size_slider.setValue(self.coqui_stream_chunk_size)
        if 'vad_threshold' in settings:
            self.vad_threshold = float(settings['vad_threshold'])
            self.threshold_slider.setValue(int(self.vad_threshold * 100))
        if 'vad_min_speech_duration' in settings:
            self.vad_min_speech_duration = float(settings['vad_min_speech_duration'])
            self.min_speech_slider.setValue(int(self.vad_min_speech_duration * 10))
        if 'vad_min_silence_duration' in settings:
            self.vad_min_silence_duration = float(settings['vad_min_silence_duration'])
            self.min_silence_slider.setValue(int(self.vad_min_silence_duration * 10))

        if 'vad_device' in settings:
            self.vad_device = settings['vad_device']
            idx = 0 if self.vad_device == "cuda" else 1
            if self.vad_device_group.button(idx): self.vad_device_group.button(idx).setChecked(True)

        if 'whisper_language' in settings:
            self.whisper_language = settings['whisper_language']
            lang_map = {"auto": 0, "en": 1, "ro": 2}
            if self.whisper_language in lang_map:
                self.whisper_lang_group.button(lang_map[self.whisper_language]).setChecked(True)

        if 'whisper_device' in settings:
            self.whisper_device = settings['whisper_device']
            idx = 0 if self.whisper_device == "cuda" else 1
            if self.whisper_device_group.button(idx): self.whisper_device_group.button(idx).setChecked(True)

        if 'coqui_device' in settings:
            self.coqui_device = settings['coqui_device']
            idx = 0 if self.coqui_device == "cuda" else 1
            if self.coqui_device_group.button(idx): self.coqui_device_group.button(idx).setChecked(True)

        if 'wake_word' in settings:
            self.wake_word = settings['wake_word']
            self.wake_word_entry.setText(self.wake_word)

        if 'wake_word_enabled' in settings:
            self.wake_word_enabled = settings['wake_word_enabled'].lower() == 'true'
            idx = 0 if self.wake_word_enabled else 1
            if self.wake_word_group.button(idx): self.wake_word_group.button(idx).setChecked(True)

            # === Apply thinking setting ===
        if 'thinking_enabled' in settings:
            self.thinking_enabled = settings.get("thinking_enabled", False)
            self.radio_think_on.setChecked(self.thinking_enabled)
            self.radio_think_off.setChecked(not self.thinking_enabled)        
 
        if 'use_mcp_server' in settings:
            mcp_enabled = settings['use_mcp_server'].lower() == 'true'
            # === Always reset mcp_connected so init runs fresh on every profile load ===
            self.llm.mcp_connected = False
            # === Update radio button UI (block signals to avoid double-call) ===
            idx = 0 if mcp_enabled else 1
            btn = self.mcp_group.button(idx)
            if btn:
                btn.blockSignals(True)
                btn.setChecked(True)
                btn.blockSignals(False)
            # === Always call directly — toggled signal won't fire if state unchanged ===
            self.update_system_prompt_with_mcp(mcp_enabled)

        if 'real_talk_enabled' in settings:
            self.real_talk_enabled = settings['real_talk_enabled'].lower() == 'true'
            idx = 0 if self.real_talk_enabled else 1
            if self.real_talk_group.button(idx): self.real_talk_group.button(idx).setChecked(True)

        if 'rag_memory_enabled' in settings:
            self.rag_memory_enabled = settings['rag_memory_enabled'].lower() == 'true'
            idx = 0 if self.rag_memory_enabled else 1
            if self.rag_group.button(idx): self.rag_group.button(idx).setChecked(True)

        if 'whisper_model' in settings:
            self.whisper_model = settings['whisper_model']
            model_map = {"tiny": 0, "base": 1, "small": 2, "medium": 3, "large": 4}
            if self.whisper_model in model_map:
                self.whisper_model_group.button(model_map[self.whisper_model]).setChecked(True)

        if 'lm_server' in settings:
            self.lm_server = settings['lm_server']
            self.lm_server_entry.setText(self.lm_server)
        if 'mcp_server' in settings:
            self.mcp_server = settings['mcp_server']
            self.mcp_server_entry.setText(self.mcp_server)

        if 'temperature' in settings:
            self.temperature = float(settings['temperature'])
            self.temperature_slider.setValue(int(self.temperature * 100))
        if 'max_tokens' in settings:
            self.max_tokens = int(settings['max_tokens'])
            self.max_tokens_entry.setText(str(self.max_tokens))
        if 'top_k' in settings:
            self.top_k = int(settings['top_k'])
            self.top_k_entry.setText(str(self.top_k))
        if 'repetition_penalty' in settings:
            self.repetition_penalty = float(settings['repetition_penalty'])
            self.repetition_penalty_entry.setText(str(self.repetition_penalty))
        if 'min_p' in settings:
            self.min_p = float(settings['min_p'])
            self.min_p_slider.setValue(int(self.min_p * 100))
        if 'top_p' in settings:
            self.top_p = float(settings['top_p'])
            self.top_p_slider.setValue(int(self.top_p * 100))

        if 'prompt_text' in settings and settings['prompt_text'].strip():
            self.prompt_text.setPlainText(settings['prompt_text'])

    def load_lm_models(self):
        logging.info("Loading LM Studio models")

        models = self.llm.list_models(timeout=3)

        if models is None:
            # === Server not reachable — friendly warning, no error code ===
            lm_url = self.lm_server_entry.text().strip() or "http://127.0.0.1:1234"
            logging.warning(f"⚠️ Turn on LM Studio and open server on: {lm_url}")
            if self.lm_model_dropdown.count() == 0:
                self.lm_model_dropdown.addItem("No loaded models")
            return

        # === OPTIMAL REFRESH LOGIC ===
        current_selection = self.lm_model_dropdown.currentText()
        self.lm_model_dropdown.blockSignals(True)
        self.lm_model_dropdown.clear()

        if models:
            self.lm_model_dropdown.addItems(models)
            if current_selection in models:
                self.lm_model_dropdown.setCurrentText(current_selection)
            else:
                self.lm_model_dropdown.setCurrentIndex(0)
                self.selected_lm_model = models[0]
            logging.info(f"LM Studio models loaded: {models}")
        else:
            self.lm_model_dropdown.addItem("No loaded models")
            logging.warning("No loaded LM Studio models")

        self.lm_model_dropdown.blockSignals(False)

    def auto_refresh_lm_models(self):
        """Automatically refresh until it finds a model loaded in LM Studio"""
        def check():
            if self.lm_model_dropdown.count() > 0 and self.lm_model_dropdown.itemText(0) != "No loaded models":
                # === We have a model → we stop the timer ===
                return

            models = self.llm.list_models(timeout=2)

            if models:
                self.lm_model_dropdown.clear()
                self.lm_model_dropdown.addItems(models)
                self.selected_lm_model = models[0]
                logging.info(f"Model detectat automat: {models[0]}")
                # === We turn off the refresh once we find a model ===
                return

            # === Keeps checking every 4 seconds ===
            QTimer.singleShot(4000, check)

        # === Start the checker only if we don't already have a model ===
        if self.lm_model_dropdown.count() == 0 or "No loaded models" in self.lm_model_dropdown.itemText(0):
            QTimer.singleShot(500, check)  # === Starts before 0.5s on startup ===

    def append_log(self, role, text, visible=True):
        """
        Add message to chat history
    
        Args:
            role: "User", "Assistant", "MCP Request", "MCP Response"
            text: Message content
            visible: If False, do not display in UI (but it is saved and indexed)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.chat_history.append({
            "timestamp": timestamp,
            "role": role,
            "text": text,
            "visible": visible
        })
    
        # === Show in UI only if visible=True ===
        if visible:
            display_role = role
            color = "#00B200" if display_role == "User" else "#FFFF96"
            self.chat_update_signal.emit(display_role, text, color)  # === Thread-safe: never touch widget directly ===
    
        # === Save to file (ALWAYS) ===
        with open(self.current_chat_log, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} {role}: {text}\n\n")  # ← Dublu \n pentru rând gol
    
        # === RAG indexing (ALWAYS) ===
        if self.rag_memory_enabled:
            self.rag.index_message(role, text, timestamp)

    def show_about(self):
        """Shows the About dialog centered on screen"""
        dialog = QDialog(self)
        dialog.setWindowTitle("About...")
        dialog.setFixedSize(400, 300)
        dialog.setStyleSheet("background-color: #191919; color: #FFFFFF;")

        # === Center on screen ===
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - 400) // 2
        y = (screen.height() - 300) // 2
        dialog.move(x, y)

        # === Version ===
        version_label = QLabel("Version: 0.1.8 Beta", dialog)
        version_label.setGeometry(140, 2, 200, 20)
        version_label.setStyleSheet("color: #FFFF96; font-weight: bold; font-size: 10pt;")

        # === Author ===
        author_label = QLabel("Author: Nechifor Marian", dialog)
        author_label.setGeometry(138, 18, 250, 20)
        author_label.setStyleSheet("color: #FFFFFF; font-size: 9pt;")

        # === Copyright ===
        copyright_label = QLabel("Copyright: 2026 Nechifor Marian", dialog)
        copyright_label.setGeometry(115, 35, 250, 20)
        copyright_label.setStyleSheet("color: #AAAAAA; font-size: 9pt;")

        # === License text ===
        license_label = QLabel("This is a free software licensed under the GNU General Public License", dialog)
        license_label.setGeometry(30, 56, 380, 10)
        license_label.setStyleSheet("color: #AAAAAA; font-size: 8pt;")
        license_label.setWordWrap(True)

        # === License button ===
        license_btn = QPushButton("License", dialog)
        license_btn.setGeometry(166, 73, 75, 20)
        license_btn.setStyleSheet(self.button_style)
        license_btn.clicked.connect(self.show_license)

        # === Social Media label ===
        social_label = QLabel("Social Media", dialog)
        social_label.setGeometry(166, 99, 100, 15)
        social_label.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 9pt;")

        # === YouTube icon ===
        yt_label = QLabel(dialog)
        yt_label.setGeometry(75, 122, 32, 32)
        yt_pixmap = QPixmap(os.path.join(GRAPHICS_DIR, "YouTube.png"))
        if not yt_pixmap.isNull():
            yt_label.setPixmap(yt_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        yt_text = QLabel('<a href="https://www.youtube.com/@DIY_Engineering" style="color: #FFFF96; text-decoration: none;">YouTube</a>', dialog)
        yt_text.setGeometry(64, 157, 65, 15)
        yt_text.setStyleSheet("font-size: 9pt;")
        yt_text.setOpenExternalLinks(True)

        # === Instagram icon ===
        ig_label = QLabel(dialog)
        ig_label.setGeometry(190, 122, 32, 32)
        ig_pixmap = QPixmap(os.path.join(GRAPHICS_DIR, "Instagram.png"))
        if not ig_pixmap.isNull():
            ig_label.setPixmap(ig_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        ig_text = QLabel('<a href="https://www.instagram.com/diwhy_engineering/" style="color: #FFFF96; text-decoration: none;">Instagram</a>', dialog)
        ig_text.setGeometry(178, 157, 70, 15)
        ig_text.setStyleSheet("font-size: 9pt;")
        ig_text.setOpenExternalLinks(True)

        # === GitHub icon ===
        gh_label = QLabel(dialog)
        gh_label.setGeometry(300, 122, 32, 32)
        gh_pixmap = QPixmap(os.path.join(GRAPHICS_DIR, "GitHub.png"))
        if not gh_pixmap.isNull():
            gh_label.setPixmap(gh_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        gh_text = QLabel('<a href="https://github.com/DIY-Engineering" style="color: #FFFF96; text-decoration: none;">GitHub</a>', dialog)
        gh_text.setGeometry(297, 157, 55, 15)
        gh_text.setStyleSheet("font-size: 9pt;")
        gh_text.setOpenExternalLinks(True)

        # === Contact label ===
        contact_label = QLabel("Contact", dialog)
        contact_label.setGeometry(180, 182, 100, 20)
        contact_label.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 9pt;")

        # === Gmail icon ===
        gm_label = QLabel(dialog)
        gm_label.setGeometry(190, 210, 175, 32)
        gm_pixmap = QPixmap(os.path.join(GRAPHICS_DIR, "Gmail.png"))
        if not gm_pixmap.isNull():
            gm_label.setPixmap(gm_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        gm_text = QLabel('<a href="mailto:diwhy.engineering.86@gmail.com" style="color: #FFFF96; text-decoration: none;">diwhy.engineering.86@gmail.com</a>', dialog)
        gm_text.setGeometry(115, 244, 250, 15)
        gm_text.setStyleSheet("font-size: 9pt;")
        gm_text.setOpenExternalLinks(True)

        dialog.exec_()

    def show_license(self):
        """Shows the LICENSE file content in a scrollable dialog"""
        license_path = os.path.join(BASE_DIR, "LICENSE")

        dialog = QDialog(self)
        dialog.setWindowTitle("License")
        dialog.setFixedSize(560, 800)
        dialog.setStyleSheet("background-color: #191919; color: #FFFFFF;")

        # === Center on screen ===
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - 560) // 2
        y = (screen.height() - 800) // 2
        dialog.move(x, y)

        # === Text area ===
        text_area = QTextEdit(dialog)
        text_area.setGeometry(6, 6, 548, 788)
        text_area.setReadOnly(True)
        text_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        text_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        text_area.setStyleSheet("""
            QTextEdit {
                background-color: #121212;
                color: #FFFFFF;
                border: 2px solid #FFFFFF;
                border-radius: 5px;
                font-family: Courier New;
                font-size: 9pt;
            }
        """)

        # === Load LICENSE file ===
        try:
            with open(license_path, 'r', encoding='utf-8') as f:
                text_area.setPlainText(f.read())
        except FileNotFoundError:
            text_area.setPlainText("LICENSE file not found.")
        except Exception as e:
            text_area.setPlainText(f"Error loading LICENSE file:\n{str(e)}")

        dialog.exec_()

    def open_lm_studio(self):
        """Search and launch LM Studio from common installation paths"""
        common_paths = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\LM Studio\LM Studio.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\LM Studio\LM Studio.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\LM Studio\LM Studio.exe"),
            os.path.expandvars(r"%USERPROFILE%\AppData\Local\Programs\LM Studio\LM Studio.exe"),
        ]

        for path in common_paths:
            if os.path.exists(path):
                subprocess.Popen([path])
                logging.info(f"[LM Studio] Launched from: {path}")
                return

        # === Not found ===
        logging.warning("[LM Studio] Executable not found")
        QMessageBox.warning(
            self, "LM Studio Not Found",
            "Could not find LM Studio on this system.\n\n"
            "Please make sure LM Studio is installed.\n"
            "Download from: https://lmstudio.ai"
        )

    def open_mcp_gui(self):
        """Launch MCP Server GUI in a separate process"""
        import subprocess, sys
        try:
            if not os.path.exists(MCP_SERVER_FILE):
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, "MCP Server Not Found",
                    f"Could not find:\n{MCP_SERVER_FILE}\n\n"
                    "Please check the MCP Server directory."
                )
                return
            subprocess.Popen(
                [sys.executable, MCP_SERVER_FILE],
                cwd=MCP_SERVER_DIR
            )
            logging.info("[MCP] GUI launched")
        except Exception as e:
            logging.error(f"[MCP] Failed to open GUI: {e}")

    def update_system_prompt_with_mcp(self, enabled):
        """Toggle MCP connection + start/stop headless server"""
        self.use_mcp_server = enabled

        if enabled:
            # === Start headless MCP server if not already running ===
            was_running = (self.llm.mcp_server_process is not None and
                           self.llm.mcp_server_process.poll() is None)
            self.llm.start_mcp_server_headless()
            if not self.llm.mcp_connected:
                delay = 0 if was_running else 3000
                logging.info(f"[MCP] Connecting in {delay}ms...")
                QTimer.singleShot(delay, self.llm.initialize_mcp_connection)
        else:
            self.llm.mcp_connected = False
            self.llm.stop_mcp_server_headless()
            logging.info("ℹ️ MCP disabled")

    def release_gpu_memory(self):
        """Release GPU Memory"""
        self.audio.release_whisper()
        self.tts.release_gpu_memory()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logging.info("🗑️ GPU memory cleared")

    def _build_settings_dict(self):
        """
        Builds and returns a dictionary with ALL current GUI settings.
        Single source of truth — used by save_settings() and load_settings() auto-save.
        Add new settings here ONCE and they'll be handled everywhere automatically.
        """
        return {
            'selected_mic':             self.mic_dropdown.currentText(),
            'selected_output_device':   self.output_device_dropdown.currentText(),
            'selected_lm_model':        self.lm_model_dropdown.currentText(),
            'selected_coqui_sample':    self.coqui_dropdown.currentText(),
            'volume_level':             str(self.volume_level),
            'mic_volume':               str(self.mic_volume),
            'coqui_temperature':        str(self.coqui_temperature),
            'coqui_top_p':              str(self.coqui_top_p),
            'coqui_top_k':              str(self.coqui_top_k),
            'coqui_speed':              str(self.coqui_speed),
            'coqui_stream_chunk_size':  str(self.coqui_stream_chunk_size),
            'vad_threshold':            str(self.vad_threshold),
            'vad_min_speech_duration':  str(self.vad_min_speech_duration),
            'vad_min_silence_duration': str(self.vad_min_silence_duration),
            'vad_device':               self.vad_device,
            'whisper_language':         self.whisper_language,
            'whisper_device':           self.whisper_device,
            'coqui_device':             self.coqui_device,
            'wake_word':                self.wake_word,
            'wake_word_enabled':        str(self.wake_word_enabled),
            'thinking_enabled':         self.thinking_enabled,
            'use_mcp_server':           str(self.use_mcp_server),
            'real_talk_enabled':        str(self.real_talk_enabled),
            'rag_memory_enabled':       str(self.rag_memory_enabled),
            'whisper_model':            self.whisper_model,
            'lm_server':                self.lm_server,
            'mcp_server':               self.mcp_server,
            'temperature':              str(self.temperature),
            'max_tokens':               str(self.max_tokens),
            'top_k':                    str(self.top_k),
            'repetition_penalty':       str(self.repetition_penalty),
            'min_p':                    str(self.min_p),
            'top_p':                    str(self.top_p),
            'prompt_text':              self.prompt_text.toPlainText().strip()
        }

    # === Reserved profile names — cannot be used by user ===
    RESERVED_PROFILE_NAMES = {"Jarvis"}

    def _validate_profile_name(self, file_path):
        """
        Returns True if profile name is valid (not reserved).
        Shows warning and returns False if name is reserved.
        """
        if not self.profiles.validate_profile_name(file_path):
            name = os.path.splitext(os.path.basename(file_path))[0]
            QMessageBox.warning(
                self, "Reserved Name",
                f"'{name}' is a reserved profile name and cannot be used.\n"
                f"Please choose a different name."
            )
            return False
        return True

    def save_settings(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Settings", SETTINGS_DIR, "JSON Files (*.json)")
        if not file_path:
            return

        # === Block reserved profile names ===
        if not self._validate_profile_name(file_path):
            return
        
        try:
            # === Build dictionary with all settings ===
            settings_dict = self._build_settings_dict()

            # === Save JSON via ProfileManager ===
            self.profiles.save_profile(file_path, settings_dict)
            self.profile_modified = False
            QMessageBox.information(self, "Success", f"Settings saved to {file_path}")

            # === Move conversation if saving under a NEW profile name ===
            profile_name = os.path.splitext(os.path.basename(file_path))[0]

            if profile_name != self.current_profile_name:
                # === New profile name → move chat history and RAG to new profile ===
                self.save_current_conversation_to_profile(profile_name)
            else:
                # === Same profile name → paths already correct, just reinit to be safe ===
                self.switch_profile_paths(profile_name)
                self.rag.switch_profile(self.current_rag_dir)
        
        except Exception as e:
            logging.error(f"Error saving settings: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error saving settings: {str(e)}")

    def save_current_conversation_to_profile(self, profile_name):
        try:
            # === Move Chat History (text file — no locks, works fine) ===
            new_chat_log = os.path.join(HISTORY_DIR, f"{profile_name}.txt")
            if os.path.exists(self.current_chat_log) and self.current_chat_log != new_chat_log:
                if os.path.exists(new_chat_log):
                    os.remove(new_chat_log)
                os.rename(self.current_chat_log, new_chat_log)
                logging.info(f"✅ Chat History moved → {new_chat_log}")

            # === Release all RAG file handles before touching the directory on disk ===
            self.rag.release_for_move()

            # === Delete old RAG DB — no move, just delete! ===
            # It will be rebuilt from Chat History at the new profile path
            old_rag_dir = self.current_rag_dir
            if os.path.exists(old_rag_dir):
                try:
                    shutil.rmtree(old_rag_dir)
                    logging.info(f"✅ Old RAG DB deleted: {old_rag_dir}")
                except Exception as e:
                    logging.warning(f"⚠️ Could not delete old RAG DB: {e} — will be overwritten on next use")

            # === Switch paths to new profile ===
            self.switch_profile_paths(profile_name)
            self.rag.switch_profile(self.current_rag_dir)

            # === Restart RAG worker thread ===
            self.rag.start_worker()

            # === Rebuild RAG from Chat History ===
            if self.rag_memory_enabled:
                logging.info("🔄 Rebuilding RAG from Chat History for new profile...")
                self.rag.rebuild()

        except Exception as e:
            logging.error(f"❌ Error saving conversation to profile: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error saving conversation:\n{str(e)}")

    def load_settings(self):

        # === STEP 1: Ask to save if unsaved changes exist ===
        if not self._ask_save_if_modified():
            return  # User cancelled

        # === STEP 2: Pick new profile file ===
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Profile", SETTINGS_DIR, "JSON Files (*.json)"
        )
        if not file_path or not os.path.exists(file_path):
            return

        # === STEP 3: Switch to new profile paths and reinit RAG ===
        new_profile_name = os.path.splitext(os.path.basename(file_path))[0]
        self.switch_profile_paths(new_profile_name)
        self.rag.switch_profile(self.current_rag_dir)

        # === STEP 4: Load chat history for new profile ===
        self.chat_history = []
        self.chat_text.clear()
        self.load_initial_chat_history()
        self.update_chat_display()

        try:
            # === Load JSON ===
            with open(file_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)

            # === Apply all settings to GUI ===
            self._apply_settings_to_gui(settings)

            # === Refresh MCP Logic ===
            if self.use_mcp_server:
                idx = 0
                if self.mcp_group.button(idx):
                    self.mcp_group.button(idx).setChecked(True)

            logging.info(f"✅ Profile '{new_profile_name}' loaded successfully!")
            self.profile_modified = False
            QMessageBox.information(self, "Success", f"Profile '{new_profile_name}' loaded successfully!")

        except Exception as e:
            logging.error(f"Error loading settings: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error loading settings: {str(e)}")

    def load_default_settings(self, silent=False):
        if not silent:
            reply = QMessageBox.question(self, "Confirm", "Are you sure you want to reset settings to defaults?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return

        self.volume_level = 50
        self.volume_slider.setValue(50)
        self.mic_volume = 50
        self.mic_volume_slider.setValue(50)
        self.coqui_temperature = 0.7
        self.coqui_temperature_slider.setValue(70)
        self.coqui_top_p = 0.95
        self.coqui_top_p_slider.setValue(95)
        self.coqui_top_k = 50
        self.coqui_top_k_slider.setValue(50)
        self.coqui_speed = 1.0
        self.coqui_speed_slider.setValue(10)
        self.coqui_stream_chunk_size = 200
        self.coqui_stream_chunk_size_slider.setValue(200)
        self.vad_threshold = 0.2
        self.threshold_slider.setValue(20)
        self.vad_min_speech_duration = 1.0
        self.min_speech_slider.setValue(10)
        self.vad_min_silence_duration = 1.5
        self.min_silence_slider.setValue(15)
        self.vad_device = "cuda" if torch.cuda.is_available() else "cpu"
        self.vad_device_group.button(0 if self.vad_device == "cuda" else 1).setChecked(True)
        
        self.whisper_language = "auto"
        self.whisper_lang_group.button(0).setChecked(True)
        
        self.whisper_device = "cuda" if torch.cuda.is_available() else "cpu"
        self.whisper_device_group.button(0 if self.whisper_device == "cuda" else 1).setChecked(True)

        self.coqui_device = "cuda" if torch.cuda.is_available() else "cpu"
        self.coqui_device_group.button(0 if self.coqui_device == "cuda" else 1).setChecked(True)
        self.coqui_sample = "EN Jarvis (Paul Bettany).wav"
        self.selected_coqui_sample = "EN Jarvis (Paul Bettany).wav"
        idx = self.coqui_dropdown.findText("EN Jarvis (Paul Bettany).wav")
        if idx >= 0:
            self.coqui_dropdown.setCurrentIndex(idx)

        self.wake_word = "Jarvis"
        self.wake_word_entry.setText("Jarvis")
        self.wake_word_enabled = True
        self.wake_word_group.button(0).setChecked(True)

        self.use_mcp_server = False
        self.mcp_group.button(1).setChecked(True)

        self.real_talk_enabled = False
        self.real_talk_group.button(1).setChecked(True)

        self.rag_memory_enabled = True
        self.rag_group.button(0).setChecked(True)

        self.whisper_model = "medium"
        self.whisper_model_group.button(3).setChecked(True)

        self.lm_server = "http://127.0.0.1:1234"
        self.lm_server_entry.setText("http://127.0.0.1:1234")
        self.mcp_server = "http://127.0.0.1:8765"
        self.mcp_server_entry.setText("http://127.0.0.1:8765")
        
        self.temperature = 0.7
        self.temperature_slider.setValue(70)
        self.max_tokens = 512
        self.max_tokens_entry.setText("512")
        self.top_k = 40
        self.top_k_entry.setText("40")
        self.repetition_penalty = 1.1
        self.repetition_penalty_entry.setText("1.1")
        self.min_p = 0.05
        self.min_p_slider.setValue(5)
        self.top_p = 0.95
        self.top_p_slider.setValue(95)

        # === SYSTEM PROMPT ===
        self.prompt_text.setPlainText("Your name is Jarvis. You are a local AI assistant running on user's PC\nFirst you ask the user for his name, then continue the conversation using his/her name\n\nPERSONALITY:\n- Act natural, like with a close friend\n- Keep responses concise and on point\n- A little humor is welcome when appropriate\n\nLANGUAGE:\n- Always respond in the same language the user is speaking\n- If the user switches language mid-conversation, switch with them immediately\n\nSPEECH TO TEXT AWARENESS:\n- The user interacts with you via microphone\n- If something seems misspelled or unclear, use context to figure out what the user meant\n- Never point out transcription mistakes to the user\n\nTEXT TO SPEECH:\n- You talk to the user thru a TTS system with the voice of Jarvis\n- DO NOT USE ANY special characters or emoji otherwise you may sound unnatural\n\nMEMORY & CONTEXT:\n- You have access to conversation history and user context via RAG\n- Use this context naturally and don't announce that you're using it\n\nMCP TOOL USE:\n- When the user activates tool use mode, you will receive the available tools and their JSON schema dynamically\n- You detect when you are in tool use mode when user ask you to take an action that may match any possible combination of tools from the MCP server\n- In tool use mode, respond ONLY with valid JSON, no extra text, no explanations\n- In tool use mode you DON'T output commands that may affect the integrity of the data on user's machine UNLESS explicitly asked\n- In normal conversation mode, never output raw JSON\n\nBOUNDARIES:\n- You refuse any request that involves harming people or property\n- You refuse to engage in explicit sexual conversations\n- Do so briefly and respectfully, without lecturing\n")

        # === Reset profile paths to default "Jarvis" ===
        self.switch_profile_paths("Jarvis")
        self.profile_modified = False
        logging.info("Profile paths reset to default 'Jarvis'.")

        logging.info("Default settings loaded.")
        if not silent:
            QMessageBox.information(self, "Success", "Default settings loaded successfully")

    def load_initial_chat_history(self):
        """Load chat history at startup — includes MCP Request/Response entries"""
        try:
            if os.path.exists(self.current_chat_log):
                with open(self.current_chat_log, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                self.chat_history = self.profiles.parse_chat_file(lines, include_mcp=True)
                logging.info(f"Initial chat history loaded: {len(self.chat_history)} messages")
                self.update_chat_display()

        except Exception as e:
            logging.error(f"Error loading initial chat history: {str(e)}")

    def save_prompt(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Prompt", PROMPTS_DIR, "Text Files (*.txt);;All Files (*)")
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.prompt_text.toPlainText())
            logging.info(f"Prompt saved to {file_path}")
            QMessageBox.information(self, "Success", "Prompt saved successfully")

    def load_prompt(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Prompt", PROMPTS_DIR, "Text Files (*.txt);;All Files (*)")
        if file_path:
            with open(file_path, "r", encoding="utf-8") as f:
                self.prompt_text.setPlainText(f.read())
            logging.info(f"Prompt loaded from {file_path}")
            QMessageBox.information(self, "Success", "Prompt loaded successfully")

    def save_chat_history(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Chat History", HISTORY_DIR, "Text Files (*.txt);;All Files (*)")
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                for entry in self.chat_history:
                    f.write(f"{entry['timestamp']} {entry['role']}: {entry['text']}\n")
            logging.info(f"Chat history saved to {file_path}")
            QMessageBox.information(self, "Success", "Chat history saved successfully")

    def load_chat_history(self):
        """Load chat history from a user-selected file — User/Assistant only (no MCP entries)"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Chat History", HISTORY_DIR, "Text Files (*.txt);;All Files (*)")
        if not file_path:
            return
    
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            self.chat_history = self.profiles.parse_chat_file(lines, include_mcp=False)
            self.update_chat_display()
            logging.info(f"Chat history loaded from {file_path}: {len(self.chat_history)} messages")
            QMessageBox.information(self, "Success", f"Chat history loaded successfully\n{len(self.chat_history)} messages loaded")
        
        except Exception as e:
            logging.error(f"Error loading chat history from {file_path}: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error loading chat history:\n{str(e)}")

    def clear_chat_history(self):
        reply = QMessageBox.question(
            self, 
            "Confirm", 
            "Clear chat history?\n\n⚠️ This will also completely reset the RAG memory database!\n"
            "The SQLite file will be deleted and recreated from scratch.",
            QMessageBox.Yes | QMessageBox.No
        )
    
        if reply == QMessageBox.Yes:
            # === 1. Clear in-memory chat history and UI ===
            self.chat_history = []
            self.chat_text.clear()
        
            # === 2. Clear chat log file ===
            try:
                with open(self.current_chat_log, "w", encoding="utf-8") as f:
                    pass
                logging.info("✅ Chat log file cleared.")
            except Exception as e:
                logging.error(f"❌ Error clearing chat log file: {str(e)}")

            # === 3. Full RAG reset — encapsulated in RAGManager.clear() ===
            self.rag.clear()

            logging.info("✅ Chat history and RAG database fully reset.")
            QMessageBox.information(
                self, 
                "Success", 
                "Chat history and RAG memory cleared successfully!\n"
                "The database has been reset to zero."
            )

    def rebuild_rag_database(self):
        """Manually rebuilds RAG Database from Chat History"""
    
        # === CHECK 1: RAG Memory active? ===
        if not self.rag_memory_enabled:
            QMessageBox.warning(
                self,
                "RAG Memory Disabled",
                "RAG Memory is currently disabled!\n\n"
                "Please enable 'RAG Memory' first."
            )
            return
    
        # === CHECK 2: Chat history empty? ===
        if not self.chat_history:
            reply = QMessageBox.question(
                self,
                "Chat History Empty",
                "Chat history is empty!\n\n"
                "Would you like to load a chat history file (.txt) first?",
                QMessageBox.Yes | QMessageBox.No
            )
        
            if reply == QMessageBox.Yes:
                # === Opens file dialog for loading file ===
                self.load_chat_history()
            
                # === Check again if something loaded ===
                if not self.chat_history:
                    QMessageBox.information(
                        self,
                        "Cancelled",
                        "No chat history loaded. RAG rebuild cancelled."
                    )
                    return
            else:
                return
    
        # === CHECK 3: RAG System initialized? ===
        if not self.rag.is_ready():
            QMessageBox.critical(
                self,
                "RAG System Error",
                "RAG system is not properly initialized!\n\n"
                "Please restart the application."
            )
            return
    
        # === CONFIRMING REBUILD ===
        current_docs = self.rag.document_count()
    
        reply = QMessageBox.question(
            self,
            "Confirm Rebuild",
            f"Current RAG Database: {current_docs} documents\n"
            f"Chat History: {len(self.chat_history)} messages\n\n"
            f"This will:\n"
            f"• Clear existing RAG database\n"
            f"• Rebuild from current chat history\n\n"
            f"Continue?",
            QMessageBox.Yes | QMessageBox.No
        )
    
        if reply == QMessageBox.No:
            return
    
        # === REBUILD PROCESS ===
        try:
            logging.info("🔄 Starting RAG database rebuild...")

            # === include_mcp=True — AI also "remembers" previous tool calls/results ===
            messages_indexed = self.rag.rebuild(self.chat_history, include_mcp=True)

            logging.info(f"✅ Queued {messages_indexed} messages for indexing")
        
            # === Waits a bit for RAG worker to process ===
            QTimer.singleShot(2000, lambda: self.show_rebuild_complete(messages_indexed))
        
            # === Instant Feedback ===
            QMessageBox.information(
                self,
                "Rebuild Started",
                f"RAG rebuild started!\n\n"
                f"Indexing {messages_indexed} messages...\n"
                f"Check Debug Console for progress."
            )
        
        except Exception as e:
            logging.error(f"❌ RAG rebuild error: {str(e)}")
            QMessageBox.critical(
                self,
                "Rebuild Error",
                f"Failed to rebuild RAG database:\n\n{str(e)}"
            )

    def show_rebuild_complete(self, expected_count):
        """Callback after rebuild for confirmation"""
        try:
            actual_count = self.rag.document_count()
        
            QMessageBox.information(
                self,
                "Rebuild Complete",
                f"✅ RAG database rebuilt!\n\n"
                f"Expected: {expected_count} messages\n"
                f"Indexed: {actual_count} documents\n\n"
                f"Memory is now up to date!"
            )
        
            logging.info(f"✅ RAG rebuild complete: {actual_count} documents")
        
        except Exception as e:
            logging.error(f"Error checking rebuild status: {str(e)}")

    def update_chat_display(self):
        """Displays only visible messeges in UI"""
        self.chat_text.clear()

        logging.info(f"🐛 Total messages: {len(self.chat_history)}")
        for i, entry in enumerate(self.chat_history):
            role = entry.get('role', 'UNKNOWN')
            visible = entry.get('visible', 'MISSING')
            text_preview = entry.get('text', '')[:30]
            logging.info(f"🐛 [{i}] {role} | visible={visible} | '{text_preview}...'")


        # === Chronological sorting before display ===
        sorted_history = sorted(self.chat_history, key=lambda x: x.get('timestamp', ''))
    
        for entry in sorted_history:
            # === Skip MCP messages în UI - display only User/Assistant ===
            if entry.get("visible", True):  
                role = entry['role']
                text = entry['text']
                color = "#00B200" if role == "User" else "#FFFF96"
                # === Reuse the same widget-writing logic as append_log() ===
                # === Same code path whether it's one live message or a full history rebuild ===
                self._append_chat_safe(role, text, color)

    def closeEvent(self, event):
        # === Ask to save if unsaved changes exist ===
        if not self._ask_save_if_modified():
            event.ignore()
            return

        self.tts.stop()
        self.audio.stop()
        self.stop_tts_stream()    
        self.rag.stop()
        # === Stop System Monitor worker thread ===
        self.monitor_worker.stop()
        self.monitor_thread.quit()
        self.monitor_thread.wait(2000)
        # === Stop the headless MCP Server if it runs ===
        if self.use_mcp_server:
            self.llm.stop_mcp_server_headless()
            logging.info("[MCP] Server stopped on application close")
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # === Set dark palette ===
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(25, 25, 25))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(18, 18, 18))
    palette.setColor(QPalette.AlternateBase, QColor(25, 25, 25))
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(60, 60, 60))
    palette.setColor(QPalette.ButtonText, Qt.white)
    app.setPalette(palette)
    
    window = AIAssistantGUI()
    window.show()
    sys.exit(app.exec_())
