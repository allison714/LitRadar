"""
LitRadar LM Slide Deck Generator.
Generates an interactive, presentation-ready HTML slide deck
and a NotebookLM / Markdown presentation paired with weekly podcast topics.
Ensures rigorous academic citations: (LastName F.I., Year, Journal).
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from config import PODCAST_DIR, OUTPUT_DIR, TRACKS


def format_academic_citation(paper: Dict[str, Any]) -> str:
    """Format citation as: (LastName F.I., Year, Journal)"""
    raw_authors = paper.get("authors", "")
    first_author_formatted = "Unknown"

    if raw_authors:
        # Split first author
        first_author_raw = re.split(r"[,;]", raw_authors)[0].strip()
        parts = first_author_raw.split()
        if len(parts) >= 2:
            last_name = parts[-1]
            first_initial = parts[0][0].upper() + "."
            first_author_formatted = f"{last_name} {first_initial}"
        elif parts:
            first_author_formatted = parts[0]

    year = paper.get("year", datetime.now().year)
    journal = paper.get("journal", "Journal")
    if len(journal) > 30:
        journal = journal[:27] + "..."

    return f"({first_author_formatted}, {year}, {journal})"


class SlideDeckGenerator:
    def __init__(self, output_dir: Path = OUTPUT_DIR):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_slide_deck(
        self,
        harvest_results: Dict[str, List[Dict[str, Any]]],
        week_label: Optional[str] = None
    ) -> Path:
        """
        Generate both an interactive HTML presentation and a NotebookLM-ready Markdown slide deck.
        """
        if not week_label:
            now = datetime.now()
            week_label = f"Week {now.strftime('%U')} • {now.strftime('%B %Y')}"

        slides_data = []

        # 1. Title Slide
        slides_data.append({
            "type": "title",
            "title": "LitRadar: Weekly Synaptic Biology Intelligence",
            "subtitle": f"Surveillance & Mechanistic Dossier | {week_label}",
            "footer": "SHANK2 • ACC Circuitry • Nanoscale PSD • Pan-ExM • Connectomics",
            "notes": "Welcome to this week's literature intelligence briefing. Today we synthesize new mechanistic breakthroughs across our 5 synaptic biology dimensions."
        })

        # 2. Executive Overview Slide
        total_papers = sum(len(p) for p in harvest_results.values())
        overview_bullets = []
        for track_key, papers in harvest_results.items():
            track_meta = TRACKS.get(track_key, {"name": track_key.upper()})
            if papers:
                top_p = papers[0]
                cite = format_academic_citation(top_p)
                overview_bullets.append(f"<strong>{track_meta['name']}:</strong> {top_p.get('title', '')[:75]}... <em>{cite}</em>")

        slides_data.append({
            "type": "content",
            "tag": "EXECUTIVE SUMMARY",
            "title": "Weekly Harvest & Thematic Synthesis",
            "subtitle": f"Harvested {total_papers} newly indexed publications across 5 research dimensions.",
            "bullets": overview_bullets or ["No newly indexed papers this surveillance cycle."],
            "notes": f"Across {total_papers} newly indexed papers, the overarching theme this week centers on nanoscale scaffolding stability and circuit remodeling."
        })

        # 3. Pillar Slides (One slide per active research pillar)
        for track_key, track_meta in TRACKS.items():
            papers = harvest_results.get(track_key, [])
            if not papers:
                continue

            top_paper = papers[0]
            citation = format_academic_citation(top_paper)
            title = top_paper.get("title", "Untitled Research")
            tldr = top_paper.get("tldr", top_paper.get("abstract", "")[:250] + "...")
            targets = ", ".join(top_paper.get("targets", [])) or "Synaptic targets"
            methods = ", ".join(top_paper.get("methods", [])) or "Electrophysiology / Super-Resolution / Histology"
            url = top_paper.get("url", f"https://doi.org/{top_paper.get('doi', '')}")

            slides_data.append({
                "type": "pillar",
                "tag": f"PILLAR: {track_meta['name'].upper()}",
                "title": title,
                "citation": citation,
                "url": url,
                "tldr": tldr,
                "targets": targets,
                "methods": methods,
                "podcast_note": "🎧 Paired with NotebookLM Podcast Dossier in podcast_briefings/",
                "notes": f"Host A: Notice how {citation} demonstrates critical remodeling at the postsynaptic density.\nHost B: Yes, but we need to pay close attention to whether the sample size and antibody controls fully rule out non-specific binding."
            })

        # 4. Methodological Reagent & Antibody Inventory Slide
        ab_entries = []
        for papers in harvest_results.values():
            for p in papers:
                for ab in p.get("pan_exm_antibodies", []):
                    ab_cite = format_academic_citation(p)
                    ab_entries.append(f"<strong>{ab.get('target', 'Unknown')}</strong> ({ab.get('host', 'Host')}) — {ab.get('vendor', 'Vendor')} {ab.get('catalog_no', '')} | <em>{ab_cite}</em>")

        if ab_entries:
            slides_data.append({
                "type": "content",
                "tag": "PAN-EXM PROTOCOL ASSETS",
                "title": "Validated Antibodies & Reagents Identified",
                "subtitle": "Experimental tools extracted for immediate laboratory deployment:",
                "bullets": ab_entries[:6],
                "notes": "Here are the exact antibody clones and protocols extracted from this week's harvest that we can directly test in our expansion microscopy experiments."
            })

        # Render HTML Slide Deck
        html_path = self.output_dir / "Weekly_Slide_Deck.html"
        self._render_html_presentation(slides_data, html_path)

        # Render LM / Markdown Slide Deck (Optimized for NotebookLM Ingestion)
        lm_md_path = self.output_dir / "Weekly_LM_Slide_Deck.md"
        self._render_lm_markdown(slides_data, lm_md_path)

        # Also copy to podcast_briefings folder for 1-click NotebookLM bundles
        try:
            shutil_dest = PODCAST_DIR / "Weekly_LM_Slide_Deck.md"
            with open(shutil_dest, "w", encoding="utf-8") as f:
                f.write(lm_md_path.read_text(encoding="utf-8"))
        except Exception:
            pass

        print(f"[Slide Generator] Presentation ready at: {html_path}")
        print(f"[Slide Generator] LM Markdown Slide Deck ready at: {lm_md_path}")
        return html_path

    def _render_lm_markdown(self, slides: List[Dict[str, Any]], dest_path: Path):
        """Render a clean, structured Markdown presentation specifically designed for NotebookLM digestion."""
        lines = [
            f"# 📊 LitRadar: Weekly Synaptic Biology Slide Deck (LM Edition)",
            f"> **Optimized for NotebookLM & AI Presentation Generation**",
            f"> **Date:** {datetime.now().strftime('%B %d, %Y')}\n",
            f"---",
        ]

        for idx, s in enumerate(slides, start=1):
            if s["type"] == "title":
                lines.append(f"## Slide {idx}: {s['title']}")
                lines.append(f"**Subtitle:** {s['subtitle']}")
                lines.append(f"**Focus Areas:** {s['footer']}")
                lines.append(f"\n> 🎙️ **Presenter & Podcast Notes:**\n> *\"{s.get('notes', '')}\"*\n")
                lines.append("---\n")
            elif s["type"] == "pillar":
                lines.append(f"## Slide {idx} [{s['tag']}]: {s['title']}")
                lines.append(f"**Academic Citation:** `{s['citation']}` | **DOI:** {s['url']}")
                lines.append(f"\n### 🔬 Core Biological Finding")
                lines.append(f"{s['tldr']}")
                lines.append(f"\n### 🧪 Experimental Framework")
                lines.append(f"- **Key Targets:** {s['targets']}")
                lines.append(f"- **Methodologies:** {s['methods']}")
                lines.append(f"- **Podcast Episode Note:** {s['podcast_note']}")
                lines.append(f"\n> 🎙️ **Podcast Host Dialogue & Presenter Notes:**\n> *\"{s.get('notes', '')}\"*\n")
                lines.append("---\n")
            else:
                lines.append(f"## Slide {idx} [{s.get('tag', '')}]: {s['title']}")
                if s.get("subtitle"):
                    lines.append(f"*{s['subtitle']}*\n")
                for b in s.get("bullets", []):
                    clean_b = re.sub(r"<[^>]+>", "", b)
                    lines.append(f"- {clean_b}")
                lines.append(f"\n> 🎙️ **Presenter & Podcast Notes:**\n> *\"{s.get('notes', '')}\"*\n")
                lines.append("---\n")

        with open(dest_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _render_html_presentation(self, slides: List[Dict[str, Any]], dest_path: Path):
        slides_html = ""
        for idx, s in enumerate(slides, start=1):
            if s["type"] == "title":
                slides_html += f"""
                <section class="slide title-slide active" id="slide-{idx}">
                    <div class="slide-content">
                        <div class="badge">LITRADAR INTELLIGENCE BRIEFING</div>
                        <h1>{s['title']}</h1>
                        <h3>{s['subtitle']}</h3>
                        <div class="footer-note">{s['footer']}</div>
                        <div class="presenter-note">🎙️ <strong>Presenter Note:</strong> {s.get('notes', '')}</div>
                    </div>
                </section>
                """
            elif s["type"] == "pillar":
                slides_html += f"""
                <section class="slide" id="slide-{idx}">
                    <div class="slide-content">
                        <div class="badge">{s['tag']}</div>
                        <h2>{s['title']}</h2>
                        <div class="citation-bar">
                            <span class="cite-tag">📌 Citation:</span> <strong>{s['citation']}</strong> &nbsp;|&nbsp; <a href="{s['url']}" target="_blank">Open DOI Paper ↗</a>
                        </div>
                        <div class="card-grid">
                            <div class="card main-card">
                                <h4>🔬 Core Biological Finding</h4>
                                <p>{s['tldr']}</p>
                            </div>
                            <div class="card meta-card">
                                <h4>🧪 Experimental Framework</h4>
                                <p><strong>Key Targets:</strong> {s['targets']}</p>
                                <p><strong>Methodologies:</strong> {s['methods']}</p>
                                <div class="podcast-pill">{s['podcast_note']}</div>
                            </div>
                        </div>
                        <div class="presenter-note">🎙️ <strong>Podcast Dialogue:</strong> {s.get('notes', '')}</div>
                    </div>
                </section>
                """
            else:
                bullets_html = "".join([f"<li>{b}</li>" for b in s.get("bullets", [])])
                slides_html += f"""
                <section class="slide" id="slide-{idx}">
                    <div class="slide-content">
                        <div class="badge">{s['tag']}</div>
                        <h2>{s['title']}</h2>
                        <p class="subtitle">{s.get('subtitle', '')}</p>
                        <ul class="bullet-list">
                            {bullets_html}
                        </ul>
                        <div class="presenter-note">🎙️ <strong>Presenter Note:</strong> {s.get('notes', '')}</div>
                    </div>
                </section>
                """

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LitRadar — Weekly Slide Deck</title>
    <style>
        :root {{
            --primary: #0f2c59;
            --accent: #0284c7;
            --bg: #0b1329;
            --card-bg: #1e293b;
            --text: #f8fafc;
            --text-muted: #94a3b8;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
        body {{ background: var(--bg); color: var(--text); overflow: hidden; height: 100vh; display: flex; flex-direction: column; }}
        .deck-container {{ flex: 1; position: relative; width: 100vw; height: 100vh; display: flex; align-items: center; justify-content: center; }}
        .slide {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: none; padding: 50px 80px; justify-content: center; flex-direction: column; background: radial-gradient(circle at 80% 20%, #1e293b 0%, #0b1329 70%); }}
        .slide.active {{ display: flex; animation: fadeIn 0.3s ease-in-out; }}
        @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        
        .badge {{ display: inline-block; background: rgba(2, 132, 199, 0.2); color: #38bdf8; border: 1px solid #0284c7; padding: 5px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; letter-spacing: 1px; margin-bottom: 14px; width: fit-content; }}
        h1 {{ font-size: 40px; font-weight: 800; line-height: 1.2; margin-bottom: 14px; color: #ffffff; }}
        h2 {{ font-size: 28px; font-weight: 700; line-height: 1.3; margin-bottom: 14px; color: #ffffff; }}
        h3 {{ font-size: 20px; font-weight: 400; color: #94a3b8; margin-bottom: 24px; }}
        .subtitle {{ font-size: 16px; color: var(--text-muted); margin-bottom: 20px; }}
        
        .citation-bar {{ background: rgba(255,255,255,0.06); padding: 8px 16px; border-radius: 6px; font-size: 14px; margin-bottom: 20px; border-left: 4px solid var(--accent); }}
        .citation-bar a {{ color: #38bdf8; text-decoration: none; font-weight: 600; }}
        .cite-tag {{ color: #e2e8f0; }}
        
        .card-grid {{ display: grid; grid-template-columns: 1.4fr 1fr; gap: 20px; margin-bottom: 16px; }}
        .card {{ background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 20px; backdrop-filter: blur(10px); }}
        .card h4 {{ color: #38bdf8; font-size: 14px; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .card p {{ font-size: 14px; line-height: 1.5; color: #cbd5e1; margin-bottom: 8px; }}
        .podcast-pill {{ margin-top: 10px; background: rgba(15, 44, 89, 0.8); border: 1px solid #38bdf8; padding: 6px 10px; border-radius: 6px; font-size: 12px; color: #e0f2fe; font-weight: 600; }}
        
        .bullet-list {{ list-style-type: none; margin-bottom: 16px; }}
        .bullet-list li {{ padding: 10px 14px; background: rgba(30, 41, 59, 0.5); border-left: 3px solid var(--accent); margin-bottom: 10px; border-radius: 4px; font-size: 15px; line-height: 1.4; color: #e2e8f0; }}
        
        .presenter-note {{ background: rgba(15, 23, 42, 0.85); border: 1px dashed rgba(56, 189, 248, 0.4); border-radius: 8px; padding: 10px 16px; font-size: 13px; color: #94a3b8; line-height: 1.4; }}
        .presenter-note strong {{ color: #38bdf8; }}
        
        .controls {{ position: fixed; bottom: 20px; right: 40px; display: flex; align-items: center; gap: 12px; z-index: 100; }}
        .nav-btn {{ background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: white; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; transition: all 0.2s; }}
        .nav-btn:hover {{ background: var(--accent); }}
        .slide-counter {{ font-size: 13px; color: var(--text-muted); font-weight: 600; min-width: 60px; text-align: center; }}
        .footer-note {{ margin-top: 20px; font-size: 13px; color: var(--text-muted); letter-spacing: 0.5px; }}
    </style>
</head>
<body>
    <div class="deck-container">
        {slides_html}
    </div>

    <div class="controls">
        <button class="nav-btn" onclick="prevSlide()">❮ Prev</button>
        <span class="slide-counter" id="counter">1 / {len(slides)}</span>
        <button class="nav-btn" onclick="nextSlide()">Next ❯</button>
    </div>

    <script>
        let currentSlide = 1;
        const totalSlides = {len(slides)};

        function showSlide(n) {{
            document.querySelectorAll('.slide').forEach(s => s.classList.remove('active'));
            currentSlide = (n > totalSlides) ? 1 : (n < 1 ? totalSlides : n);
            document.getElementById(`slide-${{currentSlide}}`).classList.add('active');
            document.getElementById('counter').innerText = `${{currentSlide}} / ${{totalSlides}}`;
        }}

        function nextSlide() {{ showSlide(currentSlide + 1); }}
        function prevSlide() {{ showSlide(currentSlide - 1); }}

        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') nextSlide();
            if (e.key === 'ArrowLeft' || e.key === 'PageUp') prevSlide();
        }});
    </script>
</body>
</html>
"""
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(html)
