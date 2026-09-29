"""
Automated Scientific PDF Downloader and Organizer.
Saves PDFs directly into your designated storage folder:
<PDF_STORAGE_DIR>/<TopicSubfolder>/

Supports:
  1. Open Access via Unpaywall + Europe PMC
  2. Direct publisher PDF links (Nature, Science, PNAS, Wiley, Elsevier,
     Springer, Cell Press, Oxford, ACS, JNeurosci, Frontiers, eLife,
     bioRxiv/medRxiv, MDPI, JBC, Taylor & Francis)
  3. Institutional proxy fallback (Yale EZProxy) for VPN-authenticated access
"""

import os
import re
import time
import requests
import urllib3
from pathlib import Path
from typing import Dict, Any, Optional, List

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from config import PDF_STORAGE_DIR, NCBI_EMAIL

# ---------------------------------------------------------------------------
# Institutional EZProxy Configuration
# When on institutional VPN, this proxy prefix enables authenticated access
# to paywalled publisher content. Set to "" to disable.
# Common formats:
#   Yale:     https://login.ezproxy.library.yale.edu/login?url=
#   Harvard:  https://ezp-prod1.hul.harvard.edu/login?url=
#   Stanford: https://stanford.idm.oclc.org/login?url=
# ---------------------------------------------------------------------------
EZPROXY_PREFIX = os.environ.get(
    "EZPROXY_PREFIX",
    "https://login.ezproxy.library.yale.edu/login?url="
)


class PDFDownloader:
    def __init__(self, base_dir: Path = PDF_STORAGE_DIR):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            "User-Agent": f"LitRadar/1.0 (mailto:{NCBI_EMAIL})",
            "Accept": "application/pdf,*/*",
        })
        # Track stats for end-of-run summary
        self.stats = {"oa": 0, "publisher": 0, "proxy": 0, "failed": 0}

    def _get_target_subfolder(self, paper: Dict[str, Any]) -> Path:
        """Route paper to matching subfolder in Scientific Journals."""
        tags_str = " ".join(paper.get("tags", [])).lower()
        title_str = paper.get("title", "").lower()
        track_name = paper.get("track_name", "").lower()

        if "shank2" in tags_str or "shank2" in title_str or "shank2" in track_name:
            sub = self.base_dir / "Shank2"
        elif "acc" in tags_str or "anterior cingulate" in title_str or "acc" in track_name:
            sub = self.base_dir / "ACC Circuitry"
        elif "homer1" in tags_str or "glun1" in tags_str or "glua1" in tags_str or "postsynaptic-density" in tags_str or "psd" in track_name:
            sub = self.base_dir / "PSD Nanoscale"
        elif "pan-exm" in tags_str or "pan-exm" in title_str or "pan-exm" in track_name:
            sub = self.base_dir / "pan-ExM References"
        elif "connectomics" in tags_str or "connectomics" in title_str or "connectomics" in track_name:
            sub = self.base_dir / "Connectomics"
        else:
            sub = self.base_dir / "WeeklyUpdates"

        sub.mkdir(parents=True, exist_ok=True)
        return sub

    def _sanitize_filename(self, text: str, max_len: int = 60) -> str:
        clean = re.sub(r"[^\w\s-]", "", text).strip()
        clean = re.sub(r"[-\s]+", "_", clean)
        return clean[:max_len]

    # ------------------------------------------------------------------
    # PDF URL Resolution Chain
    # ------------------------------------------------------------------

    def _resolve_pdf_url(self, doi: str, pmid: str) -> Optional[str]:
        """
        Multi-source PDF URL resolution:
          1. Unpaywall (open access)
          2. Europe PMC / PubMed Central
          3. bioRxiv / medRxiv preprint servers
          4. Direct publisher URL patterns (works best on institutional VPN)
        """
        # 1. Unpaywall — fastest & most reliable for open access
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

        # 2. Europe PMC / PubMed Central
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

        # 3. bioRxiv / medRxiv preprint check
        if doi:
            doi_lower = doi.lower()
            if "10.1101/" in doi_lower:
                # bioRxiv/medRxiv DOIs resolve to preprint PDFs directly
                return f"https://www.biorxiv.org/content/{doi}v1.full.pdf"

        # 4. Direct publisher PDF endpoints
        #    These work when on institutional VPN or when the article is open access.
        if doi:
            publisher_url = self._resolve_publisher_url(doi)
            if publisher_url:
                return publisher_url

        return None

    def _resolve_publisher_url(self, doi: str) -> Optional[str]:
        """
        Map DOI prefixes to direct publisher PDF download URLs.
        These URLs serve PDFs directly when accessed from an institutional
        network (VPN) or when the article is open access.
        """
        doi_lower = doi.lower()

        # Nature Publishing Group (Nature, Nat Neurosci, Nat Methods, etc.)
        if "10.1038/" in doi_lower:
            art_id = doi.split("10.1038/")[-1]
            return f"https://www.nature.com/articles/{art_id}.pdf"

        # Science / AAAS
        if "10.1126/" in doi_lower:
            return f"https://www.science.org/doi/pdf/{doi}"

        # PNAS (Proceedings of the National Academy of Sciences)
        if "10.1073/" in doi_lower:
            return f"https://www.pnas.org/doi/pdf/{doi}"

        # Wiley (J Comp Neurol, Eur J Neurosci, Hippocampus, etc.)
        if "10.1002/" in doi_lower:
            return f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}"

        # Elsevier / ScienceDirect (Neuron, Cell, Mol Cell, etc.)
        if "10.1016/" in doi_lower:
            pii = doi.split("10.1016/")[-1].replace("/", "").replace(".", "").replace("-", "")
            return f"https://www.sciencedirect.com/science/article/pii/{pii}/pdfft"

        # Cell Press (also Elsevier, but different URL pattern)
        # Cell, Neuron, Cell Reports, Current Biology
        if "10.1016/j.cell." in doi_lower or "10.1016/j.neuron." in doi_lower or \
           "10.1016/j.celrep." in doi_lower or "10.1016/j.cub." in doi_lower:
            return f"https://www.cell.com/action/showPdf?pii={doi.split('10.1016/')[-1]}"

        # Springer / SpringerLink
        if "10.1007/" in doi_lower:
            return f"https://link.springer.com/content/pdf/{doi}.pdf"

        # Oxford University Press (Cerebral Cortex, NAR, Brain, etc.)
        if "10.1093/" in doi_lower:
            return f"https://academic.oup.com/doi/pdf/{doi}"

        # American Chemical Society (ACS)
        if "10.1021/" in doi_lower:
            return f"https://pubs.acs.org/doi/pdf/{doi}"

        # Society for Neuroscience (Journal of Neuroscience)
        if "10.1523/" in doi_lower:
            return f"https://www.jneurosci.org/content/jneuro/{doi.split('JNEUROSCI.')[-1] if 'JNEUROSCI.' in doi else doi.split('10.1523/')[-1]}.full.pdf"

        # Frontiers (open access — should usually be caught by Unpaywall)
        if "10.3389/" in doi_lower:
            return f"https://www.frontiersin.org/articles/{doi}/pdf"

        # eLife (open access)
        if "10.7554/" in doi_lower:
            return f"https://elifesciences.org/articles/{doi.split('eLife.')[-1] if 'eLife.' in doi else doi.split('10.7554/')[-1]}/pdf"

        # MDPI (open access)
        if "10.3390/" in doi_lower:
            return f"https://www.mdpi.com/{doi.split('10.3390/')[-1]}/pdf"

        # Journal of Biological Chemistry (JBC)
        if "10.1074/" in doi_lower:
            return f"https://www.jbc.org/article/{doi.split('10.1074/')[-1]}/pdf"

        # Taylor & Francis
        if "10.1080/" in doi_lower or "10.1179/" in doi_lower:
            return f"https://www.tandfonline.com/doi/pdf/{doi}"

        # Royal Society of Chemistry
        if "10.1039/" in doi_lower:
            return f"https://pubs.rsc.org/en/content/articlepdf/{doi.split('10.1039/')[-1]}"

        # Annual Reviews
        if "10.1146/" in doi_lower:
            return f"https://www.annualreviews.org/doi/pdf/{doi}"

        # PLOS (open access)
        if "10.1371/" in doi_lower:
            return f"https://journals.plos.org/plosone/article/file?id={doi}&type=printable"

        return None

    # ------------------------------------------------------------------
    # Download Engine
    # ------------------------------------------------------------------

    def _try_download(self, pdf_url: str, target_path: Path) -> bool:
        """Attempt to download a PDF from a URL. Returns True if successful."""
        try:
            resp = self.session.get(pdf_url, stream=True, timeout=30, allow_redirects=True)
            if resp.status_code == 200:
                content_type = resp.headers.get("Content-Type", "").lower()
                # Read first chunk to verify it's a PDF
                first_chunk = next(resp.iter_content(chunk_size=1024), b"")
                if b"%PDF" in first_chunk or "pdf" in content_type:
                    with open(target_path, "wb") as f:
                        f.write(first_chunk)
                        for chunk in resp.iter_content(chunk_size=32768):
                            if chunk:
                                f.write(chunk)
                    if target_path.stat().st_size > 10000:
                        return True
                    else:
                        # Too small — likely an error page, not a real PDF
                        target_path.unlink(missing_ok=True)
            elif resp.status_code in (403, 401):
                pass  # Paywall — will try proxy fallback
        except Exception:
            pass
        return False

    def _try_proxy_download(self, doi: str, target_path: Path) -> bool:
        """
        Attempt to download via institutional EZProxy.
        This prepends the proxy URL to the DOI resolver, which routes through
        the university's authenticated gateway — works when on VPN.
        """
        if not EZPROXY_PREFIX or not doi:
            return False

        # Route through proxy: EZProxy prefix + DOI URL
        doi_url = f"https://doi.org/{doi}"
        proxy_url = f"{EZPROXY_PREFIX}{doi_url}"

        try:
            resp = self.session.get(proxy_url, stream=True, timeout=30, allow_redirects=True)
            if resp.status_code == 200:
                content_type = resp.headers.get("Content-Type", "").lower()
                first_chunk = next(resp.iter_content(chunk_size=1024), b"")
                if b"%PDF" in first_chunk or "pdf" in content_type:
                    with open(target_path, "wb") as f:
                        f.write(first_chunk)
                        for chunk in resp.iter_content(chunk_size=32768):
                            if chunk:
                                f.write(chunk)
                    if target_path.stat().st_size > 10000:
                        return True
                    else:
                        target_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download_pdf(self, paper: Dict[str, Any]) -> Optional[Path]:
        """
        Download paper PDF using a 3-tier strategy:
          Tier 1: Open Access (Unpaywall, PMC, bioRxiv)
          Tier 2: Direct publisher link (works on VPN)
          Tier 3: Institutional EZProxy fallback (works on VPN)
        """
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

        # --- Tier 1 & 2: Resolve URL and attempt direct download ---
        pdf_url = self._resolve_pdf_url(doi, pmid)
        if pdf_url and self._try_download(pdf_url, target_path):
            print(f"    [PDF Downloaded] {target_path.name} -> {target_dir.name}/")
            paper["local_pdf_path"] = str(target_path)
            self.stats["oa"] += 1
            return target_path

        # --- Tier 3: Institutional EZProxy fallback ---
        if doi and EZPROXY_PREFIX:
            if self._try_proxy_download(doi, target_path):
                print(f"    [PDF via Proxy ] {target_path.name} -> {target_dir.name}/")
                paper["local_pdf_path"] = str(target_path)
                self.stats["proxy"] += 1
                return target_path

        # All tiers failed
        self.stats["failed"] += 1
        return None
