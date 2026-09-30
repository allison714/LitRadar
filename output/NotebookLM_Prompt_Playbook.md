# 🎙️ Google NotebookLM: Master Research & Podcast Prompt Playbook
> **LitRadar Companion Guide** • *Ready-to-Copy Prompts for Weekly Literature Syntheses*

When you upload your weekly PDF bundle or markdown dossiers into [Google NotebookLM](https://notebooklm.google.com), use these prompts to extract maximum insight or customize your 2-host audio podcasts.

---

## 🎧 Category A: Audio Overview (Podcast) Customization Prompts
*Where to paste:* In NotebookLM, click **Audio Overview** $\rightarrow$ **Customize** (the pencil icon next to Generate).

### 1. The Rigorous Journal Club Deep Dive (Recommended)
```text
Act as two senior principal investigators and neurobiologists leading a high-level journal club. Focus the discussion on:
1. The exact mechanistic claims made regarding synaptic scaffolding (SHANK2/Homer1/GluN1) and circuitry (ACC/Connectomics).
2. Methodological rigor: Scrutinize imaging techniques (especially Pan-Expansion Microscopy / super-resolution), sample sizes, antibody validation, and controls.
3. Healthy scientific disagreement: Have the two hosts debate whether the authors' conclusions are fully justified or if alternative interpretations exist.
4. Conclude with 2 active-recall questions for the listener.
```

### 2. The Methods & Protocols Deep Dive
```text
Focus exclusively on the experimental methods, protocols, reagents, and technical breakthroughs across these papers. Highlight specific antibody clones, tissue clearing / expansion factors, patch-clamp parameters, and computational reconstruction pipelines. Explain how a researcher in the lab can reproduce or adapt these techniques.
```

### 3. The Translational & Clinical Perspective
```text
Discuss these papers from a neurodevelopmental and translational psychiatry standpoint. Connect the molecular synaptopathy findings to autism spectrum disorders, behavioral phenotyping in mouse models, and therapeutic opportunities.
```

---

## 💬 Category B: NotebookLM Chat Prompts (Copy & Paste directly into Chat)

### 4. Cross-Study Synthesis & Consensus Matrix
```text
Generate a cross-study comparison table for all uploaded papers with the following columns:
- Study (First Author, Year)
- Primary Biological Question
- Key Experimental Model (e.g., Exon 24 KO mice, human iPSCs)
- Key Finding / Molecular Mechanism
- Methodological Innovations & Limitations
Where do these studies agree, and what are the major contradictions?
```

### 5. Antibody & Reagent Extraction (For Pan-ExM / Imaging)
```text
Extract all antibodies, fluorophores, gel chemistry reagents, and expansion microscopy protocols mentioned across these papers. Format the output as a clean table: Target Antigen | Host Species | Dilution / Protocol Note | Source Paper.
```

### 6. Critical Vulnerability Analysis
```text
Critique these papers like a tough peer reviewer for Nature Neuroscience. Identify the top 3 potential technical artifacts, confounding variables, or unaddressed alternative hypotheses across these studies.
```

### 7. Future Hypothesis Generator
```text
Based on the combined findings of all attached papers, propose 3 novel, testable hypotheses for our next lab project, including proposed experimental assays and predicted outcomes.
```
