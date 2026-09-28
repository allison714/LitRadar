"""
Configuration for LitRadar.
Literature Intelligence & Podcast Pipeline.
"""

import os
import sys
from pathlib import Path

# Base Paths (Anchored to this Desktop folder)
CORE_DIR = Path(__file__).resolve().parent
BASE_DIR = CORE_DIR.parent if CORE_DIR.name == "core" else CORE_DIR
OUTPUT_DIR = BASE_DIR / "output"
PODCAST_DIR = BASE_DIR / "podcast_briefings"
EXCEL_PATH = OUTPUT_DIR / "SHANK2_Synaptopathy_Master.xlsx"

# ---------------------------------------------------------
# Load User Settings from lab_config.env (if present)
# ---------------------------------------------------------
ENV_FILE = BASE_DIR / "lab_config.env"
if ENV_FILE.exists():
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("\"'")
                    if k and v:
                        os.environ[k] = v
    except Exception:
        pass

# Master PDF Storage Directory (loaded from lab_config.env or default downloads folder)
PDF_STORAGE_DIR = Path(os.getenv("PDF_STORAGE_DIR") or (BASE_DIR / "downloaded_pdfs"))

# Ensure directories exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PODCAST_DIR.mkdir(parents=True, exist_ok=True)
try:
    PDF_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

# ---------------------------------------------------------
# 1. Search Query Definitions (5 Thematic Tracks)
# ---------------------------------------------------------
TRACKS = {
    "track_1_shank2_genetics": {
        "id": 1,
        "name": "Pillar 1: SHANK2 & Exon 24 Genetics",
        "folder": "Shank2",
        "pubmed_query": (
            '("SHANK2"[Title/Abstract] OR "SHANK-2"[Title/Abstract] OR "ProSAP1"[Title/Abstract]) '
            'AND ("exon 24"[Title/Abstract] OR "ex24"[Title/Abstract] OR "splicing"[Title/Abstract] '
            'OR "isoform"[Title/Abstract] OR "knockout"[Title/Abstract] OR "mutation"[Title/Abstract])'
        ),
        "semantic_query": "SHANK2 exon 24 deletion alternative splicing knockout autism",
    },
    "track_2_acc_circuitry": {
        "id": 2,
        "name": "Pillar 2: ACC Synaptic Circuitry",
        "folder": "ACC_Circuitry",
        "pubmed_query": (
            '("SHANK2"[Title/Abstract] OR "Shank2"[Title/Abstract]) '
            'AND ("anterior cingulate"[Title/Abstract] OR "ACC"[Title/Abstract] OR "cingulate cortex"[Title/Abstract] '
            'OR "social behavior"[Title/Abstract] OR "prefrontal"[Title/Abstract])'
        ),
        "semantic_query": "SHANK2 anterior cingulate cortex synaptic transmission social behavior",
    },
    "track_3_psd_nanoscale": {
        "id": 3,
        "name": "Pillar 3: PSD Nanoscale Dynamics",
        "folder": "PSD_Nanoscale",
        "pubmed_query": (
            '("postsynaptic density"[Title/Abstract] OR "PSD"[Title/Abstract]) '
            'AND ("Homer1"[Title/Abstract] OR "Homer"[Title/Abstract]) '
            'AND ("GluN1"[Title/Abstract] OR "GluA1"[Title/Abstract] OR "GRIN1"[Title/Abstract] OR "GRIA1"[Title/Abstract] OR "NMDAR"[Title/Abstract] OR "AMPAR"[Title/Abstract])'
        ),
        "semantic_query": "postsynaptic density Homer1 GluN1 GluA1 nanodomain scaffolding AMPA NMDA",
    },
    "track_4_pan_exm_methods": {
        "id": 4,
        "name": "Pillar 4: Pan-ExM Protocols & Antibodies",
        "folder": "pan_ExM_References",
        "pubmed_query": (
            '("Pan-ExM"[Title/Abstract] OR "pan-expansion microscopy"[Title/Abstract] '
            'OR ("expansion microscopy"[Title/Abstract] AND "ultrastructure"[Title/Abstract])) '
            'AND ("antibody"[Title/Abstract] OR "antibodies"[Title/Abstract] OR "staining"[Title/Abstract] '
            'OR "NHS"[Title/Abstract] OR "validation"[Title/Abstract] OR "synapse"[Title/Abstract])'
        ),
        "semantic_query": "Pan-ExM pan-expansion microscopy antibody validation synapse ultrastructure NHS-ester",
    },
    "track_5_connectomics": {
        "id": 5,
        "name": "Pillar 5: Synaptic Connectomics",
        "folder": "Connectomics",
        "pubmed_query": (
            '("connectomics"[Title/Abstract] OR "synaptic connectivity"[Title/Abstract] '
            'OR "electron microscopy reconstruction"[Title/Abstract]) '
            'AND ("synapse"[Title/Abstract] OR "postsynaptic"[Title/Abstract] OR "neurodevelopmental"[Title/Abstract])'
        ),
        "semantic_query": "connectomics synaptic reconstruction neural circuit electron microscopy",
    },
}

# ---------------------------------------------------------
# 2. Zotero Tag Architecture (Strict Schema Mapping)
# ---------------------------------------------------------
ZOTERO_TAG_RULES = {
    # Tier 1: Project & Workflow Tags
    "status_tags": ["!unread", "#project-thesis"],
    # Tier 2: Biological Subjects & Gene Targets
    "genes_and_targets": {
        "SHANK2": ["shank2", "shank-2", "prosap1"],
        "shank2-exon24": ["exon 24", "ex24", "exon-24", "delta-ex24", "exon24"],
        "SHANK1": ["shank1", "shank-1"],
        "SHANK3": ["shank3", "shank-3"],
        "homer1": ["homer1", "homer-1", "homer"],
        "glun1": ["glun1", "grin1", "nmdar1", "nr1"],
        "glua1": ["glua1", "gria1", "glu-a1", "ampar1"],
        "postsynaptic-density": ["postsynaptic density", "psd", "psd-95", "dlg4"],
        "excitatory-synapses": ["excitatory synapse", "glutamatergic"],
        "cortactin": ["cortactin", "cttn"],
        "gephyrin": ["gephyrin", "gphn"],
        "mglur5": ["mglur5", "grm5"],
        "hippo-pathway": ["hippo signaling", "hippo pathway", "yap", "taz", "mst1", "mst2"],
    },
    # Tier 3: Disease & Phenotypic Context
    "disease_and_anatomy": {
        "ACC": ["anterior cingulate", "acc", "cingulate cortex"],
        "autism-spectrum-disorder": ["autism", "asd", "autistic"],
        "schizophrenia": ["schizophrenia", "psychosis"],
        "neurodevelopmental-disorders": ["neurodevelopmental", "ndd"],
        "synaptopathy": ["synaptopathy", "synaptic dysfunction", "synaptic deficit"],
    },
    # Tier 4: Methodological Framework
    "methods": {
        "pan-exm": ["pan-exm", "pan-expansion", "pan expansion microscopy"],
        "expansion-microscopy": ["expansion microscopy", "exm", "expansion pathology"],
        "antibody-validation": ["antibody validation", "epitope retention", "staining validation"],
        "connectomics": ["connectomics", "connectome", "wiring diagram"],
        "electron-microscopy": ["electron microscopy", "em reconstruction", "serial section em", "cryo-et"],
        "mouse-model": ["mouse model", "knockout mouse", "conditional knockout", "transgenic mouse", "shank2 ko"],
        "patch-clamp": ["patch-clamp", "patch clamp", "electrophysiology", "epsc", "ipsc", "whole-cell"],
        "ipsc": ["ipsc", "induced pluripotent", "human neuronal culture", "cortical organoid"],
        "rna-seq": ["rna-seq", "rnaseq", "transcriptomics", "single-cell rna", "scrna-seq"],
        "wes": ["whole exome sequencing", "wes", "cnv", "copy number variation", "de novo mutation"],
    },
}

LAB_MEMBER_NAME = os.getenv("LAB_MEMBER_NAME", "")
LAB_MEMBER_EMAIL = os.getenv("LAB_MEMBER_EMAIL", "")
PYTHON_EXE = os.getenv("PYTHON_EXE", sys.executable)

NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")
NCBI_EMAIL = os.getenv("NCBI_EMAIL", LAB_MEMBER_EMAIL)
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")

# Zotero: Local SQLite or Web API
ZOTERO_USER_ID = os.getenv("ZOTERO_USER_ID", "")
ZOTERO_API_KEY = os.getenv("ZOTERO_API_KEY", "")
DEFAULT_LOCAL_ZOTERO_DB = Path(os.environ.get("USERPROFILE", "")) / "Zotero" / "zotero.sqlite"
ZOTERO_DB_PATH = Path(os.getenv("ZOTERO_LOCAL_DB") or str(DEFAULT_LOCAL_ZOTERO_DB))

# Email Settings
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SENDER_GMAIL", os.getenv("SMTP_USER", ""))
SMTP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", os.getenv("SMTP_PASSWORD", ""))
EMAIL_RECIPIENT = os.getenv("RECIPIENT_EMAIL", os.getenv("EMAIL_RECIPIENT", ""))

# Gemini API Key (powers automated briefings & future LM podcasts)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


# ---------------------------------------------------------
# 4. Curated High-Impact Journals (Neuroscience & Imaging)
# ---------------------------------------------------------
TOP_TIER_JOURNALS = {
    # 1. Multidisciplinary Flagships
    "flagships": [
        "Nature", "Science", "Cell", "Nature Communications",
        "Science Advances", "PNAS", "Proc Natl Acad Sci U S A",
        "Proceedings of the National Academy of Sciences"
    ],
    # 2. Premier Neuroscience Venues (Synapse, Circuits, Autism)
    "neuroscience": [
        "Neuron", "Nature Neuroscience", "The Journal of Neuroscience",
        "J Neurosci", "Cell Reports", "Molecular Psychiatry",
        "Biological Psychiatry", "Brain", "eLife", "Trends in Neurosciences"
    ],
    # 3. Super-Resolution, Pan-ExM, Connectomics & Methods
    "methods_and_imaging": [
        "Nature Methods", "Nature Biotechnology", "The Journal of Cell Biology",
        "J Cell Biol", "Nano Letters", "ACS Nano", "Biophysical Journal"
    ],
    # 4. Synaptic Ultrastructure, Connectomics & EM Classics
    "ultrastructure_em": [
        "The Journal of Comparative Neurology", "J Comp Neurol",
        "Frontiers in Synaptic Neuroscience", "Neuroscience", "Synapse"
    ]
}

# Flattened list of high-impact journal names/abbreviations for matching and querying
ALL_TOP_JOURNALS = sorted(list(set(
    j for group in TOP_TIER_JOURNALS.values() for j in group
)))

