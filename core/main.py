"""
Master Pipeline Orchestrator.
LitRadar Suite.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harvester import LiteratureHarvester
from zotero_sync import ZoteroSync
from classifier import PaperClassifier
from excel_generator import ExcelKnowledgeBase
from podcast_prep import PodcastBriefingGenerator
from email_digest import EmailDigestNotifier
from pdf_downloader import PDFDownloader
from config import EXCEL_PATH, PODCAST_DIR, OUTPUT_DIR, PDF_STORAGE_DIR


def run_pipeline(days_back: int = 30, dry_run: bool = False):
    print("=" * 70)
    print("  LitRadar - Literature Surveillance Pipeline")
    print("=" * 70)

    # 1. Harvest Literature
    print(f"\n[Step 1/7] Harvesting literature published in the last {days_back} days...")
    harvester = LiteratureHarvester(days_back=days_back)
    raw_harvest = harvester.harvest_all_tracks()
    total_raw = sum(len(papers) for papers in raw_harvest.values())
    print(f"--> Total retrieved across all 5 tracks: {total_raw} candidate papers.")

    # 2. Zotero Deduplication
    print("\n[Step 2/7] Deduplicating against existing Zotero library (2,359+ papers)...")
    zotero = ZoteroSync()
    deduped_harvest = {}
    total_fresh = 0

    for track_key, papers in raw_harvest.items():
        fresh_papers = zotero.filter_new_papers(papers)
        deduped_harvest[track_key] = fresh_papers
        total_fresh += len(fresh_papers)
        print(f"    - {track_key}: {len(fresh_papers)} fresh papers (filtered out {len(papers) - len(fresh_papers)} already in library).")

    print(f"--> Total truly new papers: {total_fresh}")

    # Flatten for classification
    all_fresh_papers = []
    for papers in deduped_harvest.values():
        all_fresh_papers.extend(papers)

    # 3. AI Classification & Tagging
    print("\n[Step 3/7] Classifying papers into Zotero 4-tier tag schema & extracting Pan-ExM antibodies...")
    classifier = PaperClassifier()
    for idx, paper in enumerate(all_fresh_papers, start=1):
        print(f"    [{idx}/{len(all_fresh_papers)}] Tagging: {paper.get('title', '')[:65]}...")
        classifier.classify(paper)
        zotero.add_to_known(paper)

    # 4. Download Full-Text PDFs directly to PDF Storage Vault
    print(f"\n[Step 4/7] Downloading PDFs to Storage Vault ({PDF_STORAGE_DIR.name})...")
    downloader = PDFDownloader()
    pdf_count = 0
    for idx, paper in enumerate(all_fresh_papers, start=1):
        pdf_path = downloader.download_pdf(paper)
        if pdf_path:
            pdf_count += 1
    print(f"--> Successfully downloaded & routed {pdf_count} PDFs into: {PDF_STORAGE_DIR}")

    # 5. Zotero Sync (Dual-Mode: Offline .ris + Web API collection routing)
    print("\n[Step 5/7] Syncing with Zotero (Dual-Mode: .ris export & Cloud Collection injection)...")
    zotero.sync_new_papers(all_fresh_papers)

    # 6. Update Excel Knowledge Base
    print("\n[Step 6/7] Updating Excel Knowledge Base...")
    kb = ExcelKnowledgeBase()
    kb.update_knowledge_base(all_fresh_papers)
    print(f"--> Master Excel saved at: {EXCEL_PATH}")

    # 7. Generate 5 Weekly Podcast Briefings for NotebookLM & Email Digest
    print("\n[Step 7/7] Generating 5 Curated NotebookLM Briefing Packs & Email Digest...")
    podcast_gen = PodcastBriefingGenerator()
    briefing_files = podcast_gen.prepare_all_weekly_podcasts(deduped_harvest)

    notifier = EmailDigestNotifier()
    html_content = notifier.render_html_digest(deduped_harvest, briefing_files)
    notifier.dispatch_email(html_content)

    print("\n" + "=" * 70)
    print("  Pipeline Execution Complete!")
    print(f"  • Excel Matrix:       {EXCEL_PATH}")
    print(f"  • Zotero .ris Backup: {OUTPUT_DIR / 'weekly_arrivals.ris'}")
    print(f"  • Podcast Briefings:  {PODCAST_DIR}")
    print(f"  • Email Preview:      {OUTPUT_DIR / 'weekly_digest_latest.html'}")
    print("=" * 70)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the SHANK2 & Pan-ExM Literature Pipeline")
    parser.add_argument("--days", type=int, default=30, help="Number of past days to harvest (default: 30)")
    args = parser.parse_args()

    run_pipeline(days_back=args.days)
