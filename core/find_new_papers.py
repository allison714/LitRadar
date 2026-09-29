"""
Interactive Literature Discovery & Harvester.
Search Europe PMC and PubMed for new papers using Boolean AND / OR logic.
Deduplicates against your 2,359-item Zotero library, previews matches,
downloads full-text PDFs to OneDrive, and imports newly discovered papers into Zotero Cloud.
"""

import os
import sys
import re
import time
import requests
import urllib3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple, Set, Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    OUTPUT_DIR,
    PDF_STORAGE_DIR,
    NCBI_EMAIL,
    NCBI_API_KEY,
    TOP_TIER_JOURNALS,
    ALL_TOP_JOURNALS,
)
from zotero_sync import ZoteroSync, COLLECTION_MAPPING
from classifier import PaperClassifier
from pdf_downloader import PDFDownloader
from excel_generator import ExcelKnowledgeBase


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


def build_europe_pmc_query(groups: List[List[str]], journal_filter: Optional[List[str]] = None, open_access_only: bool = False) -> str:
    """Constructs targeted Europe PMC query string requiring each AND condition."""
    clauses = []
    for grp in groups:
        sub = " OR ".join(f'"{t}"' if " " in t else t for t in grp)
        clauses.append(f"(TITLE_ABS:({sub}))")
    query = " AND ".join(clauses)
    if journal_filter:
        j_clauses = " OR ".join(f'JOURNAL:"{j}"' for j in journal_filter)
        query = f"({query}) AND ({j_clauses})"
    if open_access_only:
        query = f"({query}) AND (OPEN_ACCESS:y)"
    return query


def build_pubmed_query(groups: List[List[str]], journal_filter: Optional[List[str]] = None, open_access_only: bool = False) -> str:
    """Constructs targeted PubMed query string requiring each AND condition."""
    clauses = []
    for grp in groups:
        sub = " OR ".join(f'"{t}"[Title/Abstract]' for t in grp)
        clauses.append(f"({sub})")
    query = " AND ".join(clauses)
    if journal_filter:
        j_clauses = " OR ".join(f'"{j}"[Journal]' for j in journal_filter)
        query = f"({query}) AND ({j_clauses})"
    if open_access_only:
        query = f"({query}) AND (free full text[filter])"
    return query


def is_top_tier_journal(journal_name: str) -> bool:
    """Accurately checks if a journal belongs to the curated top-tier benchmark list."""
    if not journal_name:
        return False
    j_str = journal_name.strip()
    short_flagships = {'nature', 'science', 'cell', 'neuron', 'elife', 'brain', 'synapse', 'neuroscience'}
    j_lower = j_str.lower()
    if j_lower.startswith('the '):
        j_lower = j_lower[4:].strip()
    base_name = re.split(r'[:(\[]', j_lower)[0].strip()

    if base_name in short_flagships:
        return True

    for top_j in ALL_TOP_JOURNALS:
        top_lower = top_j.lower()
        if top_lower.startswith('the '):
            top_lower = top_lower[4:].strip()
        if top_lower in short_flagships:
            if re.search(rf'\b{re.escape(top_lower)}\b', base_name):
                if top_lower == 'science' and not base_name.startswith('science'):
                    continue
                if top_lower == 'cell' and not (base_name.startswith('cell') or 'cell reports' in base_name or 'cell biology' in base_name):
                    continue
                return True
        else:
            if top_lower in j_lower:
                return True
    return False


def parse_range_tokens(token_str: str, max_val: int) -> Set[int]:
    """Parses range tokens like '1-4', '7', '17' into a set of 1-based integers."""
    indices = set()
    parts = token_str.replace(";", ",").split(",")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "-" in part and not part.startswith("-"):
            sub_parts = part.split("-")
            if len(sub_parts) == 2 and sub_parts[0].strip().isdigit() and sub_parts[1].strip().isdigit():
                start = int(sub_parts[0].strip())
                end = int(sub_parts[1].strip())
                for i in range(min(start, end), max(start, end) + 1):
                    if 1 <= i <= max_val:
                        indices.add(i)
        elif part.isdigit():
            val = int(part)
            if 1 <= val <= max_val:
                indices.add(val)
    return indices


def parse_paper_selection(input_str: str, total_count: int) -> List[int]:
    """
    Parses flexible selection commands:
      - Inclusion: '1-4, 7, 17' or '1, 3, 5'
      - Exclusion: 'exclude 3, 15-17', 'all except 3, 15-17', '-3, 15-17', '!3, 15-17'
      - Combined: '1-10 except 3, 7'
      - All: 'all' or '*'
    Returns sorted 0-based indices.
    """
    s = input_str.strip().lower()
    if s in ["all", "a", "*"]:
        return list(range(total_count))

    is_pure_exclude = False
    for prefix in ["exclude", "except", "without", "omit", "!", "~"]:
        if s.startswith(prefix):
            s = s[len(prefix):].strip()
            is_pure_exclude = True
            break
    if s.startswith("-") and not re.match(r"^-\d+\s*-\s*\d+", s):
        s = s[1:].strip()
        is_pure_exclude = True

    if "except" in s or "exclude" in s:
        delim = "except" if "except" in s else "exclude"
        base_part, exc_part = s.split(delim, 1)
        base_part = base_part.strip()
        if not base_part or base_part in ["all", "a"]:
            base_set = set(range(1, total_count + 1))
        else:
            base_set = parse_range_tokens(base_part, total_count)
        exc_set = parse_range_tokens(exc_part, total_count)
        final_set = base_set - exc_set
    elif is_pure_exclude:
        exc_set = parse_range_tokens(s, total_count)
        final_set = set(range(1, total_count + 1)) - exc_set
    else:
        final_set = parse_range_tokens(s, total_count)

    sorted_1_based = sorted(list(final_set))
    return [i - 1 for i in sorted_1_based if 0 <= i - 1 < total_count]


class NewPaperFinder:
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            "User-Agent": f"LitRadar/1.0 (mailto:{NCBI_EMAIL})"
        })
        self._zotero = None
        self._classifier = None
        self._pdf_downloader = None

    @property
    def zotero(self) -> ZoteroSync:
        if self._zotero is None:
            self._zotero = ZoteroSync()
        return self._zotero

    @property
    def classifier(self) -> PaperClassifier:
        if self._classifier is None:
            self._classifier = PaperClassifier()
        return self._classifier

    @property
    def pdf_downloader(self) -> PDFDownloader:
        if self._pdf_downloader is None:
            self._pdf_downloader = PDFDownloader()
        return self._pdf_downloader

    def search_europe_pmc(self, groups: List[List[str]], max_results: int = 50, journal_filter: Optional[List[str]] = None, open_access_only: bool = False) -> List[Dict[str, Any]]:
        """Search Europe PMC across all years with Boolean AND across groups."""
        query_str = build_europe_pmc_query(groups, journal_filter=journal_filter, open_access_only=open_access_only)
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {
            "query": query_str,
            "format": "json",
            "pageSize": max_results,
            "resultType": "core",
            "sort": "CITED desc",
        }

        papers = []
        try:
            resp = self.session.get(url, params=params, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("resultList", {}).get("result", [])
                for item in results:
                    doi = (item.get("doi") or "").lower().strip()
                    pmid = str(item.get("pmid") or "").strip()
                    title = (item.get("title") or "").strip().rstrip(".")
                    abstract = item.get("abstractText") or "No abstract available."
                    journal_info = item.get("journalInfo", {})
                    journal_obj = journal_info.get("journal", {}) if isinstance(journal_info, dict) else {}
                    journal = item.get("journalTitle") or journal_obj.get("title") or journal_obj.get("medlineAbbreviation") or "Scientific Journal"
                    authors = item.get("authorString") or "Unknown Authors"
                    pub_year = item.get("pubYear", "")
                    citations = item.get("citedByCount", 0)
                    is_oa = (item.get("isOpenAccess") == "Y") or open_access_only

                    papers.append({
                        "source": "Europe PMC",
                        "pmid": pmid,
                        "doi": doi,
                        "title": title,
                        "journal": journal,
                        "authors": authors,
                        "year": int(pub_year) if str(pub_year).isdigit() else datetime.now().year,
                        "abstract": abstract,
                        "citations": citations,
                        "url": f"https://doi.org/{doi}" if doi else f"https://europepmc.org/article/MED/{pmid}",
                        "is_oa": is_oa,
                    })
        except Exception as e:
            print(f"    [Europe PMC Search Error]: {e}")

        return papers

    def search_pubmed(self, groups: List[List[str]], max_results: int = 25, journal_filter: Optional[List[str]] = None, open_access_only: bool = False) -> List[Dict[str, Any]]:
        """Search PubMed via NCBI E-utilities."""
        query_str = build_pubmed_query(groups, journal_filter=journal_filter, open_access_only=open_access_only)
        esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query_str,
            "retmode": "json",
            "retmax": max_results,
            "sort": "relevance",
        }
        if NCBI_API_KEY:
            params["api_key"] = NCBI_API_KEY

        pmids = []
        try:
            r = self.session.get(esearch_url, params=params, timeout=25)
            if r.status_code == 200:
                pmids = r.json().get("esearchresult", {}).get("idlist", [])
        except Exception as e:
            print(f"    [PubMed Search Error]: {e}")
            return []

        if not pmids:
            return []

        # Fetch details
        efetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fparams = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }
        if NCBI_API_KEY:
            fparams["api_key"] = NCBI_API_KEY

        papers = []
        try:
            import xml.etree.ElementTree as ET
            fr = self.session.get(efetch_url, params=fparams, timeout=25)
            if fr.status_code == 200:
                root = ET.fromstring(fr.content)
                for art in root.findall(".//PubmedArticle"):
                    pmid = art.findtext(".//MedlineCitation/PMID") or ""
                    title = art.findtext(".//ArticleTitle") or "Untitled"
                    journal = art.findtext(".//Journal/Title") or "PubMed Journal"
                    year = art.findtext(".//JournalIssue/PubDate/Year") or str(datetime.now().year)

                    doi = ""
                    for aid in art.findall(".//PubmedData/ArticleIdList/ArticleId"):
                        if aid.get("IdType") == "doi":
                            doi = aid.text.lower().strip()
                            break

                    abstract_parts = []
                    for abs_text in art.findall(".//Abstract/AbstractText"):
                        lbl = abs_text.get("Label")
                        t = "".join(abs_text.itertext()).strip()
                        if lbl:
                            abstract_parts.append(f"{lbl}: {t}")
                        elif t:
                            abstract_parts.append(t)
                    abstract = "\n\n".join(abstract_parts) if abstract_parts else "No abstract available."

                    authors_list = []
                    for auth in art.findall(".//AuthorList/Author"):
                        ln = auth.findtext("LastName") or ""
                        init = auth.findtext("Initials") or ""
                        if ln:
                            authors_list.append(f"{ln} {init}".strip())
                    authors_str = ", ".join(authors_list[:5]) + (" et al." if len(authors_list) > 5 else "")

                    papers.append({
                        "source": "PubMed",
                        "pmid": pmid,
                        "doi": doi,
                        "title": title.strip(),
                        "journal": journal.strip(),
                        "authors": authors_str,
                        "year": int(year) if year.isdigit() else datetime.now().year,
                        "abstract": abstract,
                        "citations": 0,
                        "url": f"https://doi.org/{doi}" if doi else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        "is_oa": open_access_only,
                    })
        except Exception as e:
            print(f"    [PubMed Fetch Error]: {e}")

        return papers

    def deduplicate_against_library(self, candidate_papers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Filters candidate papers against existing Zotero library and tracks transparent audit metrics."""
        fresh = []
        already_in_lib = 0
        cross_db_duplicates = 0
        non_neuro_filtered = 0
        seen_identifiers = set()

        for p in candidate_papers:
            doi = p.get("doi", "").lower().strip()
            pmid = str(p.get("pmid", "")).strip()
            norm_title = self.zotero._normalize_title(p.get("title", ""))

            # Filter out non-neuro mechanical/dental false positives (e.g. rotary drill shanks)
            title_lower = p.get("title", "").lower()
            if any(term in title_lower for term in ["dental", "dentistry", "root canal", "rotary system", "endodontic", "nickel-titanium", "orthodontic"]):
                non_neuro_filtered += 1
                continue

            # Intra-batch deduplication (same paper returned by both Europe PMC and PubMed)
            key = doi or pmid or norm_title
            if key in seen_identifiers:
                cross_db_duplicates += 1
                continue
            seen_identifiers.add(key)

            # Check existing Zotero collection
            in_zotero = False
            if doi and doi in self.zotero.known_dois:
                in_zotero = True
            elif pmid and pmid in self.zotero.known_pmids:
                in_zotero = True
            elif norm_title and norm_title in self.zotero.known_titles:
                in_zotero = True

            if in_zotero:
                already_in_lib += 1
            else:
                fresh.append(p)

        return {
            "total_retrieved": len(candidate_papers),
            "cross_db_duplicates": cross_db_duplicates,
            "non_neuro_filtered": non_neuro_filtered,
            "unique_candidates": len(candidate_papers) - cross_db_duplicates - non_neuro_filtered,
            "already_in_lib": already_in_lib,
            "fresh_papers": fresh
        }


def interactive_finder_menu():
    print("=" * 70)
    print("                 LitRadar - Literature Discovery & Search")
    print("=" * 70)
    print("Search scientific databases (Europe PMC & PubMed) for new papers.")
    print("Deduplicates against your Zotero library and downloads PDFs directly to OneDrive.\n")

    print("Options:")
    print("  [1] Shank2 Core & Exon Variants")
    print("  [2] ACC Circuitry & Synaptic Transmission")
    print("  [3] Postsynaptic Density (Homer1, GluN1, GluA1 Scaffolding)")
    print("  [4] Pan-Expansion Microscopy (Pan-ExM)")
    print("  [5] Synaptic Connectomics")
    print("  [C] Custom Boolean AND Query")
    print("  [Q] Quit")

    choice = input("\nEnter your choice (default [C]): ").strip().upper()
    if not choice:
        choice = "C"

    if choice == "Q":
        print("Exiting.")
        return

    if choice == "1":
        tag_to_apply = "SHANK2"
        query_str = "(Shank2, Shank-2, ProSAP1)"
        groups = [["shank2", "shank-2", "prosap1"]]
    elif choice == "2":
        tag_to_apply = "ACC"
        query_str = "(anterior cingulate, ACC, cingulate cortex)"
        groups = [["anterior cingulate", "acc", "cingulate cortex"]]
    elif choice == "3":
        tag_to_apply = "postsynaptic-density"
        query_str = "(postsynaptic density, PSD-95, Homer1, GluN1, GluA1)"
        groups = [["postsynaptic density", "psd-95", "homer1", "glun1", "glua1"]]
    elif choice == "4":
        tag_to_apply = "pan-exm"
        query_str = "(pan-exm, pan expansion microscopy, total proteome expansion)"
        groups = [["pan-exm", "pan expansion microscopy", "total proteome expansion"]]
    elif choice == "5":
        tag_to_apply = "connectomics"
        query_str = "(connectomics, synaptic reconstruction, dense reconstruction)"
        groups = [["connectomics", "synaptic reconstruction", "dense reconstruction"]]
    elif choice == "C":
        print("\n" + "=" * 70)
        print("                 --- CUSTOM BOOLEAN SEARCH SETUP ---")
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
        print("    Keywords: (Shank2, Shank-2, ProSAP1) AND (Electron Microscopy, immunogold, immunoelectron, ultrastructure, TEM)")
        print()
        print("  [Example 2: Shank2 + Receptor Subtypes / NMDA]")
        print("    Tag:      Shank2-NMDA")
        print("    Keywords: (Shank2, Shank-2) AND (NMDA, GluN1, GluN2B, NMDAR)")
        print()
        print("  [Example 3: Shank2 + Anterior Cingulate Cortex / ACC]")
        print("    Tag:      Shank2-ACC")
        print("    Keywords: (Shank2, Shank-2) AND (Anterior Cingulate, ACC, mPFC, cortex)")
        print("-" * 70)

        raw_tag = input("Enter tag to apply (e.g., 'Shank2-Ultrastructure' or 'Shank2-ACC'): ").strip()
        tag_to_apply = raw_tag.strip("\"' ") or "Discovered-Paper"

        raw_kw = input("Enter search keywords (use 'AND' to combine concepts): ").strip()
        groups = parse_keyword_query(raw_kw)

        if not groups:
            print("\n[Error] Search keywords cannot be empty. Aborting.")
            input("\nPress Enter to exit...")
            return
    else:
        print("Invalid choice. Aborting.")
        return

    finder = NewPaperFinder()

    print(f"\n[Search Profile] Primary Tag: '{tag_to_apply}'")
    if len(groups) > 1:
        print("                 Search Logic: Boolean AND across conditions:")
        for idx, grp in enumerate(groups, 1):
            print(f"                   Condition {idx} (MUST match any): {grp}")
    else:
        print(f"                 Keywords: {groups[0]}")

    print("\nSelect Journal Scope:")
    print("  [1] All Scientific Journals (Broadest coverage across all literature)")
    print("  [2] Paywall / Top Flagship Journals (Nature, Science, Cell, Neuron, etc. - requires Institutional VPN)")
    print("  [3] Free / Open Access Journals (PubMed Central, Europe PMC Open, bioRxiv - no VPN needed)")
    print("  [4] Custom Journal(s) (e.g. 'Neuron, Nature Methods, J Neurosci')")
    j_choice = input("Choose journal scope [1-4] (default: 1): ").strip()

    journal_filter = None
    open_access_only = False
    if j_choice == "2":
        journal_filter = ALL_TOP_JOURNALS
        print(f"\n[Scope Applied] Restricting search to {len(journal_filter)} paywalled top flagships (requires Institutional VPN).")
    elif j_choice == "3":
        open_access_only = True
        print("\n[Scope Applied] Restricting search to Free / Open Access repositories (PubMed Central, Europe PMC Open, bioRxiv).")
    elif j_choice == "4":
        custom_j = input("Enter journal name(s) separated by commas: ").strip()
        if custom_j:
            journal_filter = [j.strip() for j in custom_j.split(",") if j.strip()]
            print(f"\n[Scope Applied] Restricting search to custom journals: {', '.join(journal_filter)}")
    else:
        print("\n[Scope Applied] Searching all scientific journals.")

    print("\n[Step 1/3] Querying Europe PMC and PubMed databases...")
    epmc_papers = finder.search_europe_pmc(groups, max_results=50, journal_filter=journal_filter, open_access_only=open_access_only)
    pubmed_papers = finder.search_pubmed(groups, max_results=25, journal_filter=journal_filter, open_access_only=open_access_only)
    all_raw = epmc_papers + pubmed_papers
    print(f"--> Retrieved {len(all_raw)} total candidates across Europe PMC & PubMed.")

    print("\n[Step 2/3] Checking against your existing Zotero Library (2,359 items)...")
    audit = finder.deduplicate_against_library(all_raw)
    base_fresh_papers = audit["fresh_papers"]

    sort_mode = "citations"

    def apply_sort(papers_list, mode):
        if mode == "year":
            papers_list.sort(key=lambda p: (p.get("year", 0), p.get("citations", 0)), reverse=True)
        else:
            papers_list.sort(key=lambda p: (p.get("citations", 0), p.get("year", 0)), reverse=True)

    # Initial sort
    apply_sort(base_fresh_papers, sort_mode)

    print("\nHow would you like to organize the discovered papers?")
    print("  [1] Most Cited (Highest impact & benchmark papers first) [Default]")
    print("  [2] Most Recent (Newest 2026/2025/2024 publications first)")
    sort_pick = input("Choose sort order (default [1]): ").strip()
    if sort_pick == "2":
        sort_mode = "year"
        apply_sort(base_fresh_papers, sort_mode)

    def display_paper_batch(papers_list, start_idx, end_idx):
        for idx in range(start_idx, min(end_idx, len(papers_list))):
            p = papers_list[idx]
            safe_title = p['title'].encode('ascii', 'replace').decode('ascii')
            safe_journal = p.get('journal', 'Journal').encode('ascii', 'replace').decode('ascii')
            top_badge = " [TOP-TIER FLAGSHIP]" if is_top_tier_journal(p.get("journal", "")) else ""
            oa_badge = " [FREE / OPEN ACCESS]" if p.get("is_oa") else ""
            print(f"\n[{idx + 1}] [{p.get('year', 'Unknown')}] {safe_title}")
            print(f"    Journal: {safe_journal}{top_badge}{oa_badge} | Citations: {p.get('citations', 0)}")
            print(f"    Authors: {p.get('authors', 'Unknown')[:65]}")
            if p.get("doi"):
                print(f"    DOI: https://doi.org/{p['doi']}")
            elif p.get("pmid"):
                print(f"    PMID: https://pubmed.ncbi.nlm.nih.gov/{p['pmid']}/")

    flagship_only = False
    oa_only = False
    current_shown = min(5, len(base_fresh_papers))

    sort_label = "Most Recent" if sort_mode == "year" else "Most Cited"
    print(f"\n--- Top {current_shown} New Papers Discovered (Sorted by {sort_label}) ---")
    display_paper_batch(base_fresh_papers, 0, current_shown)

    papers_to_import = []

    while True:
        active_papers = base_fresh_papers
        if flagship_only:
            active_papers = [p for p in active_papers if is_top_tier_journal(p.get("journal", ""))]
        if oa_only:
            active_papers = [p for p in active_papers if p.get("is_oa")]

        total_fresh = len(active_papers)
        current_shown = min(current_shown, total_fresh) if total_fresh > 0 else 0
        sort_label = "Most Recent" if sort_mode == "year" else "Most Cited"
        other_sort = "Most Cited" if sort_mode == "year" else "Most Recent"

        print("\n" + "=" * 70)
        filter_status = ""
        if flagship_only and oa_only:
            filter_status = " [FILTER: Top Flagships & Open Access Only]"
        elif flagship_only:
            filter_status = " [FILTER: Top Flagships Only]"
        elif oa_only:
            filter_status = " [FILTER: Free / Open Access Only]"

        print(f"Currently Viewing {current_shown} of {total_fresh} newly discovered papers. [Sorted by: {sort_label}]{filter_status}")
        print("-" * 70)

        menu_options = {}
        opt_num = 1

        # Option 1: Import currently shown
        if current_shown > 0:
            key_import_curr = str(opt_num)
            print(f"  [{key_import_curr}] Download PDFs & Import Top {current_shown} to Zotero")
            menu_options[key_import_curr] = ("import_count", current_shown)
            opt_num += 1

        # Option 2: View Top 10 (if currently showing < 10)
        if current_shown < 10 and total_fresh > current_shown:
            target_10 = min(10, total_fresh)
            key_view_10 = str(opt_num)
            print(f"  [{key_view_10}] View Top {target_10} Papers")
            menu_options[key_view_10] = ("view", target_10)
            opt_num += 1

        # Option 3: View ALL papers (if not yet showing all)
        if current_shown < total_fresh:
            key_view_all = str(opt_num)
            print(f"  [{key_view_all}] View ALL ({total_fresh} papers)")
            menu_options[key_view_all] = ("view", total_fresh)
            opt_num += 1

            key_import_all = str(opt_num)
            print(f"  [{key_import_all}] Download PDFs & Import ALL {total_fresh} to Zotero")
            menu_options[key_import_all] = ("import_count", total_fresh)
            opt_num += 1

        print("  [C] Custom Selection (e.g. '1-4, 7, 17' or 'exclude 3, 15-17')")
        print(f"  [S] Switch Sorting to {other_sort}")
        flagship_label = "Show All Journals" if flagship_only else "Filter to Top Flagships Only"
        print(f"  [J] {flagship_label} (Live Toggle)")
        oa_label = "Show All Formats" if oa_only else "Filter to Free / Open Access Only"
        print(f"  [O] {oa_label} (Live Toggle)")
        print("  [Q] Cancel / Return to Menu")
        print("=" * 70)

        default_choice = "2" if current_shown < total_fresh else "1"
        user_choice = input(f"Enter choice or selection (default [{default_choice}]): ").strip()
        if not user_choice:
            user_choice = default_choice

        if user_choice.upper() == "J":
            flagship_only = not flagship_only
            active_list = base_fresh_papers
            if flagship_only:
                active_list = [p for p in active_list if is_top_tier_journal(p.get("journal", ""))]
            if oa_only:
                active_list = [p for p in active_list if p.get("is_oa")]
            current_shown = min(5, len(active_list))
            status_text = "ENABLED (Nature, Science, Cell, Neuron, etc.)" if flagship_only else "DISABLED (all journals)"
            print(f"\n[Journal Filter] Top-tier filter {status_text}.")
            display_paper_batch(active_list, 0, current_shown)
            continue

        if user_choice.upper() == "O":
            oa_only = not oa_only
            active_list = base_fresh_papers
            if flagship_only:
                active_list = [p for p in active_list if is_top_tier_journal(p.get("journal", ""))]
            if oa_only:
                active_list = [p for p in active_list if p.get("is_oa")]
            current_shown = min(5, len(active_list))
            status_text = "ENABLED (Free / Open Access only)" if oa_only else "DISABLED (all formats)"
            print(f"\n[Open Access Filter] Free full-text filter {status_text}.")
            display_paper_batch(active_list, 0, current_shown)
            continue



        if user_choice.upper() == "Q":
            print("\nImport cancelled. No files or library changes were made.")
            try:
                input("\nPress Enter to exit...")
            except (EOFError, KeyboardInterrupt):
                pass
            return

        if user_choice.upper() == "S":
            sort_mode = "citations" if sort_mode == "year" else "year"
            apply_sort(base_fresh_papers, sort_mode)
            new_label = "Most Recent" if sort_mode == "year" else "Most Cited"
            print(f"\n[Sort Updated] Re-organized papers by {new_label}:")
            display_paper_batch(active_papers, 0, current_shown)
            continue

        if user_choice.upper() == "C":
            custom_input = input("\nEnter paper numbers to download (e.g. '1-4, 7, 17' or 'exclude 3, 15-17'): ").strip()
            indices = parse_paper_selection(custom_input, total_fresh)
            if indices:
                papers_to_import = [active_papers[i] for i in indices]
                break
            else:
                print("[Warning] No valid paper numbers found in selection. Try again.")
                continue

        # Check if user typed selection directly at main prompt: e.g. "1-4, 7, 17" or "exclude 3, 15-17" or "-3, 5"
        if any(c in user_choice for c in [",", "-", "!"]) or any(word in user_choice.lower() for word in ["exclude", "except", "not"]):
            indices = parse_paper_selection(user_choice, total_fresh)
            if indices:
                papers_to_import = [active_papers[i] for i in indices]
                break

        if user_choice in menu_options:
            action, count = menu_options[user_choice]
            if action == "view":
                print(f"\n--- Expanding Display: Showing Papers {current_shown + 1} to {count} ---")
                display_paper_batch(active_papers, current_shown, count)
                current_shown = count
            elif action == "import_count":
                papers_to_import = active_papers[:count]
                break
        elif user_choice.upper() in ["ALL", "A"]:
            papers_to_import = active_papers
            break
        elif user_choice.isdigit():
            val = int(user_choice)
            if 1 <= val <= total_fresh:
                papers_to_import = [active_papers[val - 1]]
                break
        else:
            print("Invalid selection. Please choose an option from the menu.")

    if papers_to_import:
        print("\n" + "=" * 70)
        print(f"Selected {len(papers_to_import)} papers to download & import into Zotero:")
        for idx, p in enumerate(papers_to_import, 1):
            safe_title = p['title'].encode('ascii', 'replace').decode('ascii')
            print(f"  {idx:2d}. [{p.get('year', 'Unknown')}] {safe_title[:65]}...")
        print("=" * 70)
        confirm_run = input(f"Proceed with downloading PDFs and injecting {len(papers_to_import)} papers into Zotero Cloud? (Y/n): ").strip().lower()
        if confirm_run not in ["", "y", "yes"]:
            print("\nImport cancelled by user. No files or library changes were made.")
            input("\nPress Enter to exit...")
            return

        print(f"\n[Step 3/3] Downloading PDFs & Injecting {len(papers_to_import)} papers into Zotero Cloud...")

        # Target subfolder
        subfolder_name = "Shank2"
        if "acc" in tag_to_apply.lower() or "cingulate" in tag_to_apply.lower():
            subfolder_name = "ACC Circuitry"
        elif "exm" in tag_to_apply.lower():
            subfolder_name = "pan-ExM References"
        elif "connectom" in tag_to_apply.lower():
            subfolder_name = "Connectomics"
        elif "psd" in tag_to_apply.lower():
            subfolder_name = "PSD Nanoscale"

        target_dir = PDF_STORAGE_DIR / subfolder_name
        target_dir.mkdir(parents=True, exist_ok=True)

        downloaded_count = 0
        print("\nChecking Open Access repositories for full-text PDFs...")
        for p in papers_to_import:
            p["tags"] = ["!unread", "#custom-search", tag_to_apply]
            p["track_name"] = subfolder_name
            pdf_path = finder.pdf_downloader.download_pdf(p)
            if pdf_path:
                p["local_pdf_path"] = str(pdf_path)
                downloaded_count += 1
            else:
                safe_title = p.get('title', '')[:50].encode('ascii', 'replace').decode('ascii')
                print(f"    [-] Paywalled / Subscription: {safe_title}... (Reference & DOI will be added to Zotero)")

        # Push to Zotero Cloud
        collection_key = COLLECTION_MAPPING.get("shank2", "UAJ8BK85")
        if subfolder_name == "ACC Circuitry":
            collection_key = COLLECTION_MAPPING.get("acc_circuitry", "8M4HXIPP")
        elif subfolder_name == "pan-ExM References":
            collection_key = COLLECTION_MAPPING.get("pan_exm", "MZ37DCHK")
        elif subfolder_name == "Connectomics":
            collection_key = COLLECTION_MAPPING.get("connectomics", "9BIMSI9V")
        elif subfolder_name == "PSD Nanoscale":
            collection_key = COLLECTION_MAPPING.get("psd_nanoscale", "9HE6B2MS")

        injected_count = finder.zotero.push_to_zotero_cloud(papers_to_import, target_collection_key=collection_key)

        # Update Master Excel
        try:
            excel_kb = ExcelKnowledgeBase()
            excel_kb.update_knowledge_base(papers_to_import)
            print(f"\n[Excel Update] Logged {len(papers_to_import)} papers into SHANK2_Synaptopathy_Master.xlsx")
        except Exception as e:
            print(f"\n[Excel Note]: {e}")

        print("\n" + "=" * 70)
        print(f"  SUCCESSFULLY INGESTED {injected_count} PAPERS INTO ZOTERO CLOUD")
        print(f"  Target Collection: '{subfolder_name}' | Tags Applied: ['{tag_to_apply}', '#custom-search', '!unread']")
        print(f"  Full-Text PDFs Saved Locally: {downloaded_count}/{len(papers_to_import)}")
        print(f"  Local PDF Vault: {target_dir}")
        print("=" * 70)
        print("\nNEXT STEP TO SEE THEM IN ZOTERO DESKTOP:")
        print("  1. Switch to your Zotero Desktop application.")
        print("  2. Click the green circular SYNC button in the top-right corner (or press Ctrl+Shift+S).")
        print("  3. For any subscription papers without automatic PDFs, right-click the item in Zotero")
        print("     and select 'Find Available PDF' (uses your institutional library access).")
    else:
        print("\nImport cancelled. No files or library changes were made.")

    try:
        input("\nPress Enter to exit...")
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    interactive_finder_menu()
