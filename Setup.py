"""
Advanced STS Local AI Assistant — Full Setup Script
====================================================
This script handles the complete setup in 3 stages:

  STAGE 1 — Python Version Check
    Verifies Python 3.12.6 x64 is being used.
    Exits with a clear error if the version is wrong.

  STAGE 2 — Python Dependencies
    Installs all required packages from the embedded
    requirements list. PyTorch with CUDA 12.1 is handled
    separately before the rest of the packages.

  STAGE 3 — Model Downloads
    Downloads and installs all required AI models:
      - Silero VAD       (silero_vad.jit, .onnx, _half.onnx)
      - Faster-Whisper   (tiny, base, small, medium, large-v3)
      - MiniLM-L6-v2     (RAG Embedder)
      - Coqui XTTS-v2    (TTS Model + tos_agreed.txt)

Usage:
    python setup.py                         (full setup — all stages)
    python setup.py --skip-deps             (skip dependency installation)
    python setup.py --skip-models           (skip model downloads)
    python setup.py --skip-whisper          (skip Faster-Whisper models)
    python setup.py --only-coqui            (download only Coqui XTTS-v2)
    python setup.py --only-whisper          (download only Faster-Whisper)
    python setup.py --cpu                   (install PyTorch CPU version instead of CUDA)
    python setup.py --whisper-models small medium large-v3  (specific Whisper models only)
"""

import os
import sys
import shutil
import argparse
import logging
import subprocess
import platform

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

REQUIRED_PYTHON_VERSION = (3, 12, 6)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# FOLDER STRUCTURE
# ============================================================

FOLDER_STRUCTURE = [
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

PATHS = {
    "silero_vad"  : os.path.join(BASE_DIR, "Silero VAD", "Models"),
    "whisper_base": os.path.join(BASE_DIR, "Whisper STT", "Models"),
    "minilm"      : os.path.join(BASE_DIR, "RAG Embedder", "MiniLM-L6-v2"),
    "coqui"       : os.path.join(BASE_DIR, "Coqui TTS", "Models"),
}

WHISPER_MODELS = {
    "tiny"    : "Systran/faster-whisper-tiny",
    "base"    : "Systran/faster-whisper-base",
    "small"   : "Systran/faster-whisper-small",
    "medium"  : "Systran/faster-whisper-medium",
    "large-v3": "Systran/faster-whisper-large-v3",
}

SILERO_FILES    = ["silero_vad.jit", "silero_vad.onnx", "silero_vad_half.onnx"]
SILERO_BASE_URL = "https://raw.githubusercontent.com/snakers4/silero-vad/master/src/silero_vad/data/"

COQUI_FILES = [
    "config.json",
    "hash.md5",
    "model.pth",
    "speakers_xtts.pth",
    "vocab.json",
]

MINILM_FILES = [
    "config.json",
    "config_sentence_transformers.json",
    "model.safetensors",
    "modules.json",
    "README.md",
    "sentence_bert_config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
]

MINILM_FOLDERS = ["1_Pooling"]

# ============================================================
# PyTorch — installed separately due to custom CUDA index URL
# ============================================================

PYTORCH_CUDA_PACKAGES = [
    "torch==2.5.1+cu121",
    "torchaudio==2.5.1+cu121",
    "torchvision==0.20.1+cu121",
]
PYTORCH_CUDA_INDEX = "https://download.pytorch.org/whl/cu121"

PYTORCH_CPU_PACKAGES = [
    "torch==2.0.1",
    "torchaudio==2.0.2",
    "torchvision==0.15.2",
]
PYTORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"

# ============================================================
# All other pip packages (installed after PyTorch)
# ============================================================

PIP_PACKAGES = [
    # GUI
    "PyQt5==5.15.11",
    # HTTP & Web
    "requests==2.32.5",
    "httpx==0.28.1",
    "aiohttp==3.13.2",
    "beautifulsoup4==4.14.2",
    # System & Audio
    "psutil==7.1.3",
    "pycaw==20251023",
    "PyAudio==0.2.14",
    "pydub==0.25.1",
    "soundfile==0.13.1",
    "audioread==3.1.0",
    # Google APIs
    "google-auth==2.48.0",
    "google-auth-httplib2==0.3.0",
    "google-auth-oauthlib==1.2.4",
    "google-api-python-client==2.188.0",
    # Faster Whisper
    "faster-whisper==1.2.1",
    "ctranslate2==4.6.3",
    "huggingface-hub==0.36.0",
    # OpenAI Whisper
    "openai-whisper==20250625",
    # Transformers & Embeddings
    "transformers==4.55.4",
    "tiktoken==0.12.0",
    "sentence-transformers==5.2.0",
    # Coqui TTS
    "coqui-tts==0.27.2",
    "gruut==2.4.0",
    # Audio Processing
    "librosa==0.11.0",
    "silero-vad==6.2.0",
    # Scientific Computing
    "numpy==2.3.4",
    "scipy==1.16.3",
    "scikit-learn==1.7.2",
    # Neural Network Utilities
    "einops==0.8.1",
    "encodec==0.1.1",
    # NLP
    "spacy==3.8.9",
    # MCP
    "mcp==1.25.0",
    # Data & Database
    "jsonlines==1.2.0",
    "jsonschema==4.25.1",
    "orjson==3.11.5",
    "chromadb==1.3.7",
    "python-multipart==0.0.21",
    # Configuration
    "python-dotenv==1.2.1",
    "PyYAML==6.0.3",
    "pydantic==2.12.4",
    "pydantic-settings==2.12.0",
    # CLI & Terminal
    "click==8.3.0",
    "rich==14.2.0",
    # Server
    "uvicorn==0.40.0",
    "starlette==0.52.1",
    "websockets==15.0.1",
    # Monitoring
    "tensorboard==2.20.0",
    # Media
    "pillow==12.0.0",
    "matplotlib==3.10.7",
    "yt-dlp==2025.12.8",
    # Text Processing
    "regex==2025.11.3",
    "inflect==7.5.0",
    "num2words==0.5.14",
    "emoji==2.15.0",
    "anyascii==0.3.3",
    "pysbd==0.3.4",
    # Utilities
    "tqdm==4.67.1",
    "tenacity==9.1.2",
    "Jinja2==3.1.6",
    "Markdown==3.10",
    "python-dateutil==2.9.0.post0",
    # Windows-specific
    "pywin32==311",
    # Build & Packaging
    "pyinstaller==6.18.0",
]

# ============================================================
# HELPERS
# ============================================================

def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def create_folder_structure():
    """
    Creates all required project folders if they don't already exist.
    Called automatically at startup — safe to run multiple times.
    Returns the number of newly created folders.
    """
    created = 0
    for folder in FOLDER_STRUCTURE:
        full_path = os.path.join(BASE_DIR, folder)
        if not os.path.exists(full_path):
            os.makedirs(full_path, exist_ok=True)
            log.info(f"   📁 Created: {folder}")
            created += 1
    return created


def run_pip(packages, index_url=None):
    """
    Runs pip install for a list of packages.
    Returns True if all installed successfully.
    """
    cmd = [sys.executable, "-m", "pip", "install"] + packages
    if index_url:
        cmd += ["--index-url", index_url]

    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def already_installed(dest_dir, required_files):
    """Check if model is already installed (all required files exist)."""
    if not os.path.exists(dest_dir):
        return False
    return all(os.path.exists(os.path.join(dest_dir, f)) for f in required_files)


def copy_snapshot_to_dest(hf_repo_id, dest_dir, repo_type="model",
                           allowed_files=None, allowed_folders=None):
    """
    Downloads a HuggingFace model directly to a staging folder (no symlinks),
    then moves only the required files to dest_dir and cleans up staging.

    Returns True if successful, False otherwise.
    """
    from huggingface_hub import snapshot_download

    try:
        log.info(f"📥 Downloading: {hf_repo_id}")
        log.info(f"   Destination: {dest_dir}")

        os.makedirs(dest_dir, exist_ok=True)
        staging_dir = os.path.join(dest_dir, "_staging_tmp")
        os.makedirs(staging_dir, exist_ok=True)

        # Download directly — no symlinks (fixes WinError 1314 on Windows)
        log.info(f"   Downloading to staging folder (no symlinks)...")
        snapshot_download(
            repo_id=hf_repo_id,
            repo_type=repo_type,
            local_dir=staging_dir,
            local_dir_use_symlinks=False,
            ignore_patterns=["*.msgpack", "*.h5", "flax_model*", "tf_model*"]
        )

        # Move only required files/folders from staging to dest
        copied = 0
        skipped = 0
        for item in os.listdir(staging_dir):
            src = os.path.join(staging_dir, item)
            dst = os.path.join(dest_dir, item)

            if item.startswith('.') or item == "_staging_tmp":
                continue

            if os.path.isfile(src):
                if allowed_files is not None and item not in allowed_files:
                    skipped += 1
                    continue
                shutil.move(src, dst)
                size = os.path.getsize(dst) / 1024**2
                log.info(f"   ✅ {item} ({size:.1f} MB)")
                copied += 1

            elif os.path.isdir(src):
                if allowed_folders is not None and item not in allowed_folders:
                    skipped += 1
                    continue
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.move(src, dst)
                log.info(f"   ✅ Folder: {item}")
                copied += 1

        log.info(f"   Total: {copied} kept | {skipped} skipped")

        # Cleanup staging — no duplicates on disk!
        shutil.rmtree(staging_dir, ignore_errors=True)
        log.info(f"   🗑️  Staging folder cleaned up")

        return True

    except Exception as e:
        log.error(f"   ❌ Error: {str(e)}")
        return False

# ============================================================
# STAGE 1 — PYTHON VERSION CHECK
# ============================================================

def check_python_version():
    """
    Verifies that the current Python version is exactly 3.12.6 x64.
    Returns True if OK, False otherwise.
    """
    print_header("STAGE 1 — Python Version Check")

    current = sys.version_info
    required = REQUIRED_PYTHON_VERSION
    arch = platform.architecture()[0]

    log.info(f"   Current Python : {current.major}.{current.minor}.{current.micro} {arch}")
    log.info(f"   Required Python: {required[0]}.{required[1]}.{required[2]} 64bit")

    # Check architecture
    if arch != "64bit":
        log.error(f"❌ Wrong architecture: {arch}")
        log.error(f"   Please install Python 3.12.6 64-bit from https://www.python.org/downloads/release/python-3126/")
        return False

    # Check version
    if (current.major, current.minor, current.micro) != required:
        log.error(f"❌ Wrong Python version: {current.major}.{current.minor}.{current.micro}")
        log.error(f"   This project requires Python {required[0]}.{required[1]}.{required[2]} exactly.")
        log.error(f"   Download it from: https://www.python.org/downloads/release/python-3126/")
        return False

    log.info(f"✅ Python {current.major}.{current.minor}.{current.micro} {arch} — OK!")
    return True

# ============================================================
# STAGE 2 — PYTHON DEPENDENCIES
# ============================================================

def install_dependencies(use_cpu=False):
    """
    Installs all Python dependencies.
    PyTorch is installed first with the appropriate index URL.
    Returns True if all packages installed successfully.
    """
    print_header("STAGE 2 — Installing Python Dependencies")

    # Step 1 — Upgrade pip first
    log.info("📦 Upgrading pip...")
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
                   capture_output=False)

    # Step 2 — Install PyTorch
    if use_cpu:
        log.info(f"\n🔥 Installing PyTorch (CPU version)...")
        torch_packages = PYTORCH_CPU_PACKAGES
        torch_index    = PYTORCH_CPU_INDEX
    else:
        log.info(f"\n🔥 Installing PyTorch (CUDA 12.1)...")
        torch_packages = PYTORCH_CUDA_PACKAGES
        torch_index    = PYTORCH_CUDA_INDEX

    for pkg in torch_packages:
        log.info(f"   {pkg}")

    torch_ok = run_pip(torch_packages, index_url=torch_index)

    if not torch_ok:
        log.error("❌ PyTorch installation failed!")
        log.error("   Check your internet connection and CUDA drivers.")
        return False

    log.info("✅ PyTorch installed successfully!")

    # Step 3 — Install remaining packages
    log.info(f"\n📦 Installing {len(PIP_PACKAGES)} packages...")

    # Install in batches of 10 to avoid command line length limits
    batch_size = 10
    failed = []

    for i in range(0, len(PIP_PACKAGES), batch_size):
        batch = PIP_PACKAGES[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(PIP_PACKAGES) + batch_size - 1) // batch_size
        log.info(f"   Batch {batch_num}/{total_batches}: {', '.join(p.split('==')[0] for p in batch)}")

        if not run_pip(batch):
            # Retry one by one to identify which package failed
            for pkg in batch:
                if not run_pip([pkg]):
                    log.error(f"   ❌ Failed: {pkg}")
                    failed.append(pkg)

    if failed:
        log.error(f"\n❌ {len(failed)} packages failed to install:")
        for pkg in failed:
            log.error(f"   - {pkg}")
        return False

    log.info(f"\n✅ All {len(PIP_PACKAGES)} packages installed successfully!")
    return True

# ============================================================
# STAGE 3 — MODEL DOWNLOADS
# ============================================================

def setup_silero_vad():
    """Download Silero VAD files from GitHub."""
    print_header("3a — Silero VAD")

    import requests

    dest_dir = PATHS["silero_vad"]
    os.makedirs(dest_dir, exist_ok=True)

    if already_installed(dest_dir, SILERO_FILES):
        log.info("ℹ️  Silero VAD already installed, skipping...")
        return True

    success = True
    for fname in SILERO_FILES:
        dest_file = os.path.join(dest_dir, fname)
        if os.path.exists(dest_file):
            log.info(f"   ⏭️  {fname} already exists, skipping...")
            continue

        log.info(f"📥 Downloading: {fname}")
        try:
            response = requests.get(SILERO_BASE_URL + fname, stream=True, timeout=60)
            response.raise_for_status()
            with open(dest_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            size = os.path.getsize(dest_file) / 1024**2
            log.info(f"   ✅ {fname} ({size:.1f} MB)")
        except Exception as e:
            log.error(f"   ❌ Error: {fname}: {str(e)}")
            success = False

    if success:
        log.info("✅ Silero VAD installed successfully!")
    return success


def setup_whisper_models(models_to_download=None):
    """Download selected Faster-Whisper models."""
    print_header("3b — Faster-Whisper STT Models")

    if models_to_download is None:
        models_to_download = list(WHISPER_MODELS.keys())

    results = {}
    for model_name in models_to_download:
        if model_name not in WHISPER_MODELS:
            log.warning(f"Unknown model: {model_name}, skipping...")
            continue

        dest_dir = os.path.join(PATHS["whisper_base"], model_name)

        if already_installed(dest_dir, ["model.bin", "config.json"]):
            log.info(f"   ⏭️  {model_name} already installed, skipping...")
            results[model_name] = True
            continue

        log.info(f"\n🔄 Downloading Faster-Whisper: {model_name}")
        results[model_name] = copy_snapshot_to_dest(WHISPER_MODELS[model_name], dest_dir)

    ok    = sum(1 for v in results.values() if v)
    total = len(results)
    log.info(f"\n✅ Whisper: {ok}/{total} models installed successfully")
    return ok == total


def setup_minilm():
    """Download MiniLM-L6-v2 model for RAG."""
    print_header("3c — MiniLM-L6-v2 (RAG Embedder)")

    dest_dir = PATHS["minilm"]

    if already_installed(dest_dir, ["config.json", "tokenizer.json"]):
        log.info("ℹ️  MiniLM-L6-v2 already installed, skipping...")
        return True

    result = copy_snapshot_to_dest(
        "sentence-transformers/all-MiniLM-L6-v2",
        dest_dir,
        allowed_files=MINILM_FILES,
        allowed_folders=MINILM_FOLDERS
    )

    if result:
        log.info("✅ MiniLM-L6-v2 installed successfully!")
    return result


def setup_coqui():
    """Download Coqui XTTS-v2 model and create tos_agreed.txt."""
    print_header("3d — Coqui XTTS-v2 (TTS Model)")

    dest_dir = PATHS["coqui"]

    if already_installed(dest_dir, ["model.pth", "config.json", "tos_agreed.txt"]):
        log.info("ℹ️  Coqui XTTS-v2 already installed, skipping...")
        return True

    log.info("⚠️  XTTS-v2 model is ~1.8GB — this may take 10-20 minutes!")

    result = copy_snapshot_to_dest(
        "coqui/XTTS-v2",
        dest_dir,
        allowed_files=COQUI_FILES,
        allowed_folders=[]
    )

    if result:
        tos_file = os.path.join(dest_dir, "tos_agreed.txt")
        with open(tos_file, "w", encoding="utf-8") as f:
            f.write("I have read, understood and agreed to the Terms and Conditions.")
        log.info("   ✅ tos_agreed.txt created!")
        log.info("✅ Coqui XTTS-v2 installed successfully!")

    return result

# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Full Setup — Advanced STS Local AI Assistant"
    )
    parser.add_argument("--skip-deps",    action="store_true", help="Skip Python dependency installation")
    parser.add_argument("--skip-models",  action="store_true", help="Skip model downloads")
    parser.add_argument("--skip-silero",  action="store_true", help="Skip Silero VAD download")
    parser.add_argument("--skip-whisper", action="store_true", help="Skip Faster-Whisper download")
    parser.add_argument("--skip-minilm",  action="store_true", help="Skip MiniLM-L6-v2 download")
    parser.add_argument("--skip-coqui",   action="store_true", help="Skip Coqui XTTS-v2 download")
    parser.add_argument("--only-coqui",   action="store_true", help="Download only Coqui XTTS-v2")
    parser.add_argument("--only-whisper", action="store_true", help="Download only Faster-Whisper")
    parser.add_argument("--cpu",          action="store_true", help="Install PyTorch CPU version (no CUDA)")
    parser.add_argument(
        "--whisper-models",
        nargs="+",
        choices=list(WHISPER_MODELS.keys()),
        default=list(WHISPER_MODELS.keys()),
        help="Whisper models to download (default: all)"
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  Advanced STS Local AI Assistant — Full Setup")
    print("=" * 60)
    print(f"  Root folder: {BASE_DIR}")
    print("=" * 60)

    results = {}

    # ===== STAGE 0 — Folder Structure (always runs) =====
    print_header("STAGE 0 — Creating Folder Structure")
    _created = create_folder_structure()
    if _created > 0:
        log.info(f"✅ Created {_created} new folder(s)")
    else:
        log.info("✅ All folders already exist — nothing to create")

    # ===== STAGE 1 — Python check (always runs) =====
    if not check_python_version():
        print("\n❌ Setup aborted — wrong Python version.")
        print("   Please install Python 3.12.6 x64 and try again.")
        sys.exit(1)

    # ===== STAGE 2 — Dependencies =====
    if not args.skip_deps and not args.only_coqui and not args.only_whisper:
        results["Python Dependencies"] = install_dependencies(use_cpu=args.cpu)
        if not results["Python Dependencies"]:
            log.error("❌ Dependency installation failed — aborting model downloads.")
            sys.exit(1)

    # ===== STAGE 3 — Models =====
    if not args.skip_models:
        if args.only_coqui:
            results["Coqui XTTS-v2"] = setup_coqui()
        elif args.only_whisper:
            results["Faster-Whisper"] = setup_whisper_models(args.whisper_models)
        else:
            if not args.skip_silero:
                results["Silero VAD"]     = setup_silero_vad()
            if not args.skip_whisper:
                results["Faster-Whisper"] = setup_whisper_models(args.whisper_models)
            if not args.skip_minilm:
                results["MiniLM-L6-v2"]   = setup_minilm()
            if not args.skip_coqui:
                results["Coqui XTTS-v2"]  = setup_coqui()

    # ===== FINAL SUMMARY =====
    print("\n" + "=" * 60)
    print("  INSTALLATION SUMMARY")
    print("=" * 60)

    all_ok = True
    print(f"  ✅ OK     —  Folder Structure")
    for name, ok in results.items():
        status = "✅ OK    " if ok else "❌ FAILED"
        print(f"  {status}  —  {name}")
        if not ok:
            all_ok = False

    print("=" * 60)

    if all_ok:
        print("\n🎉 Setup completed successfully!")
        print("   You can now start the Advanced STS Local AI Assistant!\n")
    else:
        print("\n⚠️  Some steps failed — check the errors above and try again.\n")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())