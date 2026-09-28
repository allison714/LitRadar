"""
Harvester module for PubMed, Europe PMC, and Semantic Scholar.
Multi-engine resilience: uses Europe PMC (EMBL-EBI) as a lightning-fast, zero-rate-limit
backbone alongside PubMed and Semantic Scholar with automatic retries.
"""

import time
import requests
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from config import TRACKS, NCBI_API_KEY, NCBI_EMAIL, SEMANTIC_SCHOLAR_API_KEY


class LiteratureHarvester:
    def __init__(self, days_back: int = 30):
        self.days_back = days_back
        now = datetime.now()
        self.mindate_dt = now - timedelta(days=days_back)
        self.mindate = self.mindate_dt.strftime("%Y/%m/%d")
        self.maxdate = now.strftime("%Y/%m/%d")
        self.mindate_iso = self.mindate_dt.strftime("%Y-%m-%d")

        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            "User-Agent": f"LitRadar/1.0 (mailto:{NCBI_EMAIL})"
        })

        # Semantic Scholar rate limiter (capped conservatively at 0.5 req/sec to stay safely below 1 req/sec limit)
        self.last_s2_time = 0.0
        self.s2_min_interval = 2.0

    # -------------------------------------------------------------
    # 1. Europe PMC (EMBL-EBI) - Lightning fast, zero rate limit wall
    # -------------------------------------------------------------
    def search_europe_pmc(self, query: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Query Europe PMC REST API (indexes all PubMed + bioRxiv/medRxiv preprints)."""
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        # Filter for recent literature
        full_query = f"({query}) AND (FIRST_PDATE:[{self.mindate_iso} TO *])"
        params = {
            "query": full_query,
            "format": "json",
            "pageSize": limit,
            "resultType": "core",
            "sort": "P_PDATE_D desc",
        }

        articles = []
        try:
            resp = self.session.get(url, params=params, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("resultList", {}).get("result", [])
                for item in results:
                    doi = item.get("doi", "").lower().strip()
                    pmid = item.get("pmid", "")
                    title = item.get("title", "").strip().rstrip(".")
                    abstract = item.get("abstractText", "No abstract available.")
                    journal = item.get("journalTitle") or item.get("bookOrReportDetails", {}).get("publisher") or "Preprint/Journal"
                    authors = item.get("authorString", "Unknown Authors")
                    pub_year = item.get("pubYear", datetime.now().year)

                    articles.append({
                        "source": "Europe PMC",
                        "pmid": pmid,
                        "doi": doi,
                        "title": title,
                        "journal": journal,
                        "authors": authors,
                        "year": int(pub_year) if str(pub_year).isdigit() else datetime.now().year,
                        "abstract": abstract,
                        "citations": item.get("citedByCount", 0),
                        "url": f"https://doi.org/{doi}" if doi else f"https://europepmc.org/article/MED/{pmid}",
                    })
        except Exception as e:
            print(f"    [Europe PMC Error] {e}")

        return articles

    # -------------------------------------------------------------
    # 2. PubMed via NCBI E-Utilities (with retries and 30s timeout)
    # -------------------------------------------------------------
    def search_pubmed(self, query: str, max_results: int = 20) -> List[str]:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": max_results,
            "datetype": "edat",
            "mindate": self.mindate,
            "maxdate": self.maxdate,
            "sort": "pub_date",
        }
        if NCBI_API_KEY:
            params["api_key"] = NCBI_API_KEY

        for attempt in range(2):
            try:
                resp = self.session.get(base_url, params=params, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("esearchresult", {}).get("idlist", [])
            except requests.exceptions.Timeout:
                if attempt == 0:
                    time.sleep(1.5)
            except Exception as e:
                print(f"    [PubMed Search Error] {e}")
                break
        return []

    def fetch_pubmed_details(self, pmids: List[str]) -> List[Dict[str, Any]]:
        if not pmids:
            return []

        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }
        if NCBI_API_KEY:
            params["api_key"] = NCBI_API_KEY

        articles = []
        try:
            resp = self.session.get(base_url, params=params, timeout=30)
            if resp.status_code != 200:
                return []

            root = ET.fromstring(resp.content)
            for article_elem in root.findall(".//PubmedArticle"):
                pmid = article_elem.findtext(".//MedlineCitation/PMID") or ""
                title = article_elem.findtext(".//ArticleTitle") or "Untitled"
                journal = article_elem.findtext(".//Journal/Title") or "Unknown Journal"

                doi = ""
                for article_id in article_elem.findall(".//PubmedData/ArticleIdList/ArticleId"):
                    if article_id.get("IdType") == "doi":
                        doi = article_id.text
                        break

                abstract_parts = []
                for abs_text in article_elem.findall(".//Abstract/AbstractText"):
                    label = abs_text.get("Label")
                    text = "".join(abs_text.itertext()).strip()
                    if label:
                        abstract_parts.append(f"{label}: {text}")
                    elif text:
                        abstract_parts.append(text)
                abstract = "\n\n".join(abstract_parts) if abstract_parts else "No abstract available."

                author_names = []
                for author in article_elem.findall(".//AuthorList/Author"):
                    last_name = author.findtext("LastName") or ""
                    initials = author.findtext("Initials") or ""
                    if last_name:
                        author_names.append(f"{last_name} {initials}".strip())
                authors_str = ", ".join(author_names[:5]) + (" et al." if len(author_names) > 5 else "")

                year = article_elem.findtext(".//JournalIssue/PubDate/Year") or str(datetime.now().year)

                articles.append({
                    "source": "PubMed",
                    "pmid": pmid,
                    "doi": doi.lower().strip() if doi else "",
                    "title": title.strip(),
                    "journal": journal.strip(),
                    "authors": authors_str,
                    "year": int(year) if year.isdigit() else datetime.now().year,
                    "abstract": abstract,
                    "citations": 0,
                    "url": f"https://doi.org/{doi}" if doi else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                })
        except Exception as e:
            print(f"    [PubMed Fetch Error] {e}")

        return articles

    # -------------------------------------------------------------
    # 3. Semantic Scholar (Rate-limited strictly below 1 req/sec)
    # -------------------------------------------------------------
    def _s2_throttle(self):
        """Enforces cumulative rate limiting strictly below 1 req/sec threshold."""
        now = time.time()
        elapsed = now - self.last_s2_time
        if elapsed < self.s2_min_interval:
            time.sleep(self.s2_min_interval - elapsed)
        self.last_s2_time = time.time()

    def search_semantic_scholar(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        fields = "paperId,title,abstract,venue,year,citationCount,influentialCitationCount,openAccessPdf,externalIds,authors,publicationDate"
        headers = {}
        if SEMANTIC_SCHOLAR_API_KEY:
            headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY

        params = {
            "query": query,
            "limit": limit,
            "fields": fields,
            "year": f"{datetime.now().year - 1}-{datetime.now().year}",
        }

        papers = []
        # Attempt with polite throttle and retry backoff on 429
        for attempt in range(2):
            self._s2_throttle()
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("data", []):
                        external_ids = item.get("externalIds") or {}
                        doi = external_ids.get("DOI", "")
                        pmid = external_ids.get("PubMed", "")
                        authors_list = [a.get("name", "") for a in (item.get("authors") or []) if a.get("name")]
                        authors_str = ", ".join(authors_list[:5]) + (" et al." if len(authors_list) > 5 else "")

                        papers.append({
                            "source": "Semantic Scholar",
                            "pmid": pmid,
                            "doi": doi.lower().strip() if doi else "",
                            "title": (item.get("title") or "Untitled").strip(),
                            "journal": item.get("venue") or "Preprint/Unknown",
                            "authors": authors_str,
                            "year": item.get("year") or datetime.now().year,
                            "abstract": item.get("abstract") or "No abstract available.",
                            "citations": item.get("citationCount") or 0,
                            "influential_citations": item.get("influentialCitationCount") or 0,
                            "url": f"https://doi.org/{doi}" if doi else f"https://www.semanticscholar.org/paper/{item.get('paperId')}",
                        })
                    break
                elif resp.status_code == 429:
                    # Respectful rate limit backoff (sleep 2.5s and retry once)
                    time.sleep(2.5)
                else:
                    break
            except Exception:
                time.sleep(1.0)

        return papers

    def fetch_paper_citations_s2(self, doi: str = "", pmid: str = "") -> Optional[int]:
        """Fetch real-time citation count from Semantic Scholar for a DOI or PMID."""
        if not doi and not pmid:
            return None
        raw_id = f"DOI:{doi}" if doi else f"PMID:{pmid}"
        encoded_id = urllib.parse.quote(raw_id, safe="")
        url = f"https://api.semanticscholar.org/graph/v1/paper/{encoded_id}"
        headers = {}
        if SEMANTIC_SCHOLAR_API_KEY:
            headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY

        self._s2_throttle()
        try:
            resp = self.session.get(url, params={"fields": "citationCount"}, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("citationCount")
            elif resp.status_code == 429:
                time.sleep(2.5)
        except Exception:
            pass
        return None

    # -------------------------------------------------------------
    # Multi-Engine Harvest Across All 5 Tracks
    # -------------------------------------------------------------
    def harvest_all_tracks(self) -> Dict[str, List[Dict[str, Any]]]:
        harvest_results = {}

        for track_key, track_meta in TRACKS.items():
            print(f"--> Harvesting {track_meta['name']}...")
            track_articles = []
            seen_identifiers = set()

            # Stream 1: Europe PMC (Reliable & Instant)
            epmc_items = self.search_europe_pmc(track_meta["semantic_query"], limit=10)
            for item in epmc_items:
                ident = item["doi"] or item["pmid"] or item["title"].lower()
                if ident not in seen_identifiers:
                    seen_identifiers.add(ident)
                    item["track_id"] = track_meta["id"]
                    item["track_name"] = track_meta["name"]
                    track_articles.append(item)

            # Stream 2: PubMed
            time.sleep(0.3)
            pmids = self.search_pubmed(track_meta["pubmed_query"], max_results=15)
            if pmids:
                time.sleep(0.3)
                pubmed_items = self.fetch_pubmed_details(pmids)
                for item in pubmed_items:
                    ident = item["doi"] or item["pmid"] or item["title"].lower()
                    if ident not in seen_identifiers:
                        seen_identifiers.add(ident)
                        item["track_id"] = track_meta["id"]
                        item["track_name"] = track_meta["name"]
                        track_articles.append(item)

            # Stream 3: Semantic Scholar (gentle)
            time.sleep(0.4)
            s2_items = self.search_semantic_scholar(track_meta["semantic_query"], limit=5)
            for item in s2_items:
                ident = item["doi"] or item["pmid"] or item["title"].lower()
                if ident not in seen_identifiers:
                    seen_identifiers.add(ident)
                    item["track_id"] = track_meta["id"]
                    item["track_name"] = track_meta["name"]
                    track_articles.append(item)

            harvest_results[track_key] = track_articles
            print(f"    Found {len(track_articles)} candidate papers.")

        return harvest_results
