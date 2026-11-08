# Data and attribution

This repository contains project code and third-party materials with different ownership. Publication of the repository does not itself grant a license to the university documents, assignment brief, branding or pretrained model.

## University sources

The application reads these canonical source files. The citation names in generated answers preserve the names used by the original project; local filenames are normalized.

| Local file | Document represented |
| --- | --- |
| `data/raw/student_handbook_aug2026.pdf` | Vidyashilp University Student Handbook, August 2026 |
| `data/raw/sop_students_aug2026.pdf` | Student Standard Operating Procedures, 17 August 2026 |
| `data/raw/semester_spread_structures_sept2026.xlsx` | B.Tech semester spread and programme structures, September 2026 |
| `data/raw/minor_courses_btech.xlsx` | B.Tech minor-course lists supplied with the assignment |

`docs/reference/assignment-brief.pdf` is the supplied GenAI assignment brief. `frontend/public/vu-logo.png` is university branding. These files were present before repository preparation; no redistribution permission or project-wide license was found. Retaining them locally does not establish permission to republish them.

The extracted Markdown/JSON, SQL database, `backend/index/chunks.json`, embeddings, deployment copies, reports and some screenshots derive from those materials. Excluding only the raw files would not remove all source-derived content. The source documents and code also contain university office contact details. These are institutional contacts copied from source material, not invented student profiles.

Before public publication, the owner should confirm that the intended distribution of the included material is permitted. If that cannot be confirmed, prepare a version with appropriately licensed replacement documents and regenerate all derived assets rather than merely hiding the original PDFs.

## Synthetic student data

`backend/make_profiles.py` generates 10 synthetic profiles in `data/synthetic/student_profiles.json`. Invented grades and scenarios are combined with course data from the supplied spreadsheets. Synthetic media fixtures and their expected answers are under `data/synthetic/multimodal/`.

These fixtures are intended for demonstration and testing. They are not real transcripts or official academic records. The unauthenticated profile selector must not be populated with real student records.

User-uploaded images and audio are processed in memory by the application and sent to external providers for extraction/transcription. The extraction prompt excludes identifying fields from its output; it does not redact an image before sending it. Provider terms and retention settings are separate from this application's behavior.

## Embedding model

The original project identifies `backend/models/all-MiniLM-L6-v2/model.onnx` and `tokenizer.json` as the ONNX export and tokenizer of [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2). The upstream model card identifies its license as Apache-2.0. See the [upstream model files](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/main) for the authoritative license and metadata.

The preparation matched both bundled files against upstream file metadata at revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`: SHA-256 for the ONNX LFS object and Git blob SHA-1 for the tokenizer. This establishes matching contents at that revision, not the original download date. See `backend/models/README.md` for local SHA-256 checksums. Upstream declares Apache-2.0 in the model metadata but does not contain a separate LICENSE file at that revision; a copy of the standard license from Apache is included alongside the model. Preserve applicable license/notice requirements when redistributing model assets. Do not infer that the model's license applies to this project's code or university data.

## Project code and historical artifacts

No root code license was found or assigned during preparation. The existing `docs/package.json` contains an `ISC` package metadata field; it does not establish permission to license all repository content. This publication uses a fresh Git history at the owner's request. [Project provenance](PROVENANCE.md) records the original source repository, base commit and existing authorship; the new history does not assert sole authorship.

The existing technical DOCX report, diagrams, evaluation responses and demo walkthrough are historical project artifacts. They may use earlier names, counts, provider choices and deployment links. The checked source tree and the dated audit are the basis for current feature and validation claims.
