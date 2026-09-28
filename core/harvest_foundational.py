"""
Foundational Literature Harvester.
Harvests the Top 20 all-time highest-cited papers for each of the 5 research pillars,
skipping any papers already in your 2,359-item Zotero library, and synthesizes 5
'Master Class Intro' podcast briefing documents for NotebookLM.
"""

import sys
import time
import requests
import urllib3
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import TRACKS, PODCAST_DIR, OUTPUT_DIR, PDF_STORAGE_DIR
from zotero_sync import ZoteroSync
from classifier import PaperClassifier
from excel_generator import ExcelKnowledgeBase
from pdf_downloader import PDFDownloader

PRIMER_DIR = PODCAST_DIR / "Foundational_Primers"
PRIMER_DIR.mkdir(parents=True, exist_ok=True)


class FoundationalHarvester:
    def __init__(self, top_n_per_track: int = 20):
        self.top_n = top_n_per_track
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({"User-Agent": "LitRadar/1.0"})
        self.zotero = ZoteroSync()
        self.classifier = PaperClassifier()

    def fetch_top_cited_europe_pmc(self, query: str, target_count: int = 20) -> List[Dict[str, Any]]:
        """Fetch papers sorted strictly by citation count descending, skipping existing Zotero items."""
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {
            "query": query,
            "format": "json",
            "pageSize": 50,  # Fetch a wide candidate pool to find ones you don't already have
            "resultType": "core",
            "sort": "CITED desc",
        }

        fresh_papers = []
        try:
            resp = self.session.get(url, params=params, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("resultList", {}).get("result", [])
                print(f"    Scanning {len(results)} highly-cited candidate papers...")

                for item in results:
                    doi = item.get("doi", "").lower().strip()
                    pmid = str(item.get("pmid", "")).strip()
                    title = item.get("title", "").strip().rstrip(".")

                    # Deduplication check against your Zotero library
                    norm_title = self.zotero._normalize_title(title)
                    if doi and doi in self.zotero.known_dois:
                        continue
                    if pmid and pmid in self.zotero.known_pmids:
                        continue
                    if norm_title and norm_title in self.zotero.known_titles:
                        continue

                    # If fresh, extract
                    abstract = item.get("abstractText", "Abstract available in full text.")
                    journal = item.get("journalTitle") or "High-Impact Journal"
                    authors = item.get("authorString", "Key Investigators")
                    pub_year = item.get("pubYear", "")
                    citations = item.get("citedByCount", 0)

                    paper = {
                        "source": "Europe PMC (Foundational)",
                        "doi": doi,
                        "pmid": pmid,
                        "title": title,
                        "journal": journal,
                        "authors": authors,
                        "year": int(pub_year) if str(pub_year).isdigit() else datetime.now().year,
                        "abstract": abstract,
                        "citations": citations,
                        "url": f"https://doi.org/{doi}" if doi else f"https://europepmc.org/article/MED/{pmid}",
                    }
                    fresh_papers.append(paper)

                    if len(fresh_papers) >= target_count:
                        break

        except Exception as e:
            print(f"    [Foundational Harvest Error] {e}")

        return fresh_papers

    def generate_master_intro_briefing(self, track_meta: Dict[str, Any], papers: List[Dict[str, Any]]) -> str:
        """Synthesize top 20 foundational papers into a Master Class podcast briefing."""
        paper_summaries = []
        for idx, p in enumerate(papers, start=1):
            paper_summaries.append(
                f"### {idx}. {p['title']} ({p['year']})\n"
                f"- **Journal:** {p['journal']} | **Citations:** {p['citations']:,}\n"
                f"- **Authors:** {p['authors']}\n"
                f"- **Direct Link:** [{p['url']}]({p['url']})\n"
                f"- **Core Abstract & Insight:** {p['abstract'][:450]}...\n"
            )

        summaries_block = "\n".join(paper_summaries)

        return f"""# Master Class Podcast Briefing: Foundational Overview
## Pillar: {track_meta['name']}
**Pedagogical Purpose:** A comprehensive, high-level introductory deep dive synthesizing the top {len(papers)} benchmark publications establishing this scientific domain.

---

### Episode Roadmap & Host Instructions (NotebookLM Audio Overview)
* **Tone:** Engaging, intellectually demanding academic discussion between two senior neurobiology colleagues.
* **Act 1: The Historical Context & Paradigm Shift (0:00 - 5:00)**
  * Why was this question historically difficult to address?
  * What early dogmas were overturned by these foundational discoveries?
* **Act 2: The Core Molecular & Circuit Mechanisms (5:00 - 15:00)**
  * Break down the key findings of the benchmark papers listed below.
  * Connect the structural biochemistry to functional physiology.
* **Act 3: The Major Controversies & Open Frontiers (15:00 - 22:00)**
  * Where do these top studies disagree?
  * What technical challenges (e.g. imaging resolution limits, antibody specificity, model organism translation) remain unresolved?
* **Act 4: Active Recall Self-Test (Conclusion)**
  * Two challenging conceptual questions for the listener to verify foundational mastery.

---

## The {len(papers)} Benchmark Publications Synthesized in this Master Class

{summaries_block}

---

### Key Synthesis Themes for the Hosts
1. **Biological Anchors:** Highlight the recurring scaffolding partners, receptor complexes, and cellular subtypes that unify these studies.
2. **Methodological Evolution:** Trace how experimental techniques progressed from early biochemical assays to super-resolution nanoscopy and connectomic reconstructions.
3. **Clinical & Translational Implications:** Bridge the basic molecular biology to autism spectrum disorder, schizophrenia, and circuit-level therapies.
"""

    def run_foundational_pipeline(self):
        print("=" * 75)
        print("  SHANK2 & Pan-ExM Foundational Literature Harvester (Top 20 by Citations)")
        print("=" * 75)

        all_foundational_papers = []

        for track_key, track_meta in TRACKS.items():
            print(f"\n--> Harvesting Top {self.top_n} Foundational Papers for {track_meta['name']}...")
            papers = self.fetch_top_cited_europe_pmc(track_meta["semantic_query"], target_count=self.top_n)
            print(f"    Found {len(papers)} fresh, highly-cited foundational papers (excluding your existing library).")

            # Classify
            for p in papers:
                p["track_name"] = track_meta["name"]
                p["track_id"] = track_meta["id"]
                self.classifier.classify(p)
                all_foundational_papers.append(p)

            # Generate Master Class Briefing Document
            briefing_content = self.generate_master_intro_briefing(track_meta, papers)
            filename = f"Intro_Track_{track_meta['id']}_{track_meta['folder']}_MasterClass.md"
            filepath = PRIMER_DIR / filename
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(briefing_content)
            print(f"    [+] Created Master Class Briefing: {filename}")

        # Download Full-Text PDFs directly to PDF Storage Vault
        print(f"\n--> Downloading Foundational PDFs directly to Storage Vault ({PDF_STORAGE_DIR.name})...")
        downloader = PDFDownloader()
        pdf_count = 0
        for p in all_foundational_papers:
            pdf_path = downloader.download_pdf(p)
            if pdf_path:
                pdf_count += 1
        print(f"    [+] Saved {pdf_count} foundational PDFs to {PDF_STORAGE_DIR}")

        # Sync to Zotero (Cloud collection routing & .ris export)
        print("\n--> Syncing Foundational Literature to Zotero...")
        self.zotero.sync_new_papers(all_foundational_papers)

        # Update Master Excel Archive with these foundational benchmarks
        print("\n--> Merging Foundational Benchmarks into Master Excel Archive...")
        kb = ExcelKnowledgeBase()
        kb.update_knowledge_base(all_foundational_papers)

        print("\n" + "=" * 75)
        print("  Foundational Harvest Complete!")
        print(f"  • Total Benchmarks Added: {len(all_foundational_papers)} papers")
        print(f"  • PDFs Saved to OneDrive: {pdf_count} papers")
        print(f"  • Master Class Briefings: {PRIMER_DIR}")
        print("=" * 75)


if __name__ == "__main__":
    harvester = FoundationalHarvester(top_n_per_track=20)
    harvester.run_foundational_pipeline()
