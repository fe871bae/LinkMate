# LinkMate

AI-powered personal network manager. Free-text notes about people become reviewed contact profiles, and a question in natural language returns up to three contacts with a reason and the source notes, or "no suitable contact". Everything runs on the laptop through Ollama, Chroma and Streamlit.

CECS 451 Term Project, Team 10, CSULB Fall 2026: Antoine Courant, Felix Baechle, Vishal Bahatyani, Mika Brueggemann.

```text
Capture:  note -> LLM extracts JSON profile -> user reviews -> JSON store + Chroma index
Ask:      question -> embedding search -> threshold -> grounded LLM answer -> validation -> label
```

All data in `data/dataset/` is synthetic. The project uses no API keys or other secrets.

| Document | Content |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Components, data flows, interfaces, design decisions, with diagrams |
| [`docs/llm_workflow.md`](docs/llm_workflow.md) | Prompts, API workflow, input and output, limitations, own contribution |
| [`docs/code_guide.md`](docs/code_guide.md) | Reading order of the main files, how to extend the code |
| [`docs/evaluation.md`](docs/evaluation.md) | Method, results, failure analysis and business evidence |
| [`data/dataset/README.md`](data/dataset/README.md) | The synthetic dataset and its format |
| [`docs/phase1/`](docs/phase1/), [`docs/phase2/`](docs/phase2/), [`docs/phase3/`](docs/phase3/) | Course reports and pitch material |

## Install and run

Prerequisite: Python 3.10 or newer ([download](https://www.python.org/downloads/)). Everything else is set up on the first start, which downloads about 1.6 GB and takes a few minutes.

| System | How |
|---|---|
| Mac | Double-click `LinkMate.command` |
| Windows | Double-click `LinkMate.bat` |
| Linux or any terminal | `python3 start_linkmate.py` |

| Step | What happens if it is missing |
|---|---|
| Python | Stops with the download link |
| Environment and packages | Creates `.venv` and installs the pinned packages from `requirements.txt` |
| Ollama | Asks once, then installs it with winget, Homebrew or the official Linux script. Otherwise opens the download page and waits. Starts Ollama if it is not running |
| AI models | Downloads `qwen3:0.6b` and `nomic-embed-text` with a progress display |
| Contacts and index | Loads the synthetic contacts on the very first start, and rebuilds a missing index |
| App | Starts on <http://localhost:8501> or the next free port and opens the browser |

Options: `--yes` installs Ollama without asking, `--no-browser` and `--port N` do what they say, `--package` builds `dist/linkmate.zip` for sharing.

**Manual setup.** The same steps by hand:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
ollama pull qwen3:0.6b
ollama pull nomic-embed-text
.venv/bin/python scripts/seed.py
.venv/bin/streamlit run app/Home.py
```

**Stopping.** Click **Shut down LinkMate** in the sidebar, or press Ctrl+C in the start window. This stops the server and unloads the models. If the start script started Ollama, it stops it too.

**Tested only on macOS** (Apple Silicon, 8 GB of RAM, Python 3.13 and 3.14). The Windows and Linux paths are written but have not been run. The automatic Ollama installation has not been run on any system.

## Configure

All settings are in `config.yaml`: models, search mode, threshold, confidence limit and prompt limits. `LINKMATE_OLLAMA_HOST` and `LINKMATE_DATA_DIR` override the Ollama address and the data folder. Section 6 of the architecture document explains each setting.

To reset the data, stop the app and run this. It removes all contacts in `data/contacts/`, including ones you captured.

```bash
.venv/bin/python scripts/seed.py --reset
```

## Use

| Page | What it does |
|---|---|
| Capture | Paste a note or email, review the proposed profile, then save it as a new contact or add it to an existing one |
| Ask | Ask for a contact in `dense`, `bm25` or `hybrid` mode and see the reason, sources, confidence label, candidates and timings |
| Contacts | Browse contacts with facts and notes, edit a profile, export everything as JSON, delete a contact or a note |
| Status | Check Ollama and models, index sync, corrupt files and LLM latency, rebuild the index, delete the LLM log |

## Reproduce a sample result

Start the app and open **Ask**.

| Enter | Expected result with `qwen3:0.6b` |
|---|---|
| Who could help me calibrate an IMU sensor for my project? | Lena Hoffmann with a reason, a source note and no weak label |
| Who can recommend a good veterinarian for my dog? | No suitable contact |

Then open **Capture** and paste this note. The review form should show the name, role and offer of help. Confirm it, then ask "Who could teach me lead climbing?". The answer should name Mara Lindt with this note as source.

```text
Met Mara Lindt at the Granite climbing gym open day. She is a route setter and physio student in Long Beach. Said she can teach me to lead climb and check my technique on Sundays.
```

Answers can differ on other Ollama versions or platforms, because the model output is only repeatable on one setup.

## Tests and evaluation

```bash
.venv/bin/python -m pytest
```

Unit tests run in a few seconds and need no Ollama. They use a fake LLM and embedder with a real Chroma and JSON store.

```bash
.venv/bin/python scripts/run_e2e.py
.venv/bin/python eval/evaluate.py --split dev
.venv/bin/python eval/evaluate.py --split test
.venv/bin/python eval/scale.py
```

`run_e2e.py` checks system behavior with real models, including rebuild and Ollama failures. `evaluate.py` produces all metrics, baselines, the failure analysis, the bias check and the injection results. `scale.py` adds generated contacts up to 5,055. Reports go to `reports/`. All of them use temporary data folders and never touch your contacts.

## Results

Measured on 40 held-out questions, 30 with a right contact and 10 without, with settings frozen on 30 development questions. Method, analysis and failures are in [`docs/evaluation.md`](docs/evaluation.md).

| System | Right contact | Correct refusal | Fitting recommendations |
|---|---|---|---|
| Keyword baseline (BM25), top hit | 20/30 | 0/10 | 21/39 |
| Dense search, top hit, no LLM | 23/30 | 1/10 | 26/38 |
| LinkMate, all recommendations | 21/30 | 2/10 | 25/35 |
| LinkMate, strong label only | 16/30 | 9/10 | 16/18 |

Direct questions reach 14/14. Paraphrased needs are the hard part, with Recall@3 of 0.75 for dense search against 0.44 for keywords. No recommendation had an invalid source. Extraction gave 70/70 correct names and a fact F1 of 0.69. A question takes 1.2 s at the median on an 8 GB laptop.

## Repository structure

```text
app/                 Streamlit pages, only call services
linkmate/
  models.py          data model
  config.py          loads config.yaml
  infra/             Ollama client, JSON store, Chroma index
  core/              prompts, extraction cleanup, merge, retrieval, validation
  services/          capture, ask, contacts: the only layer that uses infra
scripts/             seed, reindex, check_ollama, run_e2e
eval/                metrics, evaluation, threshold sweep, scale test, attack cases
reports/             generated evaluation reports
start_linkmate.py    checks and sets up everything, starts and stops the app
LinkMate.command     double-click starter for macOS
LinkMate.bat         double-click starter for Windows
data/dataset/        synthetic contacts, notes and labeled questions
tests/               unit tests with fakes
docs/                architecture, LLM workflow, code guide, evaluation, course reports
config.yaml          models, threshold, retrieval mode
```

Generated at runtime and not committed: `data/contacts/` (source of truth), `data/chroma.nosync/` (derived index), `data/logs/llm_calls.jsonl` (every prompt, output and duration).

## Completed and planned

| Status | Item |
|---|---|
| Completed | Capture with review, enrichment of existing contacts, ask with reason and sources, confidence label, contact list with edit, export and delete, status page, one-command setup, 70 labeled questions, full evaluation |
| Written, not tested | Windows and Linux start paths, automatic Ollama installation |
| Planned | Photo and voice input, email and LinkedIn import, mobile-optimized interface, cloud sync |

## Known limitations

- **Weak refusals.** The small model accepts near misses and search scores overlap, so only the strong label is reliable. This is the main weakness.
- **Paraphrased needs** reach 7/16 at answer level. The difference to the keyword baseline is not statistically significant with 40 questions.
- **Invented details in reasons.** The source note is shown next to every reason, and the code checks sources, not wording.
- **Prompt injection.** A keyword rule removes known wording only, and attacks can reach the proposed profile, so every profile goes through the review.
- **Synthetic data, no user test yet.** The pilot in `docs/phase3/user_pilot.md` is prepared, not run.
- **Extraction mistakes.** Where met and organization are the least reliable fields, which is why every profile is reviewed.
- **Deleting a note** removes its facts but keeps fields like role, which it may have set.
- **The LLM log** keeps note texts after a contact is deleted, until you delete the log on the Status page.
- **Seeding or reindexing from a script** while the app runs leaves the app with an outdated index connection. Restart the app afterwards.
- **Scale.** Recall falls above about 2,000 contacts, and all JSON files are read per question.

## Team conventions

All content in this repository is written in English. Work happens on `main` in small, logical commits with imperative messages. The repository holds no secrets or real personal data, only synthetic data.
