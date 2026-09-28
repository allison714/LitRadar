"""
Classifier and Tagging Engine.
LitRadar Suite.
"""

import json
import re
from typing import Dict, List, Any

from config import ZOTERO_TAG_RULES, GEMINI_API_KEY


class PaperClassifier:
    def __init__(self):
        self.gemini_client = None
        if GEMINI_API_KEY:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
                print("[Classifier] Gemini API client initialized.")
            except Exception:
                pass

    def _rule_based_classify(self, title: str, abstract: str) -> Dict[str, Any]:
        combined_text = f"{title}\n{abstract}".lower()
        tags = set(ZOTERO_TAG_RULES["status_tags"])

        detected_targets = []
        detected_methods = []
        detected_diseases = []

        # Tier 2: Targets
        for tag, keywords in ZOTERO_TAG_RULES["genes_and_targets"].items():
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", combined_text):
                    tags.add(tag)
                    detected_targets.append(tag)
                    break

        # Tier 3: Disease & Anatomy
        for tag, keywords in ZOTERO_TAG_RULES["disease_and_anatomy"].items():
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", combined_text):
                    tags.add(tag)
                    detected_diseases.append(tag)
                    break

        # Tier 4: Methods
        for tag, keywords in ZOTERO_TAG_RULES["methods"].items():
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", combined_text):
                    tags.add(tag)
                    detected_methods.append(tag)
                    break

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", abstract) if len(s.strip()) > 20]
        if len(sentences) >= 2:
            tldr = f"{sentences[0]} {sentences[-1]}"
        elif sentences:
            tldr = sentences[0]
        else:
            tldr = "Summary not available; see original publication."

        return {
            "tags": sorted(list(tags)),
            "targets": list(set(detected_targets)),
            "diseases": list(set(detected_diseases)),
            "methods": list(set(detected_methods)),
            "tldr": tldr,
            "pan_exm_antibodies": self._extract_antibodies_rule_based(combined_text),
        }

    def _extract_antibodies_rule_based(self, text: str) -> List[Dict[str, str]]:
        antibodies = []
        if "antibody" in text or "antibodies" in text or "pan-exm" in text:
            matches = re.findall(r"(anti-[a-zA-Z0-9\-_]+|rabbit|mouse|guinea pig|chicken)\s+([a-zA-Z0-9\-_]+)", text)
            for m in matches[:3]:
                antibodies.append({
                    "target": m[1].upper(),
                    "host": m[0].title(),
                    "vendor": "See Paper",
                    "catalog_no": "N/A",
                    "dilution": "N/A",
                    "notes": "Extracted via Pan-ExM / staining keyword scan",
                })
        return antibodies

    def _gemini_classify(self, title: str, abstract: str) -> Dict[str, Any]:
        prompt = f"""
You are an expert neurobiologist reviewing literature on SHANK2, postsynaptic density (PSD) scaffolding (Homer1, GluN1, GluA1), ACC circuitry, and Pan-Expansion Microscopy (Pan-ExM).

TITLE: {title}
ABSTRACT: {abstract}

Taxonomy Rules to match:
1. Status tags: always include ["!unread", "#project-thesis"]
2. Targets: ["SHANK2", "shank2-exon24", "SHANK1", "SHANK3", "homer1", "glun1", "glua1", "postsynaptic-density", "excitatory-synapses", "cortactin", "gephyrin", "mglur5", "hippo-pathway"]
3. Disease/Anatomy: ["ACC", "autism-spectrum-disorder", "schizophrenia", "neurodevelopmental-disorders", "synaptopathy"]
4. Methods: ["pan-exm", "expansion-microscopy", "antibody-validation", "connectomics", "electron-microscopy", "mouse-model", "patch-clamp", "ipsc", "rna-seq", "wes"]

Extract into strictly valid JSON matching this schema:
{{
  "tags": ["list of exact matching tags from above categories"],
  "targets": ["detected biological targets"],
  "diseases": ["detected diseases or anatomy e.g. ACC"],
  "methods": ["detected methodological tools"],
  "tldr": "A 2-sentence crisp, rigorous scientific summary of the primary finding and biological implication.",
  "pan_exm_antibodies": [
    {{
      "target": "target protein (e.g. Homer1, GluA1)",
      "host": "host species if specified (e.g. Rabbit, Mouse)",
      "vendor": "vendor if mentioned or 'Unspecified'",
      "catalog_no": "catalog number if mentioned or 'N/A'",
      "dilution": "dilution ratio if mentioned",
      "notes": "any specific performance notes regarding Pan-ExM, digestion, or staining"
    }}
  ]
}}
Respond with JSON only.
"""
        try:
            response = self.gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception:
            return self._rule_based_classify(title, abstract)

    def classify(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")

        if self.gemini_client:
            res = self._gemini_classify(title, abstract)
        else:
            res = self._rule_based_classify(title, abstract)

        paper["tags"] = res.get("tags", ["!unread", "#project-thesis"])
        paper["targets"] = res.get("targets", [])
        paper["diseases"] = res.get("diseases", [])
        paper["methods"] = res.get("methods", [])
        paper["tldr"] = res.get("tldr", "")
        paper["pan_exm_antibodies"] = res.get("pan_exm_antibodies", [])

        return paper
