"""
LitRadar - NotebookLM Bundle Exporter.
Allows querying Zotero by exact date added / date uploaded,
collects all matching PDFs from Zotero storage & local vaults,
and creates a clean drag-and-drop folder for Google NotebookLM.
"""

import os
import shutil
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from config import ZOTERO_DB_PATH, OUTPUT_DIR, PODCAST_DIR, PDF_STORAGE_DIR


class NotebookLMBundleExporter:
    def __init__(self, zotero_db_path: Path = ZOTERO_DB_PATH):
        self.db_path = zotero_db_path
        self.zotero_dir = self.db_path.parent
        self.storage_dir = self.zotero_dir / "storage"

    def _query_zotero(self, sql: str, params: tuple = ()) -> List[tuple]:
        """Query local Zotero SQLite database safely in read-only immutable mode."""
        if not self.db_path.exists():
            return []
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro&immutable=1", uri=True)
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_papers_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        tag_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract items added to Zotero between start_date and end_date.
        Resolves titles, years, DOIs, dateAdded, and local PDF file paths.
        """
        start_str = start_date.strftime("%Y-%m-%d 00:00:00")
        end_str = end_date.strftime("%Y-%m-%d 23:59:59")

        # Query top-level non-attachment items added in date range
        # itemTypeID 14 = attachment, 1 = note, 28/37/etc = journalArticle/book
        sql = """
            SELECT i.itemID, i.key, i.dateAdded, it.typeName
            FROM items i
            JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
            WHERE it.typeName NOT IN ('attachment', 'note', 'annotation')
              AND i.dateAdded >= ? AND i.dateAdded <= ?
            ORDER BY i.dateAdded DESC
        """
        item_rows = self._query_zotero(sql, (start_str, end_str))
        if not item_rows:
            return []

        papers = []
        for item_id, item_key, date_added, type_name in item_rows:
            # Get metadata (Title, DOI, Date/Year, PublicationTitle)
            meta_sql = """
                SELECT f.fieldName, iv.value
                FROM itemData id
                JOIN fields f ON id.fieldID = f.fieldID
                JOIN itemDataValues iv ON id.valueID = iv.valueID
                WHERE id.itemID = ?
            """
            meta_rows = self._query_zotero(meta_sql, (item_id,))
            meta = {k: v for k, v in meta_rows}

            title = meta.get("title", "Untitled")
            doi = meta.get("DOI", "")
            year = meta.get("date", "")[:4]
            journal = meta.get("publicationTitle", "")
            extra = meta.get("extra", "")

            # Get Tags
            tag_sql = """
                SELECT t.name
                FROM itemTags it
                JOIN tags t ON it.tagID = t.tagID
                WHERE it.itemID = ?
            """
            tags = [r[0] for r in self._query_zotero(tag_sql, (item_id,))]

            if tag_filter and not any(tag_filter.lower() in t.lower() for t in tags):
                continue

            # Locate attached PDF
            # Check Zotero Storage attachments
            attach_sql = """
                SELECT ia.itemID, ia.path, ia.contentType, i_att.key
                FROM itemAttachments ia
                JOIN items i_att ON ia.itemID = i_att.itemID
                WHERE ia.parentItemID = ?
            """
            attach_rows = self._query_zotero(attach_sql, (item_id,))

            pdf_path = None
            for _, att_path, content_type, att_key in attach_rows:
                if att_path and "pdf" in str(att_path).lower():
                    clean_filename = att_path.replace("storage:", "").strip()
                    candidate = self.storage_dir / att_key / clean_filename
                    if candidate.exists():
                        pdf_path = candidate
                        break
                    # Search entire subfolder if filename slightly different
                    folder = self.storage_dir / att_key
                    if folder.exists():
                        pdfs = list(folder.glob("*.pdf"))
                        if pdfs:
                            pdf_path = pdfs[0]
                            break

            # Fallback: check Scientific Journals vault
            if not pdf_path and PDF_STORAGE_DIR.exists():
                safe_title_slug = "".join(c for c in title if c.isalnum() or c in " _-")[:30].strip()
                if safe_title_slug:
                    matches = list(PDF_STORAGE_DIR.rglob(f"*{safe_title_slug}*.pdf"))
                    if matches:
                        pdf_path = matches[0]

            papers.append({
                "item_id": item_id,
                "key": item_key,
                "title": title,
                "doi": doi,
                "year": year,
                "journal": journal,
                "extra": extra,
                "tags": tags,
                "date_added": date_added,
                "pdf_path": pdf_path,
            })

        return papers

    def create_notebook_lm_bundle(
        self,
        papers: List[Dict[str, Any]],
        bundle_name: Optional[str] = None
    ) -> Path:
        """
        Copies all matched PDFs into a designated bundle folder,
        and generates a formatted Bundle_Overview.md for NotebookLM.
        """
        today_slug = datetime.now().strftime("%Y-%m-%d")
        if not bundle_name:
            bundle_name = f"NotebookLM_Bundle_{today_slug}"

        bundle_dir = OUTPUT_DIR / bundle_name
        bundle_dir.mkdir(parents=True, exist_ok=True)

        copied_count = 0
        summary_lines = [
            f"# 📚 Literature Synthesis Bundle for Google NotebookLM",
            f"> **Generated by LitRadar** • {datetime.now().strftime('%B %d, %Y')}",
            f"> **Total Papers in Bundle:** {len(papers)}\n",
            f"---",
            f"## 📋 Included Papers & Key Metadata\n",
        ]

        for idx, p in enumerate(papers, start=1):
            pdf_status = "❌ No Local PDF"
            local_filename = ""
            if p.get("pdf_path") and Path(p["pdf_path"]).exists():
                src_path = Path(p["pdf_path"])
                dest_filename = f"{idx:02d}_{src_path.name}"
                dest_path = bundle_dir / dest_filename
                shutil.copy2(src_path, dest_path)
                pdf_status = f"✅ `{dest_filename}`"
                local_filename = dest_filename
                copied_count += 1

            date_str = p.get("date_added", "")[:10]
            tags_str = ", ".join(f"`{t}`" for t in p.get("tags", [])) or "None"

            summary_lines.append(f"### {idx}. {p.get('title', 'Untitled')}")
            summary_lines.append(f"- **Journal & Year:** *{p.get('journal', 'Unknown')}* ({p.get('year', 'N/A')})")
            summary_lines.append(f"- **DOI:** [{p.get('doi', 'N/A')}](https://doi.org/{p.get('doi', '')})")
            summary_lines.append(f"- **Date Added to Zotero:** `{date_str}`")
            summary_lines.append(f"- **Tags:** {tags_str}")
            summary_lines.append(f"- **PDF File:** {pdf_status}\n")

        summary_lines.extend([
            "---",
            "## 💡 Suggested NotebookLM Audio Overview & Research Prompts",
            "Paste these into NotebookLM chat after adding the PDFs:\n",
            "1. **Audio Overview Custom Focus:**",
            "   > *'Focus the deep dive on methodological innovations, compare mechanistic models across the authors, and highlight unanswered biological questions.'*",
            "2. **Cross-Study Synthesis:**",
            "   > *'Synthesize the key findings across all attached papers. Where do the authors agree, and what are the primary contradictions or divergent findings?'*",
            "3. **Experimental Takeaways:**",
            "   > *'What specific antibodies, imaging protocols, or genetic constructs were utilized that could be applied in our lab workflows?'*\n",
        ])

        overview_path = bundle_dir / "00_Bundle_Overview_for_NotebookLM.md"
        with open(overview_path, "w", encoding="utf-8") as f:
            f.write("\n".join(summary_lines))

        # Also write a dedicated, click-to-copy prompts file inside the bundle
        prompts_path = bundle_dir / "01_NotebookLM_CopyPaste_Prompts.md"
        prompts_content = """# 📋 Ready-to-Copy Prompts for this NotebookLM Bundle

## 🎙️ Option 1: Custom Audio Overview (Podcast) Prompt
*Paste into: Audio Overview -> Customize (Pencil icon)*

```text
Act as two senior principal investigators and neurobiologists leading a high-level journal club. Focus the discussion on:
1. The exact mechanistic claims made regarding synaptic scaffolding (SHANK2/Homer1/GluN1) and circuitry (ACC/Connectomics).
2. Methodological rigor: Scrutinize imaging techniques (especially Pan-Expansion Microscopy / super-resolution), sample sizes, antibody validation, and controls.
3. Healthy scientific disagreement: Have the two hosts debate whether the authors' conclusions are fully justified or if alternative interpretations exist.
4. Conclude with 2 active-recall questions for the listener.
```

---

## 💬 Option 2: Cross-Study Synthesis Table
*Paste into: NotebookLM Chat window*

```text
Generate a comprehensive cross-study comparison table for all uploaded papers with these columns:
- Study (First Author, Year)
- Primary Biological Question
- Key Experimental Model (e.g. KO mice, cell culture)
- Core Finding / Molecular Mechanism
- Methodological Innovations & Limitations
Summarize where these studies agree and where they contradict each other.
```

---

## 🔬 Option 3: Antibody & Protocol Extraction (For Pan-ExM)
*Paste into: NotebookLM Chat window*

```text
Extract all antibodies, fluorophores, expansion microscopy gels/clearing chemistry, and imaging protocols described in these papers. Format as a clean table: Target Antigen | Host Species | Dilution / Protocol Note | Source Paper.
```
"""
        with open(prompts_path, "w", encoding="utf-8") as f:
            f.write(prompts_content)

        return bundle_dir


def interactive_cli():
    print("=" * 72)
    print("  LitRadar - Zotero Date Inspector & NotebookLM Bundle Exporter")
    print("=" * 72)
    print()

    exporter = NotebookLMBundleExporter()
    if not exporter.db_path.exists():
        print(f"[Error] Zotero database not found at: {exporter.db_path}")
        print("Please check your ZOTERO_DB_PATH in lab_config.env.")
        input("\nPress Enter to exit...")
        return

    print("Choose date filter to find uploaded/harvested papers:")
    print("  [1] Past 7 Days (This Week's Arrivals) [Default]")
    print("  [2] Past 14 Days (Last 2 Weeks)")
    print("  [3] Past 30 Days (Last Month)")
    print("  [4] Today Only")
    print("  [5] Custom Date Range (e.g. 2026-09-01 to 2026-09-29)")
    print("  [6] Filter by Tag (e.g. !unread, #custom-search, SHANK2)")
    print()

    choice = input("Enter choice [1-6] (default [1]): ").strip() or "1"
    today = datetime.now()
    tag_filter = None

    if choice == "1":
        start_date = today - timedelta(days=7)
        end_date = today
    elif choice == "2":
        start_date = today - timedelta(days=14)
        end_date = today
    elif choice == "3":
        start_date = today - timedelta(days=30)
        end_date = today
    elif choice == "4":
        start_date = today.replace(hour=0, minute=0, second=0)
        end_date = today
    elif choice == "5":
        raw_start = input("Enter Start Date (YYYY-MM-DD): ").strip()
        raw_end = input("Enter End Date (YYYY-MM-DD, press Enter for Today): ").strip()
        try:
            start_date = datetime.strptime(raw_start, "%Y-%m-%d")
            end_date = datetime.strptime(raw_end, "%Y-%m-%d") if raw_end else today
        except Exception as e:
            print(f"[Invalid Date] {e}. Defaulting to past 7 days.")
            start_date = today - timedelta(days=7)
            end_date = today
    elif choice == "6":
        tag_filter = input("Enter Tag to filter by (e.g. '!unread'): ").strip()
        start_date = today - timedelta(days=90)
        end_date = today
    else:
        start_date = today - timedelta(days=7)
        end_date = today

    print(f"\n[Searching Zotero DB] Items added between {start_date.strftime('%Y-%m-%d')} and {end_date.strftime('%Y-%m-%d')}...")
    papers = exporter.get_papers_by_date_range(start_date, end_date, tag_filter=tag_filter)

    if not papers:
        print("\nNo papers found in your Zotero library matching that date criteria.")
        input("\nPress Enter to exit...")
        return

    print(f"\nFound {len(papers)} papers added during this timeframe:\n")
    print(f"{'#':<3} | {'Date Added':<10} | {'PDF':<5} | {'Title':<50}")
    print("-" * 75)
    for idx, p in enumerate(papers, start=1):
        has_pdf = " YES " if p.get("pdf_path") else "  -  "
        date_str = p.get("date_added", "")[:10]
        safe_title = p.get("title", "")[:48]
        print(f"{idx:<3} | {date_str:<10} | {has_pdf:<5} | {safe_title}")

    print("\n" + "=" * 72)
    print("Export Options:")
    print("  [1] Bundle all available PDFs & generate NotebookLM overview [Default]")
    print("  [2] Select specific papers (e.g. '1, 3, 5-8')")
    print("  [Q] Cancel / Exit")
    print("=" * 72)

    export_choice = input("Enter choice (default [1]): ").strip() or "1"
    if export_choice.lower() in ("q", "quit", "cancel"):
        print("Cancelled.")
        return

    papers_to_bundle = papers
    if export_choice != "1":
        # Parse selection
        selected_indices = set()
        for chunk in export_choice.split(","):
            chunk = chunk.strip()
            if "-" in chunk:
                parts = chunk.split("-")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    selected_indices.update(range(int(parts[0]), int(parts[1]) + 1))
            elif chunk.isdigit():
                selected_indices.add(int(chunk))

        papers_to_bundle = [p for i, p in enumerate(papers, start=1) if i in selected_indices]
        if not papers_to_bundle:
            print("No valid papers selected. Bundling all.")
            papers_to_bundle = papers

    bundle_dir = exporter.create_notebook_lm_bundle(papers_to_bundle)
    pdf_count = len(list(bundle_dir.glob("*.pdf")))

    print("\n" + "=" * 72)
    print("  ✅ NOTEBOOKLM BUNDLE CREATED SUCCESSFULLY!")
    print("=" * 72)
    print(f"  📁 Location:     {bundle_dir}")
    print(f"  📄 PDFs Bundled: {pdf_count}/{len(papers_to_bundle)}")
    print(f"  📝 Overview Doc: {bundle_dir / '00_Bundle_Overview_for_NotebookLM.md'}")
    print("=" * 72)
    print("\nHOW TO USE IN NOTEBOOKLM:")
    print("  1. The bundle folder is opening automatically.")
    print("  2. Open https://notebooklm.google.com in your browser.")
    print("  3. Drag & drop the PDFs and the '00_Bundle_Overview' file into your Notebook.")
    print("  4. Click 'Generate' under Audio Overview for your podcast!")
    print()

    # Open folder in Windows Explorer
    try:
        os.startfile(str(bundle_dir))
    except Exception:
        pass

    input("Press Enter to exit...")


if __name__ == "__main__":
    interactive_cli()
