## 🎬 Walkthrough Video

[▶️ Click here to watch the walkthrough](https://drive.google.com/drive/folders/1RcGZ3KcqwFCDzGMeeaIPEmeXC-CgRA80?usp=sharing)

## 🚀 Live App

[🌐 Open Streamlit App](https://zycustask-npppenpvx42zwcfxxudpep.streamlit.app/)

---

# Zycus Support AI

AI-powered support triage and TAM account health summariser for the Zycus engineering assessment. All core behaviour is deterministic and API-key free by default.

---

## Assessment mapping

| Assessment task | Implementation |
|---|---|
| **Task 1 – Ticket Triage** | `support_ai/triage.py` · `POST /triage` · `cli triage` |
| **Task 2 – TAM Account Brief** | `support_ai/account_brief.py` · `GET /accounts/{id}/brief` · `cli account-brief` |
| **Task 3 – Evaluation Harness** | `support_ai/evals.py` · `scripts/run_eval.py` · `cli eval` · `reports/eval_report.md` |
| **Task 4 – Design Note** | `DESIGN_NOTE.md` |
| **Bonus – Streamlit UI** | `support_ai/ui.py` · `streamlit run support_ai/ui.py` |

---

## Dataset policy

This project ships **without** `data/accounts.json`, `data/tickets.json`, or `knowledge-base/` content. Those are starter files supplied by the assessment environment.

- `cli data-check` and `GET /data-health` report what is present or missing.
- `cli account-brief` and `GET /accounts/{id}/brief` raise clear precondition errors when data is absent — they never fabricate account records.
- Pytest tests use `tmp_path` fixtures only; no production data is created.

---

## Architecture

```
External input
     │
     ▼
data_loader.py          ← schema-flexible JSON loader (accounts + tickets)
kb_retrieval.py         ← lexical KB retrieval (no embeddings)
     │
     ▼
triage.py               ← deterministic rule-based classifier
account_brief.py        ← deterministic TAM brief generator + risk detector
     │
     ├── redaction.py   ← PII redaction (email, phone, IP, long tokens)
     ├── deterministic.py  ← stable_hash, stable_json, clamp_score, …
     └── llm_client.py  ← optional LLM adapter (disabled by default)
     │
     ▼
api.py                  ← FastAPI REST endpoints
cli.py                  ← argparse CLI
evals.py                ← evaluation harness + Markdown/JSON reports
ui.py                   ← optional Streamlit web UI
```

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and populate as needed (all fields have safe defaults).

---

## Commands

```bash
# Check data availability
python -m support_ai.cli data-check

# Triage a ticket
python -m support_ai.cli triage --text "SSO login fails for production users"
python -m support_ai.cli triage --subject "Invoice wrong" --body "Charged twice this month"

# Generate TAM account brief (requires starter data)
python -m support_ai.cli account-brief --account-id <ACCOUNT_ID>

# Run evaluation harness
python -m support_ai.cli eval --output reports/eval_report.md
python -m support_ai.cli eval --output reports/eval_report.json

# Start REST API server
uvicorn support_ai.api:app --reload

# Run tests
pytest -q
```

### Optional Streamlit UI

```bash
pip install -r requirements-ui.txt
streamlit run support_ai/ui.py
```

---

## REST API quick reference

**Health check**
```bash
curl http://localhost:8000/health
```

**Triage a ticket**
```bash
curl -s -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{"subject": "SSO broken", "body": "SAML login fails for all users since 09:00"}' \
  | python3 -m json.tool
```

**Data health**
```bash
curl http://localhost:8000/data-health
```

**Account brief**
```bash
curl http://localhost:8000/accounts/<ACCOUNT_ID>/brief
```

---

## Determinism note

By default (`LLM_PROVIDER=none`) every response is fully deterministic — no LLM is called and no randomness is introduced. If an LLM is enabled (`LLM_PROVIDER=openai`), `LLM_TEMPERATURE=0` and `LLM_SEED=42` are applied to maximise reproducibility. The `stable_json()` helper sorts all keys before serialisation to guarantee identical bytes for identical input.

---

## Known limitations

- **Missing starter data**: If `data/accounts.json` / `data/tickets.json` are absent or empty, `account-brief` and the account brief eval cases report precondition failures rather than producing output. This is by design — the system never fabricates data.
- **KB retrieval**: Lexical overlap scoring (no embeddings). Accuracy improves with a well-structured knowledge base.
- **Triage classification**: Rule-based keyword matching. Edge cases may require tuning the signal lists in `triage.py`.
- **Scale**: Linear JSON scans are adequate for assessment volumes but would need indexed storage at production scale (see `DESIGN_NOTE.md`).

---

## CI Status

![CI](https://github.com/ketan-2905/zycustask/actions/workflows/ci.yml/badge.svg)

Tests run on Python 3.11 and 3.12. Lint enforced via Ruff.

---

## Contributing

1. Branch from `main` using `feat/<topic>` or `fix/<topic>`.
2. Keep commits atomic — one logical change per commit.
3. Run `pytest -q` and `ruff check support_ai/ tests/` before pushing.
4. Open a pull request against `main`; CI must be green before merge.
