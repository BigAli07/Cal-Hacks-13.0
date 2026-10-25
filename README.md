# Cal-Hacks-13.0

## LastPing

LastPing replays a validated archived satellite reception through three
CPU-only evidence methods: a signal-strength baseline, a bounded
physics-guided Doppler-template search, and a trained logistic-regression
classifier. The same interface retains the original synthetic experiment as a
separately labelled mode.

The bundled real example is SatNOGS observation 6659851: a 352.796-second
mono 48 kHz OGG reception of FUNCUBE-1 from station PE0SAT-32 at 145.935 MHz.
The file, original API response, SHA-256 hashes, receiver details, historical
TLEs, and CC BY-SA attribution are cached under `data/real/` for offline replay.

The real OGG is target-Doppler-corrected SatNOGS BPSK audio, not raw RF I/Q.
Its amplitude is relative and uncalibrated. The synthetic mode uses public
CelesTrak orbital elements with an explicitly assumed 437 MHz carrier.

## Setup and commands

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-lastping.txt
.venv/bin/python -m core.real_data
.venv/bin/python -c 'from core.orbit import fetch_celestrak_cache; print(fetch_celestrak_cache())'
.venv/bin/python -m core.training train
.venv/bin/python -m core.training benchmark
.venv/bin/python -m pytest -q tests/test_lastping.py
.venv/bin/streamlit run app.py
```

The default real replay is bundled and works offline; the network is needed
only for an explicit synthetic-orbit cache refresh.
If no verified cache is present, the app uses and labels a synthetic-orbit
fallback. Training and benchmarking are explicit commands/sidebar actions;
neither runs during ordinary Streamlit reruns.

`core.engine.replay_real(recording, manifest) -> dict`,
`core.engine.analyze(config) -> dict`, `core.engine.benchmark() -> dict`, and
`core.engine.saved_benchmark() -> dict` are the stable programmatic interfaces.
The saved result is explicitly marked as a historical artifact and never
reruns evaluation. Valid presets are `strong_beacon`, `faint_intermittent`,
`interference_only`, and `noise_only`.

The sidebar exposes seed, injected strength, stationary interference, and
observer latitude/longitude/elevation. Control changes do not recompute until
**Run analysis** is selected; a warning identifies stale displayed results.

## Interpretation

The real replay produces a 706×1025 PSD without resizing to the synthetic
shape. SatNOGS' target-specific Doppler correction is modeled explicitly:
candidate audio frequency is 12 kHz plus candidate RF Doppler minus the
scheduled target correction. Predicted tracks, the searched best-fit template,
and an independently measured energy ridge remain distinct.

The saved classifier was trained on synthetic recordings only. Its real-data
output is an experimental, uncalibrated synthetic-model score and never uses a
synthetic threshold to make a real RF decision. Reliable real false-alarm rate
is not measured because only one independently supported real positive pass is
bundled.

`signal_excess_db` means `10 log10(injected peak excess power / mean
background power)`. It is not measured RF SNR or receiver sensitivity. ML
output is a synthetic-model score, not a probability of satellite recovery.
False alarms are possible and are reported rather than suppressed using hidden
simulation truth.

See [DATA_SOURCES.md](DATA_SOURCES.md), [MODEL_CARD.md](MODEL_CARD.md),
[HANDOFF.md](HANDOFF.md), and [VERIFICATION.md](VERIFICATION.md) for provenance,
measured results, contracts, and verification.

