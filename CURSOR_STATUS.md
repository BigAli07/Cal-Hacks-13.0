# Cursor status — LastPing interface

Date: 2026-10-25

## Publish

| Item | Value |
| --- | --- |
| Target repository | https://github.com/BigAli07/Cal-Hacks-13.0 |
| Prompt URL | `<REPOSITORY_URL>` (placeholder in the request; this public repo is the matching Cal Hacks 13.0 GitHub project) |
| Remote verified | `origin` = `https://github.com/BigAli07/Cal-Hacks-13.0.git` |
| Branch | `cursor/interface` |
| Interface commit | `83ec659de130eeed282341a769e99012c36d997f` |
| Push | pending at time of writing this file; verified after `git push` |
| PR | opened after push; not merged |

Also present on GitHub: private `BigAli07/cal-hacks` (vision/pi/web, branch `codex/vision-checkpoints`). That is a different project. It was not overwritten.

## Codex backend on GitHub — unavailable

Inspected:

- `git fetch origin` on `Cal-Hacks-13.0`: only `main` (`a8234cb` README-only initial commit).
- No `CODEX_STATUS.md` on this repo or in GitHub code search under `BigAli07`.
- No Codex LastPing branch on `Cal-Hacks-13.0` or `cal-hacks`.

Codex source used for comparison only (not committed here): local zip `/Users/big_ali07/Desktop/lastping-project.zip` (`HANDOFF.md`, `core/engine.py`, Codex `app.py`). That zip is **not** a GitHub branch. Do not treat it as published.

## Interface components implemented

Cursor `app.py` + `.streamlit/config.toml`:

- Header LastPing / “Search for the signal that survived”
- Provenance badges (radio / orbit / cache / model)
- Placeholder banner
- Sidebar: observer lat/lon (SF defaults), four presets, signal excess, interference, seed, Analyze, Reset
- Satellite/catalog/epoch/source/time metadata
- Plotly waterfall (x = Hz offset, y = seconds, color = relative dB)
- Predicted / detected / ground-truth overlays
- Three method cards: threshold, physics, ML
- Evidence, benchmark button, JSON download, provenance expander
- Empty / error / pending-null-score / missing-model copy
- Session state: Analyze required; Reset clears; benchmark separate

Placeholder backend shipped on this branch (so the UI runs): `core/engine.py` `analyze` / `benchmark`, plus unused-by-UI `analyze_recording` in `core/recordings.py`.

## Screens/controls connected to real Codex functions

**None.** This branch still calls Cursor placeholder `analyze` / `benchmark`. Codex functions were not on the remote and were not copied onto this branch (would overwrite Codex ownership and break the current UI schema).

Disconnected / not in Cursor UI: recording upload, CelesTrak fetch, Train classifier, Codex preset names, observer Berkeley vs SF, `methods.baseline`.

## Browser checks actually performed

Earlier in the Cursor session against `streamlit run app.py` (placeholder engine), not against Codex:

- Empty state, Analyze, 96×192 heatmap, Pending + null scores, JSON download, Reset, benchmark **Status: Pending**
- Ground-truth toggle default off
- Visual QA of navy/cyan/amber layout

Not re-run against a combined Codex+Cursor app (does not exist on GitHub).

## Compatibility with Codex’s actual API (from the Desktop zip)

Codex `analyze(config)` / `benchmark()` names match, **payloads do not**.

| Topic | Cursor UI / this branch | Codex zip `core/engine.py` |
| --- | --- | --- |
| Config keys | `observer_lat_deg`, `observer_lon_deg`, `preset`, `signal_excess_db`, `interference`, `seed` | `SimulationConfig`: `preset`, `seed`, `signal_excess_db` (+ `n_time`, `n_freq`, `duration_s`, `span_hz`). Extra kwargs **raise TypeError**. |
| Presets | `strong_beacon`, `faint_intermittent`, `interference_only`, `noise_only` | `noise_only`, `weak_beacon`, `intermittent_beacon`, `beacon_with_interference` |
| Observer | SF 37.7749, −122.4194, UI-controlled | Hardcoded Berkeley 37.8715, −122.273 in `orbit.py`; no lat/lon in `analyze` config |
| Interference | separate bool | encoded in preset `beacon_with_interference` |
| Spectrum | `spectrum.times_s`, `frequency_offsets_hz`, `power_db` [T][F] relative dB | `axes.time_s`, `axes.frequency_hz`, `observed_power` linear power [T][F]; Codex UI does `10*log10` |
| Tracks | `prediction.{times_s,frequency_offsets_hz}`, `detected_track` or null | `tracks.predicted_hz` / `detected_hz` / `ground_truth_hz` aligned to time axis; Hz may include nulls |
| Method keys | `results.threshold` / `physics` / `ml` | `methods.baseline` / `physics` / `ml` |
| Status enum | `pending` \| `candidate` \| `insufficient_evidence` \| `unavailable` | `ok` or `unavailable`; decision bool → “detected” / “insufficient evidence”. Extra `ok` / `detected` would display as Pending in Cursor cards. |
| ML | pending/unavailable, score null, “synthetic-model score” | `status=ok` + `predict_proba` or `unavailable` + `setup_instruction` (`python -m core.training train`). Score is a model score, not labeled in the dict except `score_label`. |
| Benchmark | `{status: pending, methods: [], metadata: {}}` | measured `status=ok` with recall/FAR numerators (200 test recordings) in `artifacts/benchmark.json` |
| Mode / banner | `mode=placeholder`, “Placeholder — backend pending” | no `mode`; orbit `kind` `real_public_orbital_elements` or `synthetic_orbit_fallback` |
| Provenance | `radio: simulated` string | `radio.kind: simulated_power_spectrogram`; orbit object with NORAD 27844 CUTE-1 |
| Recording upload | `analyze_recording(metadata)` defined, **not wired in UI** | no file loader; synthetic spectrogram only |
| Rankings | none | none (single detected track, not a ranked list) |
| Analyze/Reset | explicit Analyze; controls do not rerun until click | Codex `app.py` runs `analyze` on first load (`if run or result is None`) |
| JSON download | full analyze payload | Codex omits `observed_power` from download |
| Ground truth | overlay from `ground_truth.times_s` + `frequency_offsets_hz` | `tracks.ground_truth_hz` vs time; extra truth fields in `ground_truth` |

Cursor must **not** map missing Codex fields to fake candidate/success placeholders.

## Exact startup command (this branch, placeholder backend)

```bash
cd /path/to/Cal-Hacks-13.0
git checkout cursor/interface
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Combined app is **not** runnable until Codex core is published and the UI is adapted (or an adapter is added). Do not train on Streamlit reruns.

## Files/commits to combine later

1. This branch: `cursor/interface` @ `83ec659de130eeed282341a769e99012c36d997f` plus this status commit — `app.py`, `.streamlit/config.toml`.
2. Codex scientific core **once it is on GitHub**: `core/orbit.py`, `simulation.py`, `detection.py`, `training.py`, Codex `engine.py`, `data/`, `artifacts/lastping_model.joblib`, `artifacts/benchmark.json`, `MODEL_CARD.md`, `DATA_SOURCES.md`.
3. **Do not** take Codex `app.py` if Cursor remains UI owner.
4. Replace or wrap Cursor `core/engine.py` so it implements Codex science **and** the Cursor return schema, or change Cursor `app.py` to Codex’s schema (UI-owner change).

## Findings

### Implemented and verified

- Cursor Streamlit interface against placeholder `analyze`/`benchmark`
- Heatmap 96×192, Analyze/Reset, null scores → Pending, JSON download, pending benchmark
- `pytest tests/` on this branch: 11 passed
- `py_compile` of `app.py`, `core/engine.py`, `core/recordings.py`
- Push target repo exists and remote matches `BigAli07/Cal-Hacks-13.0`

### Implemented but unverified

- Compatibility of Cursor UI with live Codex `analyze` (cannot run; Codex not on remote)
- `analyze_recording` (unit tests on fixtures only; no UI; no field captures)
- Combined git history of Cursor UI + Codex core

### Missing or blocked

- `CODEX_STATUS.md` and a Codex backend branch on GitHub
- Recording upload controls
- Wiring to Codex orbit cache, detectors, trained model, measured benchmark table
- Adapter between Cursor schema and Codex schema
- Observer lat/lon actually driving Codex geometry
- Shared preset vocabulary
- End-to-end verification after Cursor+Codex merge
- Prompt did not include a real `<REPOSITORY_URL>` token; used `Cal-Hacks-13.0` by name

## Integration issues (concrete)

1. Dropping Cursor config into Codex `SimulationConfig(**config)` crashes on unknown keys (`observer_*`, `interference`).
2. Cursor presets are not Codex presets (`faint_intermittent` vs `intermittent_beacon`, etc.).
3. Cursor reads `spectrum.power_db`; Codex returns `observed_power` (linear). Heatmap would be empty or throw.
4. Cursor method cards read `results.threshold`; Codex uses `methods.baseline`. All three cards stay empty/pending.
5. Codex `status=ok` is not in Cursor’s allowed set → would display as Pending even after a real detection.
6. Codex first-load auto-analyze vs Cursor explicit Analyze.
7. Codex ML `unavailable` includes `setup_instruction`; Cursor looks for `results.ml`.
8. No GitHub Codex commit to merge.

## Stop line

No merge, deploy, redesign, or presentation/video work in this pass.
