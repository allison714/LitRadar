"""
Zotero Deduplication and Bi-Directional Sync Module.
Supports:
1. Safe read-only inspection of local zotero.sqlite (deduplicates against all 2,359+ items).
2. Bulletproof Zotero Web API import directly into specific Collection IDs.
3. Offline .ris backup generator for 1-click native import.
"""

import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import List, Dict, Set, Any, Optional

from config import ZOTERO_DB_PATH, ZOTERO_USER_ID, ZOTERO_API_KEY, OUTPUT_DIR

# Your exact Zotero Cloud Collection Keys (Unified 5 Pillars)
COLLECTION_MAPPING = {
    "shank2": "UAJ8BK85",            # Shank2 folder
    "shank2_isoforms": "8SMQBACC",  # Shank2 Isoforms folder
    "acc_circuitry": "8M4HXIPP",     # ACC Circuitry folder (under Neuro)
    "psd_nanoscale": "9HE6B2MS",     # PSD Nanoscale folder (under ExM)
    "pan_exm": "MZ37DCHK",           # pan-ExM References (under ExM)
    "connectomics": "9BIMSI9V",      # Connectomics folder (under Neuro)
}


class ZoteroSync:
    def __init__(self):
        self.known_dois: Set[str] = set()
        self.known_pmids: Set[str] = set()
        self.known_titles: Set[str] = set()
        self.zot = None
        self._init_zotero_api()
        self._load_existing_library()

    def _init_zotero_api(self):
        if ZOTERO_USER_ID and ZOTERO_API_KEY:
            try:
                from pyzotero import zotero
                self.zot = zotero.Zotero(ZOTERO_USER_ID, "user", ZOTERO_API_KEY)
                print("[ZoteroSync] Connected to Zotero Web API.")
            except Exception as e:
                print(f"[ZoteroSync] Web API initialization error: {e}")

    def _normalize_title(self, title: str) -> str:
        import re
        return re.sub(r"[^a-zA-Z0-9]", "", title).lower()

    def _load_existing_library(self):
        # 1. Local SQLite read (fastest, covers all 2,359 items)
        if ZOTERO_DB_PATH.exists():
            print(f"[ZoteroSync] Reading existing library from: {ZOTERO_DB_PATH}")
            self._read_local_sqlite(ZOTERO_DB_PATH)
        elif self.zot:
            self._read_web_api()
        else:
            print("[ZoteroSync] Running in fresh-session mode.")

    def _read_local_sqlite(self, db_path: Path):
        """Read local zotero.sqlite in high-speed immutable mode, falling back to temp copy if locked."""
        conn = None
        temp_dir = None
        try:
            # 1. High-speed direct immutable read (sub-millisecond, zero file copying)
            try:
                conn = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
            except Exception:
                # Fallback: copy to temp if file locked
                temp_dir = tempfile.mkdtemp()
                temp_db = Path(temp_dir) / "zotero_temp.sqlite"
                shutil.copy2(db_path, temp_db)
                conn = sqlite3.connect(f"file:{temp_db}?mode=ro", uri=True)

            cursor = conn.cursor()
            query = """
                SELECT f.fieldName, iv.value
                FROM itemData id
                JOIN fields f ON id.fieldID = f.fieldID
                JOIN itemDataValues iv ON id.valueID = iv.valueID
                WHERE f.fieldName IN ('DOI', 'title', 'extra', 'url')
            """
            cursor.execute(query)
            for field_name, value in cursor.fetchall():
                val_str = str(value).strip()
                if field_name == "DOI" and val_str:
                    self.known_dois.add(val_str.lower().strip())
                elif field_name == "title" and val_str:
                    self.known_titles.add(self._normalize_title(val_str))
                elif field_name == "extra" and val_str:
                    import re
                    match = re.search(r"PMID:\s*(\d+)", val_str, re.IGNORECASE)
                    if match:
                        self.known_pmids.add(match.group(1).strip())

            conn.close()
            print(f"[ZoteroSync] Successfully indexed {len(self.known_dois)} DOIs, {len(self.known_pmids)} PMIDs, and {len(self.known_titles)} titles from your library.")

        except Exception as e:
            print(f"[ZoteroSync] Error reading SQLite database: {e}")
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _read_web_api(self):
        try:
            items = self.zot.everything(self.zot.items())
            for item in items:
                data = item.get("data", {})
                doi = data.get("DOI", "").lower().strip()
                if doi:
                    self.known_dois.add(doi)
                title = data.get("title", "")
                if title:
                    self.known_titles.add(self._normalize_title(title))
        except Exception as e:
            print(f"[ZoteroSync Web API Read Error] {e}")

    def filter_new_papers(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        new_papers = []
        for paper in papers:
            doi = paper.get("doi", "").lower().strip()
            pmid = str(paper.get("pmid", "")).strip()
            norm_title = self._normalize_title(paper.get("title", ""))

            if doi and doi in self.known_dois:
                continue
            if pmid and pmid in self.known_pmids:
                continue
            if norm_title and norm_title in self.known_titles:
                continue

            new_papers.append(paper)

        return new_papers

    def add_to_known(self, paper: Dict[str, Any]):
        if paper.get("doi"):
            self.known_dois.add(paper["doi"].lower().strip())
        if paper.get("pmid"):
            self.known_pmids.add(str(paper["pmid"]).strip())
        if paper.get("title"):
            self.known_titles.add(self._normalize_title(paper["title"]))

    # -------------------------------------------------------------
    # Dual-Mode Export & Sync
    # -------------------------------------------------------------
    def sync_new_papers(self, papers: List[Dict[str, Any]]):
        """Execute both Option A (offline .ris file) and Option B (Zotero Web API)."""
        if not papers:
            return

        # 1. Option A: Always create the offline .ris backup file
        self._export_ris_file(papers)

        # 2. Option B: If API is configured, push directly into target collections
        if self.zot:
            self._import_via_web_api(papers)
        else:
            print("[ZoteroSync] Notice: ZOTERO_API_KEY not configured. To auto-inject into your app, add your key to config.py.")

    def _export_ris_file(self, papers: List[Dict[str, Any]]):
        """Export papers to standard .ris format with tags and abstracts."""
        ris_path = OUTPUT_DIR / "weekly_arrivals.ris"
        lines = []

        for p in papers:
            lines.append("TY  - JOUR")
            lines.append(f"TI  - {p.get('title', '')}")
            lines.append(f"JO  - {p.get('journal', '')}")
            lines.append(f"PY  - {p.get('year', '')}")
            if p.get("doi"):
                lines.append(f"DO  - {p.get('doi')}")
            if p.get("url"):
                lines.append(f"UR  - {p.get('url')}")
            if p.get("local_pdf_path"):
                lines.append(f"L1  - {p.get('local_pdf_path')}")
            if p.get("abstract"):
                lines.append(f"AB  - {p.get('abstract')}")
            for tag in p.get("tags", []):
                lines.append(f"KW  - {tag}")
            lines.append("ER  - \n")

        with open(ris_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"[ZoteroSync Option A] Created offline import file: {ris_path}")

    def push_to_zotero_cloud(self, papers: List[Dict[str, Any]], target_collection_key: Optional[str] = None) -> int:
        """
        Push items via Zotero Web API directly into matching collections,
        and attach downloaded local PDFs to the newly created Zotero items.
        """
        if not self.zot:
            print("[Zotero Cloud Error] Zotero API not authenticated. Check ZOTERO_API_KEY in config.py.")
            return 0
        if not papers:
            return 0

        print(f"\n[Zotero Cloud Push] Uploading {len(papers)} papers into Zotero Cloud...")
        success_count = 0

        for idx, p in enumerate(papers, start=1):
            try:
                tpl = self.zot.item_template("journalArticle")
                tpl["title"] = p.get("title", "")
                tpl["publicationTitle"] = p.get("journal", "")
                tpl["date"] = str(p.get("year", ""))
                tpl["DOI"] = p.get("doi", "")
                tpl["url"] = p.get("url", "")
                tpl["abstractNote"] = p.get("abstract", "")
                if p.get("pmid"):
                    tpl["extra"] = f"PMID: {p['pmid']}"

                # Parse authors
                raw_authors = p.get("authors", "")
                if raw_authors:
                    creators = []
                    # Split on semicolons or commas if no semicolons
                    delimiter = ";" if ";" in raw_authors else ","
                    for auth in raw_authors.split(delimiter):
                        auth = auth.strip()
                        if not auth:
                            continue
                        name_parts = auth.split()
                        if len(name_parts) >= 2:
                            creators.append({
                                "creatorType": "author",
                                "lastName": name_parts[-1].strip(),
                                "firstName": " ".join(name_parts[:-1]).strip()
                            })
                        else:
                            creators.append({
                                "creatorType": "author",
                                "name": auth
                            })
                    if creators:
                        tpl["creators"] = creators[:20]  # Cap at 20 authors to avoid API payload bloat

                # Tags
                tags_to_apply = p.get("tags", [])
                tpl["tags"] = [{"tag": t} for t in tags_to_apply]

                # Target Collection
                collections = []
                if target_collection_key:
                    collections.append(target_collection_key)
                else:
                    tags_str = " ".join(tags_to_apply).lower()
                    title_str = p.get("title", "").lower()
                    track_name = p.get("track_name", "").lower()

                    if "shank2-exon24" in tags_str or "exon 24" in title_str:
                        collections.append(COLLECTION_MAPPING.get("shank2_isoforms", "UAJ8BK85"))
                    elif "shank2" in tags_str or "shank2" in title_str or "shank2" in track_name:
                        collections.append(COLLECTION_MAPPING.get("shank2", "UAJ8BK85"))
                    elif "acc" in tags_str or "anterior cingulate" in title_str or "acc" in track_name:
                        collections.append(COLLECTION_MAPPING.get("acc_circuitry", "8M4HXIPP"))
                    elif "pan-exm" in tags_str or "pan-exm" in title_str or "pan-exm" in track_name:
                        collections.append(COLLECTION_MAPPING.get("pan_exm", "MZ37DCHK"))
                    elif "homer1" in tags_str or "glun1" in tags_str or "glua1" in tags_str or "postsynaptic-density" in tags_str or "psd" in track_name:
                        collections.append(COLLECTION_MAPPING.get("psd_nanoscale", "9HE6B2MS"))
                    elif "connectomics" in tags_str or "connectomics" in title_str or "connectomics" in track_name:
                        collections.append(COLLECTION_MAPPING.get("connectomics", "9BIMSI9V"))

                tpl["collections"] = collections

                # Create item on Zotero Cloud
                resp = self.zot.create_items([tpl])
                created_key = None
                if isinstance(resp, dict) and resp.get("success"):
                    created_key = list(resp["success"].values())[0]
                elif isinstance(resp, list) and len(resp) > 0:
                    created_key = resp[0].get("key")

                if created_key:
                    success_count += 1
                    self.add_to_known(p)
                    safe_title = p.get('title', '')[:55].encode('ascii', 'replace').decode('ascii')
                    print(f"    [{idx}/{len(papers)}] Pushed to Zotero Cloud: {safe_title}... (Item: {created_key})")

                    # If local PDF exists, attach to Zotero item
                    local_pdf = p.get("local_pdf_path")
                    if local_pdf and Path(local_pdf).exists():
                        try:
                            print(f"        Attaching PDF {Path(local_pdf).name} to Zotero Cloud item...")
                            self.zot.attachment_simple([str(local_pdf)], parentid=created_key)
                            print(f"        [+] PDF attached successfully!")
                        except Exception as att_err:
                            print(f"        [Notice] Cloud PDF attachment: {att_err}")
                else:
                    err_detail = resp.get("failed") if isinstance(resp, dict) else resp
                    print(f"    [-] Failed to push item {idx}: {err_detail}")

            except Exception as e:
                print(f"    [Zotero Push Error on item {idx}]: {e}")

        # Export local offline .ris backup
        try:
            self._export_ris_file(papers)
        except Exception:
            pass

        return success_count

    def _import_via_web_api(self, papers: List[Dict[str, Any]]):
        """Legacy helper: forwards to push_to_zotero_cloud."""
        self.push_to_zotero_cloud(papers)
