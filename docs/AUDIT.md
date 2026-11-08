# Repository audit

Audit date: **8 November 2026 (Asia/Kolkata)**.

## Identity and scope

The user confirmed that the project is an AI academic advisor for students. Its permanent application name is ALICE, short for Academic Learning, Information & Course Explorer. It is a Vidyashilp University DATA308 prototype; it implements no investment or financial portfolio advice.

The starting folder contained an existing Git repository with 26 commits and an `origin` pointing to `Shivshankar8261/academic-advisor-final.version1234`. That remote was public when inspected. The connected GitHub account was `devalpauriyal-cmd`, with read access and no push permission to that remote. The original remote and commit history have not been rewritten. No repository was created or pushed during preparation.

There were already modified backend/frontend source files and new advising modules and tests. Those are the user's existing changes. They were preserved and included in validation; they are not changes made by repository preparation.

The initial eligible-file inventory contained 128 existing files totaling approximately 109.56 MiB. Generated environments, installed packages and build caches were inspected as categories, not audited as first-party source or vendored for publication. All eligible files were inventoried and hashed; source modules, configuration, data representations, document-generation scripts and evaluation tooling were examined. Binary documents were inspected through their extraction/validation paths, office metadata and existing screenshots. This is not a third-party dependency security assessment.

## Application structure

| Area | Responsibility |
| --- | --- |
| `backend/main.py` | FastAPI lifecycle, routes, CORS, headers, request limiting and upload limits |
| `backend/advisor.py`, `prompts.py`, `llm.py` | Strategy routing, context assembly, structured prompting, provider fallback and usage |
| `backend/retrieval.py`, `embedder.py`, `ingest.py` | Local ONNX embeddings, semantic search, chunks and deployment copies |
| `backend/structured.py`, `course_advice.py` | SQL-backed course/basket queries, deterministic answers and advising routes |
| `backend/memory.py`, `academic_term.py`, `profile_context.py`, `clarification.py` | Follow-up context, requested term, profile reconciliation and missing-fact handling |
| `backend/evidence.py`, `agents.py` | Evidence binding, staged planning/checks and optional answer repair |
| `backend/identity.py`, `frontend/app/identity.ts` | Permanent ALICE name and introduction |
| `backend/guard.py` | Input/history scrubbing, refusal rules, optional classifier and output checks |
| `backend/multimodal.py` | Whisper transcription, Gemini image extraction/TTS, confirmed records and SVG generation |
| `backend/extract_data.py`, `make_profiles.py`, `verify_data.py` | Data preparation, synthetic profiles and independent source/database comparison |
| `frontend/app/` | Chat UI, profile/strategy selection, sources, transcript confirmation, recording/read-aloud and traces |
| `eval/` | 296 automated test instances, 43 model-evaluation cases, live runners and historical output |
| `docs/` | Existing report/figures, optional generators, audit, demo and assignment brief |

The request flow is browser → FastAPI safety checks → strategy/context routing → exact data and/or semantic retrieval → optional model generation → evidence/output checks → structured UI response. External providers are used for generation and multimedia; retrieval itself runs locally. Baseline and structured modes intentionally omit retrieved documents.

## Cleanup and preservation

- Created an ignored recovery folder, `.local-backups/before-github-preparation-2026-11-08/`, containing the initial file/hash manifest, Git status/diff and copies of text/configuration files. Credentials were not copied into this backup.
- Compared SHA-256 hashes before moving four redundant root PDF/XLSX files to the recovery folder. The identical canonical originals remain in `data/raw/`.
- Moved the unique assignment PDF to `docs/reference/assignment-brief.pdf` and the original demo script to `docs/demo.md`.
- Moved five unused Next.js starter SVGs out of `frontend/public/` into the ignored recovery folder after checking references.
- Retained source datasets, processed assets, evaluation fixtures/results, original technical report, existing figures and deployment assets.
- Retained `backend/index/data/` duplicates intentionally: `config.py` and `ingest.py` use them for deployments that include only `backend/`.
- Retained the existing approximately 86 MiB ONNX model to preserve startup and deployment behavior; verified its contents and tokenizer against upstream metadata. Added model attribution and license text.
- Left local dependency environments and build caches available for development, while excluding them from Git and the publication archive.
- Replaced the root and frontend scaffold documentation, strengthened ignore rules, added root installation entry points and recorded the observed Python environment in `backend/requirements-lock.txt`.
- Added `scripts/check_repository.py`, a reusable path-only credential-pattern and file-size check.

Preparation did not change application logic, package versions, data extraction, SQL contents, prompts, model choices or test assertions. The new environment example reflects existing configuration defaults; it does not alter existing local credentials or runtime settings.

## Verification

Environment: Windows, Python **3.13.15**, Node.js **24.21.0**, Next.js **16.3.6**. The optional dependency snapshot records all installed Python packages, including documentation/test tools; the ordinary runtime requirements retain their original ranges.

| Check | Result and scope |
| --- | --- |
| `python -m pytest eval -q -p no:cacheprovider` | **296 passed**, one Starlette/AnyIO deprecation warning. Existing tests include advising, context, clarification, identity and evidence cases. A second run with placeholder keys and external socket connections blocked also passed all 296 tests with zero attempted external connections. |
| `python backend/verify_data.py` | **Passed**, zero source/store mismatches. Checks independently parsed spreadsheet rows, credits and basket requirements, plus PDF/index coverage. |
| API and retrieval smoke check | **11 passed**: startup/health, 10 profile summaries, ALICE greeting, attendance rule, exact Foundation table, injection refusal, unknown profile, blank message, invalid image signature, course SVG and real ONNX retrieval. TestClient ran the app lifespan; the external classifier was stubbed. |
| `npm run lint` | **Passed**. |
| `npm run build` | **Passed**, including TypeScript and static-page generation. First sandboxed attempt failed downloading Geist fonts; the permitted network-enabled rerun passed. No application code was changed to bypass the download. |
| Browser screenshot | The production frontend and backend were started locally; headless Chromium captured `docs/figures/alice-home.png`. The displayed header reported online. This is a visual startup check, not a full interactive browser test. |
| Credential-pattern scan | **No findings** in current eligible files or **200 reachable historical blobs**. Checks Groq/Google/GitHub/AWS key forms, private-key headers and credential-bearing URLs, including XML inside Office archives. |
| Local key cross-check | Actual local backend API-key values were compared in memory against Git history; no occurrences found. Values were not printed or copied. |
| Integrity comparison | Existing backend, frontend application, data and evaluation file hashes were compared with the pre-preparation snapshot; application and dataset content was preserved. |

The scan is heuristic and cannot establish that every kind of credential or personal information is absent. Real `.env` files remain locally ignored. The full live-model evaluations, model-backed prompt classifier, speech transcription, image extraction and cloud TTS were **not rerun**. No fresh accuracy/latency claim is made from the older result files.

## Findings and limitations

1. **Source quality:** the independent audit reported **47 source-file problems**, including missing prerequisite definitions, unassigned/TBA/TBD courses, malformed/overlaid PDF pages and 2026 credit conflicts. These are separate from extraction mismatches, of which none were found.
2. **Static term:** the current-term context is derived from the supplied 2026 documents, not synchronized with a university calendar. Explicit term/semester routing exists, but the default can age.
3. **Demo identity:** the profile selector is unauthenticated and uses synthetic records. Production access control and real student-record integration are absent.
4. **Provider availability:** configured model names, limits and static cost estimates may age. Existing API keys were not disclosed or republished, and current generation/multimedia availability was not certified.
5. **Privacy:** rules scrub selected patterns from text. Uploaded image/audio bytes still go to external providers, and output-only identifier omission is not pre-transmission anonymization. No application-level persistence does not prove provider deletion.
6. **Safety limits:** the optional classifier fails open when unavailable. Per-IP limiting is per instance and trusts a forwarded-IP header. CORS does not authenticate requests. These controls do not make the service production hardened.
7. **Verification limits:** keyword/rule-based evaluation and evidence checks are incomplete. Structured model fields and citations are useful signals, not proof of factual correctness.
8. **Historical docs/results:** the old README claimed 25 cases; this tree has **43**. Existing reports contain earlier counts and deployment claims. Current inventory is **148 catalogue entries, 439 chunks, 470 SQL course rows, 10 synthetic profiles**. The original report is preserved and labeled historical.
9. **Report tooling:** `docs/build_report.py` needs missing `eval/agentic_results.json` and `docs/report_findings.json`; it also assumes macOS Chrome and pandoc. Media regeneration assumes macOS `say` and font paths. Normal app startup uses prebuilt assets and does not need these generators.
10. **Redistribution:** no root code license or permission to redistribute the university materials was found. The raw and derived documents, branding and assignment brief are listed for owner review in `DATA_AND_ATTRIBUTION.md`. Existing Git authorship is retained.

## Publication status

The owner subsequently approved public publication and requested an isolated copy with a fresh Git history. That copy was created from the checked review archive; the original working tree and remote were left unchanged. The new history retains source attribution through `PROVENANCE.md`. See `PUBLISHING.md` for the approved scope. A local archive alone is not evidence of an upload.


## Isolated publication-copy verification

The publication copy was created from the checksum-verified review archive in a separate local directory. It contains no original `.git`, provider `.env` files, virtual environment or build/dependency cache. A fresh `main` repository was initialized there; the original repository was not reset, rebased or force-pushed.

In the isolated copy, 84 application/data/test files were hash-compared with the preserved working project and matched. All 296 tests passed again with placeholder provider keys and external connections blocked (zero external connection attempts). Its frontend dependencies were installed independently from the unchanged npm lockfile; ESLint and the production build, including TypeScript, passed. The current UI screenshot represents the same unchanged application source. Provider-backed AI services remain outside the verified scope described above.
