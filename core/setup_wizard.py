"""
First-Time Member Interactive Setup Wizard.
LitRadar Suite.
"""

import os
import sys
import getpass
import sqlite3
import subprocess
from pathlib import Path
from typing import Dict, Any

# Ensure core and base dirs are in path
CORE_DIR = Path(__file__).resolve().parent
BASE_DIR = CORE_DIR.parent if CORE_DIR.name == "core" else CORE_DIR
ENV_FILE = BASE_DIR / "lab_config.env"
REQUIREMENTS_FILE = CORE_DIR / "requirements.txt"


def read_existing_env() -> Dict[str, str]:
    """Load existing lab_config.env if present."""
    cfg = {}
    if ENV_FILE.exists():
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        cfg[k.strip()] = v.strip().strip("\"'")
        except Exception:
            pass
    return cfg


def detect_local_zotero() -> str:
    """Find local zotero.sqlite if present."""
    user_prof = os.environ.get("USERPROFILE", "")
    candidates = [
        Path(user_prof) / "Zotero" / "zotero.sqlite",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return str(Path(user_prof) / "Zotero" / "zotero.sqlite")


def detect_pdf_dir() -> str:
    """Find existing or best default PDF vault directory."""
    user_prof = os.environ.get("USERPROFILE", "")
    candidates = [
        Path(user_prof) / "OneDrive" / "Scientific Journals",
        Path(user_prof) / "Documents" / "Scientific Journals",
        BASE_DIR / "downloaded_pdfs",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return str(BASE_DIR / "downloaded_pdfs")


def prompt(label: str, default: str = "", help_text: str = "") -> str:
    """Prompt user with optional default and inline help."""
    if help_text:
        print(f"      -> {help_text}")
    prompt_str = f"   {label} [{default}]: " if default else f"   {label}: "
    try:
        val = input(prompt_str).strip()
    except (EOFError, KeyboardInterrupt):
        print("\n\n[SETUP CANCELLED] No changes were made.")
        sys.exit(0)
    return val if val else default


def prompt_bool(label: str, default: bool = True, help_text: str = "") -> bool:
    """Prompt user for a yes/no boolean."""
    if help_text:
        print(f"      -> {help_text}")
    def_str = "Y/n" if default else "y/N"
    prompt_str = f"   {label} ({def_str}): "
    try:
        val = input(prompt_str).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n\n[SETUP CANCELLED] No changes were made.")
        sys.exit(0)
    if not val:
        return default
    return val in ["y", "yes", "true", "1"]


def test_zotero_credentials(user_id: str, api_key: str) -> tuple[bool, str]:
    """Test Zotero API credentials."""
    if not user_id or not api_key:
        return False, "User ID or API Key missing"
    try:
        import pyzotero.zotero
        zot = pyzotero.zotero.Zotero(user_id, "user", api_key)
        # Fast lightweight call (limit=1)
        zot.items(limit=1)
        return True, "Authenticated successfully"
    except Exception as e:
        err = str(e)
        if "403" in err or "Forbidden" in err:
            return False, "403 Forbidden: Invalid API Key or User ID"
        return False, err[:60]


def check_and_install_dependencies():
    """Verify required libraries and auto-install if missing."""
    print("\n[Step 7/7] Checking Python dependencies...")
    missing = []
    for pkg in ["requests", "openpyxl", "pyzotero", "urllib3"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"   Missing packages detected: {', '.join(missing)}")
        print("   Installing required packages via pip...")
        try:
            if REQUIREMENTS_FILE.exists():
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE), "--quiet"],
                    check=True
                )
            else:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "requests", "openpyxl", "pyzotero", "--quiet"],
                    check=True
                )
            print("   [SUCCESS] Packages installed successfully.")
        except Exception as e:
            print(f"   [WARNING] Pip install returned: {e}")
    else:
        print("   [OK] All core dependencies (requests, openpyxl, pyzotero) are installed.")


def run_wizard():
    print("=" * 76)
    print("                             LitRadar SUITE")
    print("                      FIRST-TIME MEMBER SETUP WIZARD")
    print("=" * 76)
    print(" This wizard will configure your profile, storage paths, and API keys.")
    print(" Press [ENTER] on any question to accept the suggested default in brackets.")
    print("=" * 76)
    print()

    existing = read_existing_env()
    detected_zotero_db = detect_local_zotero()
    detected_pdf_dir = detect_pdf_dir()
    current_user = getpass.getuser()

    # 1. Profile
    print("[Step 1/7] Lab Member Profile")
    def_name = existing.get("LAB_MEMBER_NAME", current_user)
    name = prompt("Your Full Name", def_name)

    def_inst_email = existing.get("LAB_MEMBER_EMAIL", "")
    inst_email = prompt("Your Institutional / Primary Email", def_inst_email)

    def_recip = existing.get("RECIPIENT_EMAIL", existing.get("LAB_MEMBER_EMAIL", inst_email))
    recip_email = prompt(
        "Recipient Email",
        def_recip,
        help_text="Your personal Gmail or inbox where weekly digests & alerts will be sent."
    )
    print()

    # 2. Email Dispatch
    print("[Step 2/7] Automated Email Dispatch (Optional)")
    has_smtp = bool(existing.get("SENDER_GMAIL") and existing.get("GMAIL_APP_PASSWORD"))
    enable_smtp = prompt_bool(
        "Enable automated email delivery from this machine?",
        default=has_smtp,
        help_text="Requires a free Gmail 16-character App Password."
    )

    sender_gmail = ""
    app_password = ""
    if enable_smtp:
        sender_gmail = prompt("Sender Gmail (use a non-.edu personal Gmail)", existing.get("SENDER_GMAIL", ""))
        print("      NOTE: Institutional .edu accounts cannot generate App Passwords.")
        print("            Use a personal @gmail.com address instead.")
        print()
        print("      How to get a free Gmail App Password (~60 seconds):")
        print("        1. Go to https://myaccount.google.com/security")
        print("        2. Ensure 2-Step Verification is ON")
        print("        3. Search 'App Passwords' -> Name it 'Literature Pipeline'")
        print("        4. Copy the 16 letters and paste below:")
        app_password = prompt("Gmail 16-character App Password", existing.get("GMAIL_APP_PASSWORD", ""))
    else:
        print("      [i] Email dispatch skipped. HTML digests will still be saved to output/ folder.")
    print()

    # 3. Zotero Integration
    print("[Step 3/7] Zotero Cloud Integration")
    print("      (Used to import new papers, sync tags, and link PDFs to Zotero Cloud)")
    print("      Find your User ID and create a key at: https://www.zotero.org/settings/keys")
    def_z_user = existing.get("ZOTERO_USER_ID", "")
    z_user_id = prompt("Zotero User ID", def_z_user)

    def_z_key = existing.get("ZOTERO_API_KEY", "")
    z_api_key = prompt("Zotero API Key", def_z_key)

    # Test Zotero key
    if z_user_id and z_api_key:
        print("      Testing Zotero Cloud connection...", end="", flush=True)
        ok, msg = test_zotero_credentials(z_user_id, z_api_key)
        if ok:
            print(" [CONNECTED! Verified]")
        else:
            print(f" [WARNING: {msg}]")
            print("      (You can proceed anyway; credentials can be adjusted in lab_config.env later.)")
    print()

    # 4. Local Zotero Database
    print("[Step 4/7] Local Zotero Database (for fast 2,359+ paper deduplication)")
    def_local_db = existing.get("ZOTERO_LOCAL_DB", detected_zotero_db)
    local_db = prompt(
        "Path to local zotero.sqlite",
        def_local_db,
        help_text=f"Detected: {detected_zotero_db}"
    )
    if Path(local_db).exists():
        print(f"      [OK] Verified local database exists ({Path(local_db).stat().st_size // (1024*1024)} MB).")
    else:
        print(f"      [NOTE] Database file not found at this path. Web API deduplication will be used as fallback.")
    print()

    # 5. PDF Storage Vault
    print("[Step 5/7] Full-Text PDF Storage Directory")
    print("      Where downloaded full-text papers will be sorted into subfolders.")
    def_pdf_dir = existing.get("PDF_STORAGE_DIR", detected_pdf_dir)
    pdf_dir = prompt("Master PDF Directory", def_pdf_dir)
    try:
        Path(pdf_dir).mkdir(parents=True, exist_ok=True)
        print(f"      [OK] Directory verified and ready: {pdf_dir}")
    except Exception as e:
        print(f"      [WARNING] Could not create directory: {e}")
    print()

    # 6. Scientific APIs & AI Keys
    print("[Step 6/7] Scientific APIs & AI Keys (Optional)")
    def_ncbi_email = existing.get("NCBI_EMAIL", inst_email)
    ncbi_email = prompt("NCBI Email (for PubMed)", def_ncbi_email)

    def_ncbi_key = existing.get("NCBI_API_KEY", "")
    ncbi_key = prompt(
        "NCBI API Key (Optional)",
        def_ncbi_key,
        help_text="Speeds up PubMed queries to 10/sec. Get free at: https://www.ncbi.nlm.nih.gov/account/settings/"
    )

    def_gemini_key = existing.get("GEMINI_API_KEY", "")
    gemini_key = prompt(
        "Google Gemini API Key (Optional)",
        def_gemini_key,
        help_text="Powers automated podcast scripts, deep summaries, and future LM audio. Free at: https://aistudio.google.com/app/apikey"
    )

    def_semantic_key = existing.get("SEMANTIC_SCHOLAR_API_KEY", "")
    semantic_key = prompt("Semantic Scholar API Key (Optional)", def_semantic_key)
    print()

    # Check dependencies
    check_and_install_dependencies()

    # Write lab_config.env
    python_exe = sys.executable

    env_content = f"""# ==============================================================================
#                             LitRadar SUITE
#                    MEMBER CONFIGURATION FILE
# ==============================================================================
# PRO-TIP FOR LAB MEMBERS:
# Back up this 'lab_config.env' file somewhere safe (e.g. your cloud drive
# or password vault). When working on a new computer or workstation, just
# drop this file into the folder and all scripts are instantly configured!
#
# Instructions:
# 1. You can re-run '00_First_Time_Setup.bat' at any time to update this file.
# 2. Or edit the values directly below in Notepad (Ctrl+S to save).
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. LAB MEMBER PROFILE
# ------------------------------------------------------------------------------
LAB_MEMBER_NAME={name}
LAB_MEMBER_EMAIL={inst_email}

# Personal Gmail / inbox to RECEIVE weekly digests & alerts:
RECIPIENT_EMAIL={recip_email}

# ------------------------------------------------------------------------------
# 2. EMAIL DISPATCH SETTINGS (For automated weekly delivery to your inbox)
# ------------------------------------------------------------------------------
SENDER_GMAIL={sender_gmail}
GMAIL_APP_PASSWORD={app_password}

# ------------------------------------------------------------------------------
# 3. ZOTERO CLOUD INTEGRATION
# ------------------------------------------------------------------------------
ZOTERO_USER_ID={z_user_id}
ZOTERO_API_KEY={z_api_key}

# Path to local zotero.sqlite for instant deduplication:
ZOTERO_LOCAL_DB={local_db}

# ------------------------------------------------------------------------------
# 4. STORAGE LOCATIONS
# ------------------------------------------------------------------------------
PDF_STORAGE_DIR={pdf_dir}

# ------------------------------------------------------------------------------
# 5. SCIENTIFIC APIs & AI ENGINES
# ------------------------------------------------------------------------------
NCBI_EMAIL={ncbi_email}
NCBI_API_KEY={ncbi_key}
GEMINI_API_KEY={gemini_key}
SEMANTIC_SCHOLAR_API_KEY={semantic_key}

# ------------------------------------------------------------------------------
# 6. SYSTEM RUNTIME
# ------------------------------------------------------------------------------
PYTHON_EXE={python_exe}
"""

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(env_content)

    print()
    print("=" * 76)
    print("                     SETUP CONFIGURATION SUMMARY")
    print("=" * 76)
    print(f"  [*] Member Name:         {name}")
    print(f"  [*] Member Email:        {inst_email}")
    print(f"  [*] Recipient Email:     {recip_email}")
    print(f"  [*] Email Dispatch:      {'Enabled (' + sender_gmail + ')' if sender_gmail else 'Disabled (Local HTML only)'}")
    print(f"  [*] Zotero User ID:      {z_user_id}")
    print(f"  [*] PDF Storage Vault:   {pdf_dir}")
    print(f"  [*] Python Interpreter:  {python_exe}")
    print(f"  [*] Saved Config:        {ENV_FILE}")
    print("=" * 76)
    print(" [SUCCESS] Your configuration is saved and ready!")
    print()
    print(" --------------------------------------------------------------------------")
    print("  PRO-TIP FOR LAB MEMBERS:")
    print("  Back up your 'lab_config.env' file to your cloud drive or a secure vault.")
    print("  When switching computers or setting up a new workstation, simply drop")
    print("  your saved 'lab_config.env' into this folder and all scripts will run")
    print("  immediately without having to re-enter your API keys and paths!")
    print(" --------------------------------------------------------------------------")
    print()
    print(" You can now double-click any launcher in the root folder:")
    print("   -> 01_Find_New_Papers.bat              : Search & discover new papers")
    print("   -> 02_Retag_Zotero_Library.bat         : Retag & organize your Zotero library")
    print("   -> 03_Run_Weekly_Surveillance.bat      : Run autonomous 5-pillar surveillance")
    print("   -> 04_Harvest_Foundational_Benchmarks.bat : Harvest Top 20 landmark papers & podcasts")
    print("   -> Setup_Weekly_Scheduler.bat          : Schedule Sunday 11 PM background run")
    print("=" * 76)


if __name__ == "__main__":
    run_wizard()
