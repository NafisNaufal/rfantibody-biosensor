# Novelty & Prior-Art Assessment

**Date:** 2026-08-04
**Purpose:** Establish where a defensible novelty claim lies for a Q1 manuscript, and which framing maximises acceptance odds.
**Method:** ARS `deep-research` full mode (Phases 1–3). Prior-art triangulation, not a PRISMA systematic review.
**Status:** Phases 1–3 complete. Phases 4–6 (formal APA report, editorial review, ethics clearance) not run — deliberately deferred until framing is chosen, since the report should be written to the selected claim.

---

## 1. Project under assessment

Computationally designed de novo nanobodies (RFantibody: RFdiffusion → geometry filter → ProteinMPNN → RoseTTAFold2 blind re-prediction → PRODIGY ΔG → weighted composite + CDR clustering) against three *Enterococcus faecalis* surface proteins:

| Target | Structure | Hotspot (spot1) |
|---|---|---|
| Ace | 2Z1P (collagen-adhesin domain) | A180,A182,A193,A195 |
| EbpC | 9LLW (pilus shaft N-term domain) | A61,A62,A63,A64,A65,A67 |
| Esp | AlphaFold model | A69,A71,A74 |

**Wet-lab architecture:** nanobodies displayed on *E. coli* BL21 (non-DE3) via β-intimin scaffold (BioBrick K4765001/K4765106, from Addgene #115602), IPTG-inducible. Readout is engineered **co-aggregation** with *E. faecalis* ATCC 29212 — macroscopic floc formation quantified as co-aggregation index by OD600 sedimentation over 24 h. Controls: null-adhesin (intimin scaffold, no VHH passenger) and no-IPTG. Display confirmed by anti-FLAG Western, flow cytometry, CLSM.

**Resource profile (decisive for strategy):** GPU-rich (DGX), gene-synthesis-poor. Timeline: iGEM jamboree first, manuscript 6–12 months after.

---

## 2. Primary research question

> Where does a defensible novelty claim lie for a whole-cell bacterial biosensor that uses computationally de novo designed nanobodies as programmable specificity modules driving engineered co-aggregation-based detection of *Enterococcus faecalis*?

**FINER: 4.4/5** (Feasible 4, Interesting 5, Novel 4, Ethical 4, Relevant 5). Feasibility is capped at 4 because the question asks partly for a *negative* claim, which can only be established as "no precedent found under documented search strategy" — never as proven absence.

---

## 3. Gap map — the core result

| Claim | Verdict | Evidence |
|---|---|---|
| Nanobody display on *E. coli* via intimin | **OCCUPIED** | [5] — Neae-intimin platform, ~8,000 Nb/cell |
| Intimin-Nb as detection element in whole-cell biosensors | **OCCUPIED** | [5], explicitly reported |
| Engineered bacterial co-aggregation via Nb/antigen pairs | **OCCUPIED** | [1]; extended to living materials [6] |
| Intimin-Nb display + co-aggregation readout **in iGEM** | **OCCUPIED** | ELTE 2022, UNIZAR 2021 [13]; **K4765106 is itself an iGEM part** |
| De novo designed binders in **living mammalian** cell sensing | **OCCUPIED** | [2] — LCB1/LCB3 + EGFR minibinders in synNotch/SNIPR/CAR (Jurkat, primary CD8+ T, K562) |
| De novo designed binders **displayed on a living bacterial surface** | **UNOCCUPIED** | [2] explicitly reports *no* bacterial display |
| **De novo nanobody as specificity module of engineered bacterial co-aggregation** | **UNOCCUPIED** | Junction of [1]+[2]+[5]; no paper found joining them |
| Nanobody-based detection of *E. faecalis* Ace/EbpC/Esp | **UNOCCUPIED** for nanobodies | Only conventional polyclonal/ELISA work found [9,10] |

### The defensible claim

Every published nanobody in these bacterial display/adhesion systems was obtained by **animal immunisation + library selection** (dromedary/llama immune libraries [5]). The novelty is **replacing immunisation and selection entirely with structure-based computational design**, making the platform *animal-free and retargetable to any structurally-characterised surface antigen without a wet-lab selection campaign.*

Narrow, but real — and a *platform* claim rather than a one-off, which is what lifts it toward Q1.

### What must NOT be claimed

"First de novo binder in a whole-cell biosensor" — [2] beat this in 2024 (mammalian). Claiming it invites desk rejection.

---

## 4. Three findings that should change the plan

### 4.1 The hit-rate math is brutal; 30 candidates is underpowered
Independent evaluation found RFdiffusion binders failing for most targets via low expression, non-specific binding, or undetectable affinity [3]. Reported RFantibody hit rates span 0.1–39 % depending on definition, but practitioner guidance points to **~0–2 % per target with panels of 10³–10⁴**, because RF2 is a weak binder/non-binder discriminator. **At 30 candidates and 2 %, expected hits ≈ 0.6.**

### 4.2 Esp is a poor primary target — demote or drop
- `esp` is *enriched in* infection-derived isolates, not universal [9] → an Esp-only sensor structurally cannot detect esp-negative strains.
- Esp was found **not to be a target of opsonic or protective antibodies** in *E. faecium* infection [10].
- Esp not essential for adhesion/colonisation [11].
- The target structure is an **AlphaFold model, not experimental**.

Ace (core collagen adhesin) and EbpC (pilus shaft) are stronger on both design confidence and biological justification.

### 4.3 A proven iGEM → Q1-adjacent path exists
iGEM Thessaly's whole-cell pathogen biosensor was published in *ACS Synthetic Biology* [8]. Direct precedent for this team, framing, and venue.

---

## 5. Devil's Advocate — surviving objections

**Checkpoint 1 (scoping)**
1. **Motivated reasoning risk.** The team wants the gap to exist. Mitigated by running deliberate refutation searches — which *did* surface partial occupation [2].
2. **Novelty ≠ publishability.** A gap can exist because nobody cared. Every claimed gap needs a "so what" test.
3. **CRITICAL: the data does not exist yet.** Zero wet-lab results. Manuscript viability is contingent on experiments not yet run. No prior-art finding changes this.
4. **Scope too broad.** Platform novelty and hit-rate benchmarking are plausibly two manuscripts.
5. **The "de novo" claim is attackable.** All 30 designs share one VHH framework (`QVQLVESGGGLVQPGGSLRLSCAAS…WGQGTLVTVS`); only H1/H2/H3 vary. RFantibody designs *CDR loops onto a fixed scaffold*; it does not generate novel folds. **Always write "de novo designed CDRs on a fixed VHH framework," never "de novo protein."**

**Checkpoint 2 (post-search)**
- Counter-evidence search performed; partial occupation found and incorporated.
- "Why not just immunise a llama?" must be answered explicitly: target-agnostic speed, no animals, epitope control, ability to target poorly immunogenic or unpurifiable antigens.
- Novelty rests on a negative claim → **re-run the same searches on Scopus/Web of Science before submission and document the strategy.**

---

## 6. Venue recommendation

| Venue | Fit | Odds |
|---|---|---|
| **ACS Synthetic Biology** | **Best fit.** Q1 in synthetic biology; direct iGEM precedent [8]; values platform + device demonstration; tolerant of modest hit rates if honestly framed | **Realistic** |
| Biosensors & Bioelectronics / ACS Sensors | Application-first; will demand LOD, specificity panels, real matrix (urine/water), comparison to gold standard. PBS-based assay insufficient without more work | Moderate–hard |
| Nature Communications | Needs a striking result — high hit rate, multiple targets working, or a genuine methods advance | Low without exceptional data |
| Briefings in Bioinformatics / PLOS Comp Biol | Viable if pivoting to computational contribution + small validation | Realistic, lower impact |

**Recommendation:** ACS Synthetic Biology, platform framing.
Working title shape: *"Animal-free retargeting of engineered bacterial co-aggregation using computationally designed nanobodies."*

---

## 7. Strategic recommendation (GPU-rich / synthesis-poor)

Resource constraints and the science point the same direction. **Do not spend scarce synthesis on 30 unfiltered designs** — at a 0–2 % base rate that likely buys zero hits and no paper. Spend DGX compute raising the hit rate *before* ordering anything:

1. **Counter-screening** against *E. faecium* orthologs and commensal surface proteins — compute-only, closes the specificity hole, legitimate methods contribution.
2. **Developability filtering** — aggregation propensity, pI, unpaired cysteines, *E. coli* expressibility. [3] shows low expression is a dominant failure mode and it is computationally filterable.
3. **Massive oversampling** — 10³–10⁴ per target, then filter hard. This is what the literature recommends and what the DGX is for.
4. **Ablation study on the filter cascade** — which filters actually matter. Combined with wet-lab outcomes this becomes the "which computational metrics predict experimental success" analysis the field lacks.
5. **Then synthesise a small decisive panel** — top designs across Ace + EbpC, **plus a positive control** (e.g. anti-GFP Nb / GFP-display pair).

**The positive control is the single most important de-risking decision.** Without it, a 0/30 result cannot distinguish "our designs failed" from "our assay doesn't work" — and that ambiguity is fatal to the manuscript. With it, a null de novo result still yields an honest, citable benchmark paper.

### Known blocker for the metric-correlation analysis
`select_designs.py` gates PRODIGY behind pAE/RMSD/lDDT, so **failures have no ΔG** (`nan`). Any "which metric predicts binding" analysis would be computed on a badly truncated sample. Fix before wet-lab data lands: run PRODIGY unconditionally on a random subsample that includes failures.

---

## 8. Methodological gaps — contribution vs. baseline rigour

| Gap | Verdict |
|---|---|
| No counter-screening against homologs | **Publishable contribution** — and required for any specificity claim |
| No developability filtering | **Publishable contribution** — directly targets the dominant failure mode [3] |
| Hand-set, unvalidated composite weights | Contribution *if* validated against outcomes; otherwise baseline rigour |
| PRODIGY ΔG outlier artifacts (−55, −44 kcal/mol seen alongside poor pAE/dock) | Baseline rigour — needs principled handling, not eyeballing |
| Target-aligned RMSD corruption on residue-numbering gaps (EbpC/9LLW, gap 49–59) | Baseline rigour — currently *bypassed* with `--rmsd-cutoff 999`, which is indefensible in a manuscript. Must be fixed, not worked around |

---

## 9. Sources

1. Glass DS & Riedel-Kruse IH (2018). A Synthetic Bacterial Cell-Cell Adhesion Toolbox for Programming Multicellular Morphologies and Patterns. *Cell* 174(3):649–658. https://www.sciencedirect.com/science/article/pii/S0092867418308444
2. Weinberg ZY, Soliman SS, Kim MS, et al. (2024). De novo-designed minibinders expand the synthetic biology sensing repertoire. *bioRxiv* 10.1101/2024.01.12.575267. https://pmc.ncbi.nlm.nih.gov/articles/PMC10827046/
3. RFdiffusion Exhibits Low Success Rate in De Novo Design of Functional Protein Binders for Biochemical Detection (2025). *bioRxiv* 10.1101/2025.02.07.636769. https://www.biorxiv.org/content/10.1101/2025.02.07.636769v1
4. Bennett N, et al. Atomically accurate de novo design of antibodies with RFdiffusion. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10983868/
5. Salema V & Fernández LÁ (2017). *Escherichia coli* surface display for the selection of nanobodies. *Microbial Biotechnology* 10(6). https://enviromicro-journals.onlinelibrary.wiley.com/doi/full/10.1111/1751-7915.12819
6. Programmable living assembly of materials by bacterial adhesion (2021). *Nature Chemical Biology*. https://www.nature.com/articles/s41589-021-00934-z
7. ssDNA recombineering boosts in vivo evolution of nanobodies displayed on bacterial surfaces (2021). *Communications Biology*. https://www.nature.com/articles/s42003-021-02702-0
8. A Whole-Cell Biosensor for Point-of-Care Detection of Waterborne Bacterial Pathogens. *ACS Synthetic Biology*. https://pubs.acs.org/doi/10.1021/acssynbio.0c00491
9. Infection-derived *Enterococcus faecalis* strains are enriched in esp. PMID 9864215. https://pubmed.ncbi.nlm.nih.gov/9864215/
10. Enterococcal surface protein … is not a target of opsonic and protective antibodies. PMID 20522627. https://pubmed.ncbi.nlm.nih.gov/20522627/
11. Esp is not essential for cell adhesion and intestinal colonization. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2639590/
12. De novo design of epitope-specific antibodies via a structure-driven computational workflow (2025). *Nature Communications*. https://www.nature.com/articles/s41467-025-67361-9
13. iGEM Registry: [BBa_K4765106](https://parts.igem.org/Part:BBa_K4765106); [ELTE 2022](https://2022.igem.wiki/elte/description); [UNIZAR 2021](https://2021.igem.org/Team:UNIZAR/Implementation)

---

## 10. Verification caveats

- **[3] and [13] were identified via search but not retrieved in full** (HTTP 403). Their titles, URLs and headline findings are recorded as returned by search; **verify full text before citing in the manuscript.**
- **[2] was directly retrieved and verified** — the "no bacterial display" finding, on which the central novelty claim depends, is confirmed from the source itself, not inferred.
- Negative claims here mean *"no precedent found under this search strategy"*, never proven absence. Databases searched: OpenAlex/Semantic Scholar/PubMed/bioRxiv via web search, plus iGEM Registry. **Scopus and Web of Science were not searched** — do this before submission.
- **AI disclosure:** literature search and synthesis were AI-assisted (Claude Opus 5, ARS deep-research skill). All citations resolve to real, retrievable sources; none were generated from memory.

---

## 11. Open decisions

- [ ] Zero-hit contingency — positive control **strongly recommended**; not yet decided
- [ ] Final framing (platform vs. application vs. methods) → determines venue
- [ ] Whether Esp stays in the panel
- [ ] Scopus / Web of Science confirmation search before submission
- [ ] Fix (not bypass) the EbpC target-RMSD metric
