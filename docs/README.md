# Documentation

| Path | Content | Status |
|---|---|---|
| `architecture.md` | System architecture, derived from the code | Current |
| `llm_workflow.md` | Prompts, API workflow, input and output, limitations | Current |
| `code_guide.md` | Reading order and how to extend the code | Current |
| `evaluation.md` | Evaluation method, results and failure analysis | Current |
| `figures/` | Diagrams and charts used in the reports | Current |
| `phase1/` | Phase 1 report, as submitted on Oct 16, 2026 | Final, do not edit |
| `phase2/` | Prototype Progress Report (LaTeX, max. 2 pages), due Nov 20, 2026 | Ready for review |
| `phase3/` | Combined Final Report (max. 8 pages) and pitch material, due Dec 11, 2026 | Ready for review |

## Building the reports

Upload the folder to Overleaf, or compile locally with any TeX distribution or Tectonic:

```bash
cd docs/phase2
tectonic progress_report.tex
```

The reports read figures from `docs/figures/`. LaTeX build files are ignored by `.gitignore`. Charts are rebuilt with `.venv/bin/python docs/figures/make_charts.py` from the JSON files in `reports/evaluation/`.
