# Project documentation

Start with the [root README](../README.md) for the current application and setup instructions.

| File or folder | Purpose |
| --- | --- |
| `AUDIT.md` | Repository findings, cleanup decisions and observed validation results |
| `DATA_AND_ATTRIBUTION.md` | Source inventory, synthetic-data details and third-party material |
| `PUBLISHING.md` | Reviewable scope and proposed GitHub publication |
| `PROVENANCE.md` | Original repository, base commit and authorship retained alongside the fresh publication history |
| `demo.md` | Preserved original demonstration walkthrough; contains historical deployment references |
| `reference/assignment-brief.pdf` | Preserved original assignment brief |
| `figures/` | Local and historical UI screenshots plus supplied diagrams |
| `VU_AI_Academic_Advisor_Documentation.docx` | Existing technical report, preserved as a historical deliverable |

## Optional generation tools

These tools are not required to run ALICE. Install Python extras using `python -m pip install -r docs/requirements.txt` in the backend environment. Install Node report dependencies with `npm ci` from `docs/`.

- `make_figures.py` draws architecture and strategy figures; its optional results chart depends on `eval/summary.json`.
- `build_doc.js` generates the technical DOCX using the `docx` package. It reads some project data dynamically but also contains fixed historical descriptions and counts. Review the generated document before treating it as current documentation.
- `build_report.py` is a legacy assignment report generator. It currently requires missing `eval/agentic_results.json` and `docs/report_findings.json`, Chrome at a hard-coded macOS path, and pandoc. It is preserved but is not a working cross-platform build target in this checkout.
- `backend/make_media.py` generates synthetic transcript fixtures and audio; its audio/typography setup assumes macOS `say` and system font paths.

Running generation scripts can overwrite existing deliverables. Existing figures and reports are retained so normal setup does not depend on these optional tools.
