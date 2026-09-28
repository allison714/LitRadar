"""
Automated Scientific PDF Downloader and Organizer.
Saves PDFs directly into your designated storage folder:
<PDF_STORAGE_DIR>/<TopicSubfolder>/
"""

import os
import re
import time
import requests
import urllib3
from pathlib import Path
from typing import Dict, Any, Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from config import PDF_STORAGE_DIR, NCBI_EMAIL


class PDFDownloader:
    def __init__(self, base_dir: Path = PDF_STORAGE_DIR):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            "User-Agent": f"LitRadar/1.0 (mailto:{NCBI_EMAIL})"
        })

    def _get_target_subfolder(self, paper: Dict[str, Any]) -> Path:
        """Route paper to matching subfolder in Scientific Journals."""
        tags_str = " ".join(paper.get("tags", [])).lower()
        title_str = paper.get("title", "").lower()
        track_name = paper.get("track_name", "").lower()

        # 1. Shank2
        if "shank2" in tags_str or "shank2" in title_str or "shank2" in track_name:
            sub = self.base_dir / "Shank2"
        # 2. ACC Circuitry
        elif "acc" in tags_str or "anterior cingulate" in title_str or "acc" in track_name:
            sub = self.base_dir / "ACC Circuitry"
        # 3. PSD Nanoscale (Homer1, GluN1, GluA1)
        elif "homer1" in tags_str or "glun1" in tags_str or "glua1" in tags_str or "postsynaptic-density" in tags_str or "psd" in track_name:
            sub = self.base_dir / "PSD Nanoscale"
        # 4. Pan-ExM
        elif "pan-exm" in tags_str or "pan-exm" in title_str or "pan-exm" in track_name:
            sub = self.base_dir / "pan-ExM References"
        # 5. Connectomics
        elif "connectomics" in tags_str or "connectomics" in title_str or "connectomics" in track_name:
            sub = self.base_dir / "Connectomics"
        # Fallback / Inbox
        else:
            sub = self.base_dir / "WeeklyUpdates"

        sub.mkdir(parents=True, exist_ok=True)
        return sub

    def _sanitize_filename(self, text: str, max_len: int = 60) -> str:
        clean = re.sub(r"[^\w\s-]", "", text).strip()
        clean = re.sub(r"[-\s]+", "_", clean)
        return clean[:max_len]

    def _resolve_pdf_url(self, doi: str, pmid: str) -> Optional[str]:
        """Query Unpaywall and Europe PMC to resolve direct full-text PDF download links."""
        # 1. Unpaywall (Fastest & Most reliable for open access and institutional preprints)
        if doi:
            try:
                url = f"https://api.unpaywall.org/v2/{doi}"
                params = {"email": NCBI_EMAIL}
                resp = self.session.get(url, params=params, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    best_oa = data.get("best_oa_location") or {}
                    pdf_url = best_oa.get("url_for_pdf")
                    if pdf_url:
                        return pdf_url
            except Exception:
                pass

        # 2. Europe PMC / PMC Direct PDF
        if pmid:
            try:
                url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:{pmid}&format=json&resultType=core"
                resp = self.session.get(url, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("resultList", {}).get("result", [])
                    if results:
                        pmcid = results[0].get("pmcid")
                        if pmcid:
                            return f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf"
            except Exception:
                pass

        # 3. Direct Publisher Endpoints (Authenticated when connected to Institutional VPN)
        if doi:
            doi_lower = doi.lower()
            # Nature Publishing Group (Nature, Nat Neurosci, Nat Methods, etc.)
            if "10.1038/" in doi_lower:
                art_id = doi.split("10.1038/")[-1]
                return f"https://www.nature.com/articles/{art_id}.pdf"
            # Science / AAAS
            elif "10.1126/" in doi_lower:
                return f"https://www.science.org/doi/pdf/{doi}"
            # PNAS
            elif "10.1073/" in doi_lower:
                return f"https://www.pnas.org/doi/pdf/{doi}"
            # Wiley (e.g. Journal of Comparative Neurology)
            elif "10.1002/" in doi_lower:
                return f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}"

        return None

    def download_pdf(self, paper: Dict[str, Any]) -> Optional[Path]:
        """Download paper PDF and save into the organized Scientific Journals folder."""
        doi = paper.get("doi", "").strip()
        pmid = paper.get("pmid", "").strip()
        title = paper.get("title", "Untitled")
        authors = paper.get("authors", "").split(",")[0].replace(" ", "_")
        year = str(paper.get("year", ""))

        target_dir = self._get_target_subfolder(paper)
        clean_title = self._sanitize_filename(title)
        filename = f"{authors}_{year}_{clean_title}.pdf" if authors else f"{clean_title}.pdf"
        target_path = target_dir / filename

        # If already downloaded, return path immediately
        if target_path.exists() and target_path.stat().st_size > 10000:
            paper["local_pdf_path"] = str(target_path)
            return target_path

        # Resolve download URL
        pdf_url = self._resolve_pdf_url(doi, pmid)
        if not pdf_url:
            return None

        # Download PDF stream
        try:
            resp = self.session.get(pdf_url, stream=True, timeout=25)
            if resp.status_code == 200:
                # Check that content is indeed a PDF
                content_type = resp.headers.get("Content-Type", "").lower()
                if "pdf" in content_type or resp.content[:4] == b"%PDF":
                    with open(target_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=32768):
                            if chunk:
                                f.write(chunk)
                    if target_path.stat().st_size > 10000:
                        print(f"    [PDF Downloaded] {target_path.name} -> {target_dir.name}/")
                        paper["local_pdf_path"] = str(target_path)
                        return target_path
                    else:
                        target_path.unlink(missing_ok=True)
        except Exception as e:
            print(f"    [PDF Download Error] {e}")

        return None
