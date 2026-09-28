"""
Podcast Briefing Preparation Engine for NotebookLM Audio Overviews.
LitRadar Suite.
"""

from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

from config import TRACKS, PODCAST_DIR, GEMINI_API_KEY


class PodcastBriefingGenerator:
    def __init__(self, output_base_dir: Path = PODCAST_DIR):
        self.output_base_dir = output_base_dir
        self.gemini_client = None
        if GEMINI_API_KEY:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            except Exception:
                pass

    def _get_week_folder(self) -> Path:
        now = datetime.now()
        week_num = now.strftime("%U")
        folder = self.output_base_dir / f"Week_{now.year}_W{week_num}"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def generate_briefing_content(self, track_meta: Dict[str, Any], paper: Dict[str, Any]) -> str:
        title = paper.get("title", "Untitled Research")
        journal = paper.get("journal", "Academic Journal")
        authors = paper.get("authors", "Research Team")
        abstract = paper.get("abstract", "")
        tldr = paper.get("tldr", "")
        url = paper.get("url", "")
        doi = paper.get("doi", "")
        targets = ", ".join(paper.get("targets", []))
        methods = ", ".join(paper.get("methods", []))

        if self.gemini_client:
            prompt = f"""
You are preparing a master source document for NotebookLM's Audio Overview (a two-host deep dive podcast).
The listener is a doctoral/postdoctoral neurobiologist specializing in SHANK2 synaptopathy, ACC circuitry, Homer1/GluN1/GluA1 postsynaptic density scaffolding, and Pan-Expansion Microscopy (Pan-ExM).

TRACK: {track_meta['name']}
TITLE: {title}
AUTHORS: {authors}
JOURNAL: {journal} ({paper.get('year', '')})
DOI: {doi}
ABSTRACT: {abstract}
DETECTED TARGETS: {targets}
DETECTED METHODS: {methods}

Synthesize this paper into an engaging, intellectually rigorous briefing with these exact 5 sections:
1. # EPISODE HOOK & CENTRAL CONFLICT: Start with a provocative question or biological contradiction.
2. # DETAILED MECHANISTIC BREAKDOWN: Step-by-step molecular, structural, or circuit mechanisms demonstrated in the paper.
3. # METHODOLOGICAL SCRUTINY: Key techniques (e.g. Pan-ExM staining, patch-clamp recordings), experimental controls, and technical limitations.
4. # HOST DEBATE & CONTRARIAN PERSPECTIVES: 3 specific controversy points where the two podcast hosts should push back on each other.
5. # ACTIVE RECALL TEST (FOR LISTENER): 2 sharp conceptual questions for the hosts to ask at the end of the episode to test the listener's retention.

Format as clean, elegant Markdown.
"""
            try:
                res = self.gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                if res.text:
                    return f"# {track_meta['name']}\n## Featured Paper: {title}\n**Source:** [{journal}]({url}) | **Authors:** {authors}\n\n" + res.text
            except Exception as e:
                print(f"[Podcast Generator] Gemini prompt error: {e}. Falling back to template.")

        # High-Quality Fallback Template
        return f"""# {track_meta['name']}
## Featured Paper: {title}
**Journal:** {journal} ({paper.get('year', datetime.now().year)})  
**Authors:** {authors}  
**Direct Link:** [{url}]({url})  
**Core Targets:** {targets or 'SHANK2, PSD, Excitatory Synapse'}  
**Primary Methods:** {methods or 'Expansion Microscopy / Patch-Clamp / Histology'}  

---

### 1. Executive Summary & Biological Hook
> **The Core Tension:** How does this study reshape our model of synaptic organization or neurodevelopmental disease?

{tldr}

---

### 2. Detailed Abstract & Findings
{abstract}

---

### 3. Methodological Scrutiny & Technical Notes
* **Experimental System:** Review whether findings originate from mouse knockouts, patient-derived iPSCs, or post-mortem tissue.
* **Imaging & Nanoscale Validation:** Pay close attention to whether antibody staining was performed pre- or post-expansion (critical in Pan-ExM protocols).
* **Statistical Rigor:** Verify biological vs. technical replicates and sex as a biological variable in behavioral/e-phys assays.

---

### 4. Podcast Debate Prompts (For NotebookLM Hosts)
1. **Contrarian Viewpoint:** Does the observed synaptic deficit reflect a cell-autonomous scaffold failure, or a network-level compensatory remodeling?
2. **Translation Gap:** How reliably do rodent models of this mutation predict human cortical synaptopathy?
3. **Resolution Limits:** Did the imaging modality (e.g. Pan-ExM or EM) convincingly demonstrate nanodomain separation between scaffold and receptor subunits?

---

### 5. Active Recall Self-Test
1. *Question 1:* What is the primary functional consequence of this perturbation on excitatory synaptic transmission?
2. *Question 2:* Which specific protein-protein interaction or scaffolding anchor was directly investigated?
"""

    def prepare_all_weekly_podcasts(self, harvest_results: Dict[str, List[Dict[str, Any]]]) -> List[Path]:
        week_folder = self._get_week_folder()
        generated_files = []

        print(f"\n[Podcast Generator] Prepping 5 Weekly Briefings in {week_folder}...")

        for track_key, track_meta in TRACKS.items():
            papers = harvest_results.get(track_key, [])
            if not papers:
                paper = {
                    "title": f"Weekly Review: Current Landscape in {track_meta['name']}",
                    "journal": "Pipeline Synthesis",
                    "authors": "Literature Surveillance System",
                    "abstract": "No newly indexed papers appeared in this narrow search window. Focus listening on previous key literature and review core questions in this research domain.",
                    "tldr": "Landscape steady; no newly indexed publications this week.",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/",
                    "targets": ["SHANK2", "PSD"],
                    "methods": ["Review"],
                }
            else:
                paper = sorted(papers, key=lambda x: (x.get("citations", 0), len(x.get("abstract", ""))), reverse=True)[0]

            content = self.generate_briefing_content(track_meta, paper)
            filename = f"Track_{track_meta['id']}_{track_meta['folder']}.md"
            filepath = week_folder / filename

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            generated_files.append(filepath)
            print(f"    [+] Created: {filename}")

        return generated_files
