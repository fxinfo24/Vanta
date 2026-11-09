# Vanta: Strategic Codebase Assessment & Roadmap
**Version**: 1.0.0  
**Status**: Critical Review & Strategic Planning  
**Lead AI**: Antigravity (Advanced Agentic Assistant)

---

## 1. Executive Summary
> **Nov 2026 update:** Phases 1, 3 (partially) and 4 below are done — Product B consolidation, result persistence (`Task.result_data` in DB), `/api/health`, platform prompting, and Apify fallback are implemented and verified (see `STATUS.md`). Remaining: deploy a live backend for the Vercel frontend, raise Apify usage limit, add Flask auth. Note: there is **no heuristic fallback** (earlier text claiming one was falsified); LLM failures surface as section errors.

---

## 2. Detailed Technical Analysis

### 2.1 The "3-Layer" Architecture Integrity
*   **Layer 1 (Directive)**: ✅ Excellent. Detailed SOPs exist in `directives/`.
*   **Layer 2 (Orchestration)**: ✅ **COMPLETED**. `SocialMediaAnalyzer` supports ALL platforms via dynamic dispatch (see STATUS.md for current state).
*   **Layer 3 (Execution)**: ✅ Robust. `ScrapeCreatorsClient` expanded to 20+ platforms. `OpenRouterClient` fully integrated.

### 2.2 Critical "Mismatches" Found
| Category | Issue | Impact |
| :--- | :--- | :--- |
| **Platform Scope** | Promised 10+ platforms; Now supports 20+ (Amazon, TikTok Shop, etc). | **RESOLVED** |
| **Logic Redundancy** | Duplicate `DataCollector` logic normalized via `content_analyzer.py` refactor. | **RESOLVED** |
| **Intelligence** | OpenRouter (Nemotron default) implemented; no heuristic fallback. | **VERIFIED LIVE** |
| **Data Flow** | Universal Adapter pattern connects all components seamlessly. | **RESOLVED** |

---

## 3. Roadmap for the "Best Result"

### 🚀 Phase 1: The "Universal Adapter" & Annealing (Immediate)
*Goal: Bridge the gap between the 10-platform scraper and the 2-platform analyzer while cleaning technical debt.*
*   **Refactor `app/core/analyzer.py`**: Switch from platform-specific collectors to a unified `ScrapeCreators` adapter.
*   **Resolve Code Duplication**: Remove the redundant `DataCollector` class from `app/core/content_analyzer.py` and enforce a "Single Source of Truth" by using `app/core/data_collector.py`. This upholds the core principle in `AGENTS.md`.
*   **Dynamic Routing**: Update the orchestration layer to handle any platform string passed from the frontend (TikTok, LinkedIn, etc.) automatically.
*   **Mock Toggle**: Implement a strict `PRODUCTION_MODE` flag to prevent accidental fallback to mock data in live environments.

### 🌐 Phase 2: Global Connectivity Restoration
*Goal: Get the live application "Talking" again.*
*   **Backend Deployment**: Migrate Flask/Celery stack to **Render.com** (via `render.yaml`) or **Fly.io**.
*   **CORS Hardening**: Synchronize `CORS_ORIGINS` between the new backend URL and the Vercel frontend.
*   **Vercel Sync**: Update `VITE_API_BASE_URL` in the Vercel dashboard to point to the new live API.

### 🧠 Phase 3: AI Intelligence Optimization
*Goal: Maximum ROI from the configured LLM (Nemotron default).*
*   **Platform-Specific Prompting**: Create specialized prompt templates for professional platforms (LinkedIn) vs. entertainment platforms (TikTok/YouTube).
*   **Vision Integration**: Activate the `vision_analyzer.py` for profile pictures and post images to detect "AI-generated" personas (Deepfake detection).

### 🛠 Phase 4: Production Hardening & UX
*Goal: Commercial-grade reliability.*
*   **Result Persistence**: Ensure all results are stored in **JSONB** format in Postgres for instant retrieval (bypassing slow AI re-computation).
*   **Health Dashboard**: Implement a `/api/health` endpoint that checks API connectivity for both ScrapeCreators and OpenRouter.

---

## 4. Final Recommendation
The "Best Result" is achieved by **consolidating the data collection layer and annealing the codebase**. By deleting the redundant/conflicting `DataCollector` logic in the analysis module and strictly pathing all platform requests through the universal `ScrapeCreatorsClient`, we transform Vanta from a fragmented tool into a **lean, production-grade Universal Intelligence API**.

**Next Step Proposed**: Deploy Phase 4: Production Hardening & UX Optimization.

---

## 5. Compliance posture: special-category inference (draft, not legal advice)

This section is a working draft, not a legal opinion. It exists because the
product infers things about people who never agreed to be analysed, and that is
the kind of risk a disclaimer cannot fix.

### 5.1 What is actually inferred

| Output | Where it lives | Likely category |
| --- | --- | --- |
| Political position, axes, party lean | `belief_system` / `political_label` | Art. 9 political opinions |
| Substance use (`drug_alcohol_indicated`) | `behavioral_profile.lifestyle_risks` | Art. 9 health data |
| Intimate relationship pattern (`sectual_habit_or_dynamic`) | `behavioral_profile.relationships` | Art. 9 sex life; the field name itself is also a defect |
| Big Five traits, "resistant vs compliant", attachment style | `content_analysis`, `psychological_resilience` | Not enumerated in Art. 9, but profiling of a person's psychology; becomes special-category wherever it is used to infer politics or health |
| Bot/authenticity likelihood, trust score | `authenticity` | Not special-category; reputational, and wrong scores cause harm |
| Brands, price sensitivity, purchase forecast | `consumer_profile` | Not special-category; economic profiling |

### 5.2 The lawful-basis problem (the honest version)

* **No consent.** The data subject is not a user of this product and has agreed to nothing. GDPR Art. 14 requires telling them within a month that their data was obtained indirectly; nothing in this codebase does that.
* **"Publicly available" is not a lawful basis.** EDPB Guidelines 2/2019 hold that Art. 9(2)(e) ("manifestly made public by the data subject") depends on the subject's intent to make the *special-category* fact public, not merely on posting in public. A public post about electricity bills is not a political-opinion disclosure.
* **Nothing is recorded.** No DPIA, no Art. 30 record of processing, no EU representative, no documented purpose per run. The system currently cannot answer "why was this person profiled and who asked for it" beyond the owning account.
* **The datasets are already inferred.** Snapshots, insights and PDF exports now carry these inferences indefinitely (see 5.4).

### 5.3 Gating (tier T0 implemented, the rest not)

**Implemented:** `privacy.allow_special_category_inference` defaults to `false`
(`config/config.json`, overridable by `ALLOW_SPECIAL_CATEGORY_INFERENCE`). While
closed, the belief engine is never invoked, relationship and substance fields are
omitted from the behavioral schema, any volunteered value is replaced with a
`not_collected` notice, and the UI states why the section is empty. This is the
T0 posture only: there is still no per-run justification, reviewer, consent
capture, region rule or DPIA, so T1 and T2 are unbuilt.

* **T0 - operator and opted-in subjects.** Special-category sections off by default behind a config flag (`ALLOW_SPECIAL_CATEGORY_INFERENCE`, default false in `config/config.json`); the factual layer (cadence, engagement arithmetic, content themes, authenticity signals) stays on. Analysis of the operator's own accounts, or of accounts that opt in, is the only use that needs no legal theory.
* **T1 - public interest / journalistic.** Public figures only; each run records a justification and a reviewer; inferences are not published verbatim; a right-of-reply step before anything ships.
* **T2 - client due diligence.** Written or explicit consent from the subject, a contract limiting purpose, and no employment, credit, insurance, immigration or dating-safety decision may be taken from the output.

Hard blocks that belong in every tier: no subjects under 18, no analysis of private individuals at another person's request (the stalker/ex-partner case), and no EU/UK processing of Art. 9 sections before a DPIA exists.

### 5.4 Retention

**Today:** nothing expires. Raw posts, full analyses, snapshots and quote receipts live in `Task.result_data` and `DossierSnapshot` indefinitely; exports also sit on disk under `data/results/`. There is no purge job in `app/core/tasks.py` and no retention setting in `config/config.json`.

**Target:**

| Data | Retention |
| --- | --- |
| Raw collected posts / dossiers | 30 days |
| Verbatim quote receipts inside analyses | 90 days |
| Snapshots and aggregate metrics (no quotes, no post ids) | 12 months |
| Provider request/response dumps | 24 hours |
| Application logs containing profile ids | 14 days |

The aggregate/quote split is the important part: trend history keeps working after the underlying posts are erased, so retention does not destroy the product's value.

### 5.5 Deletion

**Implemented:** `DELETE /api/tasks/<id>` erases a run, its result payload and its snapshot rows, scoped to the owner, refusing while the run is in flight. This is the only erasure path that exists today. There is **no cascade anywhere else** in the schema (`ondelete`/`cascade` appear nowhere), so deleting a user would orphan their tasks, and there is no bulk "erase this subject across all runs" action.

**Still required:** subject-level erasure across platforms and runs; account deletion that cascades to tasks and snapshots; erasure of on-disk exports; a documented backup TTL (deleted rows persist in backups until those rotate); and confirmation from the data provider about *their* retention, since the scrape pipeline hands it profile ids it may keep.

### 5.6 Adjacent regimes

* **EU AI Act:** inferring emotion from text is not "emotion recognition" under Art. 3(39) (that requires biometric data), so the prohibition in Art. 5 does not apply. But any use to decide on employment, education, credit or access to services pulls this into Annex III high-risk territory - do not sell into those decisions.
* **DSA:** platform terms and the transparency database constrain *how the data was obtained*; scraping remains a terms-of-service question, not a resolved legal one.
* **Output labelling:** anything published must be marked as AI-generated, with the confidence and data gaps attached. The `data_coverage` receipts already provide the substance for that.

### 5.7 Recommendation

Default the special-category sections **off** and sell what is defensible: observable behaviour, engagement arithmetic, content themes, authenticity signals with stated error rates. The psychology, belief, intimate-relationship and substance sections should require consent or a documented public-interest justification per run. Until then, the honest one-line description of the product is *"profiles people's politics, relationships and substance use without their knowledge"* - which is a choice the operator can make, but not one that can be made by accident.
