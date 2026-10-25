# LastPing

Search for the signal that survived.

LastPing is a local Streamlit console that compares three detection approaches on simulated CubeSat-like radio recordings:

1. Signal-strength threshold
2. Physics-guided detection
3. A small trained ML classifier (when the backend provides one)

This checkout currently ships a working interface and a **placeholder** analysis engine. Detector science is intentionally pending.

## Setup

Python 3.11+ is required.

```bash
cd /Users/big_ali07/CalHacks
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Start

```bash
source .venv/bin/activate
streamlit run app.py
```

The app listens on http://localhost:8501 by default.

## Usage notes

- Sidebar controls do not regenerate results until **Analyze**.
- **Reset** restores San Francisco observer defaults and clears results.
- **Run benchmark** is a separate action and does not train a model.
- Radio data is simulated. Orbit fields stay unlabeled until public orbital data is connected.
- Result language is limited to **Candidate beacon** and **Insufficient evidence**. The UI never displays “Satellite recovered”.
- ML scores are labeled **synthetic-model score**, not real-world probability.

## Project layout

| Path | Role |
| --- | --- |
| `app.py` | Streamlit interface |
| `core/engine.py` | `analyze(config)` and `benchmark()` contract |
| `HANDOFF.md` | Backend implementation notes |
