"""
Interactive Zotero Library Retagger & Topic Analyzer.
Scans your existing 2,359+ Zotero items, excludes textbooks/books,
identifies matching literature using customizable keywords, previews matches,
and updates your Zotero library with precise tags via the Zotero Web API.
"""

import sys
import re
import sqlite3
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Set, Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import ZOTERO_DB_PATH, ZOTERO_USER_ID, ZOTERO_API_KEY, OUTPUT_DIR

# Preset Topic Profiles
PRESETS = {
    "1": {
        "name": "SHANK2 (and related isoforms)",
        "tag_to_apply": "SHANK2",
        "keywords": ["shank2", "shank-2", "prosap1", "shank 2"],
        "sub_rules": {
            "shank2-exon24": ["exon 24", "ex24", "exon-24", "delta-ex24", "exon24"],
        }
    },
    "2": {
        "name": "Expansion Microscopy / Pan-ExM",
        "tag_to_apply": "expansion-microscopy",
        "keywords": ["expansion microscopy", "exm", "pan-exm", "proexm", "pro-exm", "expansion pathology", "hydrogel expansion"],
        "sub_rules": {
            "pan-exm": ["pan-exm", "pan expansion", "pan-expansion", "bulk proteome expansion"],
            "antibody-validation": ["antibody validation", "epitope retention", "staining validation"]
        }
    },
    "3": {
        "name": "Connectomics & Circuit Reconstruction",
        "tag_to_apply": "connectomics",
        "keywords": ["connectomics", "connectome", "synaptic reconstruction", "em reconstruction", "wiring diagram", "synaptic connectivity"],
        "sub_rules": {}
    },
    "4": {
        "name": "Postsynaptic Density (Homer1, GluN1, GluA1 Scaffolding)",
        "tag_to_apply": "postsynaptic-density",
        "keywords": ["postsynaptic density", "psd-95", "homer1", "homer", "glun1", "glua1", "mglur5"],
        "sub_rules": {
            "homer1": ["homer1", "homer-1"],
            "glun1": ["glun1", "grin1", "nmdar1"],
            "glua1": ["glua1", "gria1", "ampar1"]
        }
    },
    "5": {
        "name": "Anterior Cingulate Cortex (ACC)",
        "tag_to_apply": "ACC",
        "keywords": ["anterior cingulate", "acc", "cingulate cortex"],
        "sub_rules": {}
    }
}


def parse_keyword_query(query_str: str) -> List[List[str]]:
    """
    Parses a query string into keyword groups for boolean AND / OR search.
    Clauses separated by 'AND', '&', or '+' must ALL match (Conjunctive / AND).
    Within each clause, terms separated by comma ',' are synonyms (Disjunctive / OR).
    Strips surrounding quotes, parentheses, and extra whitespace.
    """
    pattern = r'''(?:\s+(?:AND|&|\+)\s+|\s+and\s+(?=(?:[^"]*"[^"]*")*[^"]*$))'''
    raw_clauses = re.split(pattern, query_str.strip())
    groups = []
    for clause in raw_clauses:
        clause = clause.strip()
        clause = re.sub(r'^[(\"\'\s]+|[)\"\'\s]+$', '', clause).strip()
        terms = [re.sub(r'^[(\"\'\s]+|[)\"\'\s]+$', '', t).strip().lower() for t in clause.split(',') if t.strip()]
        terms = [t for t in terms if t]
        if terms:
            groups.append(terms)
    return groups


class ZoteroRetagger:
    def __init__(self):
        self.db_path = ZOTERO_DB_PATH
        self.user_id = ZOTERO_USER_ID
        self.api_key = ZOTERO_API_KEY
        self.zot = None
        self._init_api()

    def _init_api(self):
        if self.user_id and self.api_key:
            try:
                from pyzotero import zotero
                self.zot = zotero.Zotero(self.user_id, "user", self.api_key)
            except Exception as e:
                print(f"[Warning] Could not initialize Zotero Web API: {e}")

    def load_library_excluding_textbooks(self) -> List[Dict[str, Any]]:
        """Query local zotero.sqlite in high-speed immutable mode, explicitly excluding textbooks."""
        conn = None
        temp_dir = None
        items = []
        try:
            try:
                conn = sqlite3.connect(f"file:{self.db_path}?mode=ro&immutable=1", uri=True)
            except Exception:
                temp_dir = tempfile.mkdtemp()
                temp_db = Path(temp_dir) / "zotero_scan.sqlite"
                shutil.copy2(self.db_path, temp_db)
                conn = sqlite3.connect(f"file:{temp_db}?mode=ro", uri=True)

            cursor = conn.cursor()

            # Find Textbook Collection IDs to exclude
            cursor.execute("""
                SELECT collectionID FROM collections 
                WHERE LOWER(collectionName) LIKE '%textbook%' 
                   OR LOWER(collectionName) LIKE '%texts%'
                   OR LOWER(collectionName) LIKE '%stanford%'
            """)
            excluded_col_ids = {row[0] for row in cursor.fetchall()}

            # Find Item IDs inside excluded collections
            excluded_item_ids = set()
            if excluded_col_ids:
                placeholders = ",".join("?" * len(excluded_col_ids))
                cursor.execute(f"SELECT itemID FROM collectionItems WHERE collectionID IN ({placeholders})", list(excluded_col_ids))
                excluded_item_ids = {row[0] for row in cursor.fetchall()}

            # Query all items with their itemType
            cursor.execute("""
                SELECT i.itemID, i.key, it.typeName
                FROM items i
                JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
                WHERE it.typeName NOT IN ('attachment', 'note', 'book', 'bookSection', 'dictionaryEntry', 'encyclopediaArticle')
                  AND i.itemID NOT IN (SELECT itemID FROM deletedItems)
            """)
            candidate_rows = cursor.fetchall()

            for item_id, item_key, type_name in candidate_rows:
                if item_id in excluded_item_ids:
                    continue

                # Fetch Title, Abstract, Extra, DOI
                cursor.execute("""
                    SELECT f.fieldName, iv.value
                    FROM itemData id
                    JOIN fields f ON id.fieldID = f.fieldID
                    JOIN itemDataValues iv ON id.valueID = iv.valueID
                    WHERE id.itemID = ? AND f.fieldName IN ('title', 'abstractNote', 'extra', 'DOI', 'date')
                """, (item_id,))

                fields_dict = {f_name: val for f_name, val in cursor.fetchall()}
                title = fields_dict.get("title", "")
                abstract = fields_dict.get("abstractNote", "")
                doi = fields_dict.get("DOI", "")
                date_val = fields_dict.get("date", "")

                # Fetch existing tags
                cursor.execute("""
                    SELECT t.name
                    FROM itemTags it
                    JOIN tags t ON it.tagID = t.tagID
                    WHERE it.itemID = ?
                """, (item_id,))
                existing_tags = [row[0] for row in cursor.fetchall()]

                items.append({
                    "item_id": item_id,
                    "key": item_key,
                    "type": type_name,
                    "title": title,
                    "abstract": abstract,
                    "doi": doi,
                    "date": date_val,
                    "existing_tags": existing_tags,
                })

            conn.close()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return items

    def scan_for_topic(
        self,
        items: List[Dict[str, Any]],
        keyword_groups: Any,
        primary_tag: str,
        sub_rules: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:
        """Identify matching papers based on title and abstract text with boolean logic support."""
        # Normalize keyword_groups: if a flat list of strings was passed, wrap in outer list
        if keyword_groups and isinstance(keyword_groups[0], str):
            groups = [keyword_groups]
        else:
            groups = keyword_groups or []

        group_patterns = []
        for grp in groups:
            if grp:
                pat = re.compile(r"\b(" + "|".join(re.escape(k.lower()) for k in grp) + r")\b", re.IGNORECASE)
                group_patterns.append(pat)

        matches = []
        for item in items:
            combined = f"{item['title']}\n{item['abstract']}"
            # ALL groups must match (Conjunctive AND logic)
            if group_patterns and all(pat.search(combined) for pat in group_patterns):
                tags_to_add = set()
                if primary_tag not in item["existing_tags"]:
                    tags_to_add.add(primary_tag)

                # Check sub-rules (e.g. exon 24 or pan-exm specific)
                for sub_tag, sub_kws in sub_rules.items():
                    sub_pat = re.compile(r"\b(" + "|".join(re.escape(k.lower()) for k in sub_kws) + r")\b", re.IGNORECASE)
                    if sub_pat.search(combined) and sub_tag not in item["existing_tags"]:
                        tags_to_add.add(sub_tag)

                matches.append({
                    "key": item["key"],
                    "title": item["title"],
                    "date": item["date"],
                    "existing_tags": item["existing_tags"],
                    "new_tags": sorted(list(tags_to_add)),
                    "already_tagged": primary_tag in item["existing_tags"],
                })

        return matches

    def apply_tags_to_zotero(self, candidates_to_update: List[Dict[str, Any]]) -> int:
        """Apply new tags via Zotero Web API in batches."""
        if not self.zot:
            print("[Error] Zotero API credentials not found. Cannot push updates to cloud.")
            return 0

        updated_count = 0
        total = len(candidates_to_update)
        print(f"\n[Updating Zotero Cloud] Pushing new tags to {total} items...")

        for idx, cand in enumerate(candidates_to_update, start=1):
            item_key = cand["key"]
            tags_to_add = cand["new_tags"]

            if not tags_to_add:
                continue

            try:
                # Fetch live item from cloud
                item = self.zot.item(item_key)
                existing = [t["tag"] for t in item["data"].get("tags", [])]
                for nt in tags_to_add:
                    if nt not in existing:
                        existing.append(nt)

                item["data"]["tags"] = [{"tag": t} for t in existing]
                self.zot.update_item(item)
                updated_count += 1
                print(f"    [{idx}/{total}] Tagged: {cand['title'][:55]}... (+{', '.join(tags_to_add)})")
            except Exception as e:
                print(f"    [Error updating {item_key}]: {e}")

        return updated_count


def interactive_menu():
    print("=" * 70)
    print("      Interactive Zotero Library Retagger & Topic Analyzer")
    print("=" * 70)
    print("\nSelect a Topic to Scan and Tag:")
    for key, p in PRESETS.items():
        print(f"  [{key}] {p['name']} (Tag: '{p['tag_to_apply']}')")
    print("  [C] Custom Topic / Custom Keywords")
    print("  [Q] Quit")

    choice = input("\nEnter your choice (default [1]): ").strip().upper()
    if not choice:
        choice = "1"

    if choice == "Q":
        print("Exiting.")
        return

    if choice in PRESETS:
        profile = PRESETS[choice]
        primary_tag = profile["tag_to_apply"]
        keyword_groups = [profile["keywords"]]
        sub_rules = profile.get("sub_rules", {})
    elif choice == "C":
        print("\n" + "=" * 70)
        print("                 --- CUSTOM TOPIC SETUP ---")
        print("=" * 70)
        print("Format Guidelines:")
        print("  - Use 'AND', '&', or '+' to require multiple concepts together.")
        print("  - Separate synonyms/variations with commas ',' (acts as OR).")
        print("  - Quotes \"\" or parentheses () are optional and automatically supported.")
        print("-" * 70)
        print("Scientific Search Note:")
        print("  When searching scientific databases for Shank2 and EM, note that SHANK2 was")
        print("  originally cloned and characterized as ProSAP1 (Proline-rich Synapse-Associated")
        print("  Protein 1) and CortBP1 (Cortactin-Binding Protein 1). Including these synonyms")
        print("  uncovers the foundational ultrastructure and immunogold studies.")
        print("-" * 70)
        print("Examples:")
        print()
        print("  [Example 1: Shank2 + Electron Microscopy / Ultrastructure]")
        print("    Tag:      Shank2-Ultrastructure")
        print("    Keywords: (Shank2, Shank-2, ProSAP1) AND (Electron Microscopy, EM, TEM, Cryo-EM, ultrastructure)")
        print()
        print("  [Example 2: Shank2 + Receptor Subtypes / NMDA]")
        print("    Tag:      Shank2-NMDA")
        print("    Keywords: (Shank2, Shank-2) AND (NMDA, GluN1, GluN2B, NMDAR)")
        print()
        print("  [Single Topic / OR Search]")
        print("    Tag:      patch-clamp")
        print("    Keywords: patch clamp, whole-cell, electrophysiology, epsc, ipsc")
        print("-" * 70)

        raw_tag = input("Enter tag to apply (e.g., 'Shank2-Ultrastructure', 'Shank2-NMDA'): ").strip()
        primary_tag = raw_tag.strip("\"' ")

        raw_kw = input("Enter search keywords (use 'AND' to combine concepts): ").strip()
        keyword_groups = parse_keyword_query(raw_kw)
        sub_rules = {}

        if not primary_tag or not keyword_groups:
            print("\n[Error] Tag and keywords cannot be empty. Aborting.")
            input("\nPress Enter to exit...")
            return
    else:
        print("Invalid selection. Aborting.")
        return

    print(f"\n[Scanning Profile] Primary Tag: '{primary_tag}'")
    if len(keyword_groups) > 1:
        print("                  Search Logic: Boolean AND across conditions:")
        for idx, grp in enumerate(keyword_groups, 1):
            print(f"                    Condition {idx} (MUST match any): {grp}")
    else:
        print(f"                  Keywords (match any): {keyword_groups[0]}")

    # Run Scanner
    retagger = ZoteroRetagger()
    print("\n[Step 1/3] Loading non-textbook items from local library...")
    items = retagger.load_library_excluding_textbooks()
    print(f"--> Loaded {len(items):,} journal/research items (Textbooks successfully excluded).")

    print(f"\n[Step 2/3] Scanning for matches against '{primary_tag}'...")
    matches = retagger.scan_for_topic(items, keyword_groups, primary_tag, sub_rules)

    already_tagged = [m for m in matches if m["already_tagged"]]
    need_tagging = [m for m in matches if not m["already_tagged"] or m["new_tags"]]

    print("\n" + "-" * 70)
    print(f"SCAN RESULTS:")
    print(f"  • Total Papers Matching Keywords:  {len(matches):,}")
    print(f"  • Already Have Tag '{primary_tag}':        {len(already_tagged):,}")
    print(f"  • Candidates Needing New Tags:     {len(need_tagging):,}")
    print("-" * 70)

    if not need_tagging:
        print(f"\nAll {len(matches)} matching papers in your library already have the '{primary_tag}' tag! No updates needed.")
        input("\nPress Enter to exit...")
        return

    # Preview
    print(f"\n--- Sample Matches Needing Tagging (Top 10 of {len(need_tagging)}) ---")
    for idx, cand in enumerate(need_tagging[:10], start=1):
        print(f" {idx}. [{cand.get('date', 'Unknown')[:4]}] {cand['title'][:70]}")
        print(f"    Tags to Add: {cand['new_tags']}")

    # Ask for confirmation
    print("\n" + "=" * 70)
    confirm = input(f"Do you want to apply these tags to all {len(need_tagging)} items in Zotero Cloud? (y/N): ").strip().lower()
    if confirm == "y":
        updated = retagger.apply_tags_to_zotero(need_tagging)
        print(f"\n[Done!] Successfully updated {updated} items in your Zotero Library.")
        print("Click the Sync button in Zotero Desktop to see the newly tagged items!")
    else:
        print("\nOperation cancelled. No changes were made to your library.")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    interactive_menu()
