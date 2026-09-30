# LitRadar 📡
**Automated Literature Intelligence & Podcast Briefing Suite**

An automated, dummy-friendly literature intelligence and podcast briefing suite targeting:
* **Pillar 1: SHANK2 & Exon 24 Genetics** (including ProSAP1 / CortBP1 synonyms & splice variants)
* **Pillar 2: Anterior Cingulate Cortex (ACC) Synaptic Circuitry**
* **Pillar 3: Nanoscale Postsynaptic Density (Homer1, GluN1, GluA1, Scaffolding)**
* **Pillar 4: Pan-Expansion Microscopy (Pan-ExM) & Validated Antibodies**
* **Pillar 5: Synaptic Connectomics & 3D Circuit Reconstruction**

---

> [!TIP]
> **PRO-TIP FOR LAB MEMBERS & REPRODUCIBILITY:**
> Back up your `lab_config.env` file to your personal cloud drive or secure password vault.
> When you switch computers, log into a shared microscope computer, or onboard a new workstation, simply drop your saved `lab_config.env` into this folder and all scripts are 100% configured instantly!

---

## Quickstart for New Users / Fresh Clones

### Step 1: Clone the Repository
```bash
git clone https://github.com/allison714/LitRadar.git
cd LitRadar
```

### Step 2: Run First-Time Setup (Takes ~60 seconds)
Double-click **`00_First_Time_Setup.bat`** (or run `python core/setup_wizard.py`).
- The wizard automatically detects your Python/Anaconda environment, local Zotero database, and storage paths.
- Prompts for your name, recipient email (e.g., personal Gmail for weekly digests), and optional API keys.
- Tests your Zotero connection live and automatically installs missing Python packages.
- Generates your local `lab_config.env` (kept private by `.gitignore`).

### Step 3: Run Any Launcher (Just Double-Click!)
The root directory contains 1-click batch launchers:
* **`00_First_Time_Setup.bat`**: Interactive setup wizard (run whenever you need to update settings or onboard a new member).
* **`01_Find_New_Papers.bat`**: Interactive paper finder. Search Europe PMC & PubMed with Boolean logic, filter by 4 journal scopes (All, Paywall/Top-Tier Flagships via Institutional VPN, Free/Open Access, Custom), deduplicate against Zotero, download PDFs to storage vault, and import directly to Zotero Cloud.
* **`02_Retag_Zotero_Library.bat`**: Scans your entire 2,359+ Zotero library, filters out textbooks/books, detects matching literature, and uploads structured 4-tier tags to Zotero Cloud.
* **`03_Run_Weekly_Surveillance.bat`**: Full autonomous weekly pipeline run (harvests all 5 pillars, deduplicates, classifies, downloads PDFs, generates Excel knowledge base, and compiles podcast dossiers).
* **`04_Harvest_Foundational_Benchmarks.bat`**: Harvests the Top 20 all-time most-cited papers per pillar and generates 5 foundational "Master Class Intro" briefings for NotebookLM.
* **`05_Export_NotebookLM_Bundle.bat`**: Date inspector & PDF packager for NotebookLM. Search your Zotero library by exact upload/arrival date, bundle all PDFs into an upload folder, and generate synthesis notes.
* **`Setup_Weekly_Scheduler.bat`**: Schedules Windows Task Scheduler to run surveillance autonomously every Sunday at 11:00 PM.
* **`Run_Diagnostic_Test.bat`**: Quick 30-day diagnostic dry run to verify all systems.

---

## Directory Architecture
```
LitRadar/
├── 00_First_Time_Setup.bat             <-- [FIRST STEP] Interactive questionnaire & environment validator
├── 01_Find_New_Papers.bat              <-- [DAILY SEARCH] Boolean discovery & Institutional VPN / OA filter
├── 02_Retag_Zotero_Library.bat         <-- [LIBRARY CLEANER] Scans 2,359+ items & syncs tags to cloud
├── 03_Run_Weekly_Surveillance.bat      <-- [SURVEILLANCE] Full 5-pillar weekly harvest & digest
├── 04_Harvest_Foundational_Benchmarks.bat <-- [PRIMERS] Harvests Top 20 landmark papers & intro podcasts
├── 05_Export_NotebookLM_Bundle.bat     <-- [NOTEBOOKLM] Filters Zotero by upload date & bundles PDFs
├── Setup_Weekly_Scheduler.bat          <-- Installs Sunday 11:00 PM background Windows Task
├── Run_Diagnostic_Test.bat             <-- 30-day diagnostic dry run
├── lab_config.env.example              <-- Clean template for new users & git tracking
├── lab_config.env                      <-- Member profile & credentials (ignored by git - private!)
├── .gitignore                          <-- Protects credentials, databases, and temporary caches
├── README.md                           <-- Visual manual & onboarding instructions
├── LitRadar_Code_and_Architecture_Guide.md <-- Educational code walkthrough & architecture guide
├── core/                               <-- Engine & Python modules (tucked away)
│   ├── config.py                       <-- Master settings loader & journal tiers
│   ├── find_new_papers.py              <-- Discovery engine
│   ├── retag_zotero_library.py         <-- Zotero library tagger
│   ├── zotero_sync.py                  <-- Zotero SQLite & Web API sync
│   ├── pdf_downloader.py               <-- Institutional PDF resolver (Institutional VPN)
│   ├── harvester.py                    <-- Multi-engine search APIs
│   ├── classifier.py                   <-- 4-tier AI tagging engine
│   ├── excel_generator.py              <-- Excel knowledge base manager
│   ├── podcast_prep.py                 <-- NotebookLM briefing dossier builder
│   ├── export_lm_bundle.py             <-- NotebookLM bundle exporter by date
│   ├── email_digest.py                 <-- HTML email generator & SMTP dispatcher
│   ├── harvest_foundational.py         <-- Top 20 cited paper harvester
│   ├── setup_wizard.py                 <-- Interactive onboarding logic
│   ├── main.py                         <-- Orchestrator CLI
│   └── requirements.txt                <-- Python dependencies
├── output/                             <-- Generated Excel files & HTML digests
└── podcast_briefings/                  <-- Markdown briefing packets for NotebookLM Audio Overviews
```
