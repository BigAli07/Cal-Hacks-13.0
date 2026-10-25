# Verification record

Verified on 2026-10-25 with Python 3.12.14 on CPU.

## Commands

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m core.real_data
.venv/bin/python -m core.training benchmark
.venv/bin/streamlit run app.py --server.headless=true
```

The complete suite passed, including real recording SHA/metadata validation,
native PSD dimensions, malformed-input rejection, historical timestamps and
TLEs, incorrect candidate comparisons, independent ridge/template separation,
synthetic-only ML labeling, Doppler sign/units, simulation reproducibility,
truth isolation, disjoint seeds, all four synthetic presets, missing-model
behavior, Analyze gating and Reset.

## Real-data gate

The bundled SatNOGS OGG and untouched API JSON pass SHA-256 and metadata
cross-checks. The importer decoded 16,934,208 mono samples at 48 kHz and
computed a native 706×1025 Hann-window PSD (2048-point FFT, 50% overlap within
0.5-second aggregation bins, 23.4375 Hz frequency resolution). No conversion to
the synthetic 128×192 shape occurs.

At the actual 2022-10-26 timestamps and PE0SAT-32 coordinates, FUNCUBE-1 is
above the horizon for 99.3% of decoded bins. It ranks first with score 6.825,
−500 Hz fitted offset, and 283.8 Hz ridge RMS residual. SatNOGS independently
publishes 53 decoded frames. OSCAR 11, AAUSAT CUBESAT 2 and OSCAR 7 are included
as incorrect candidates and are below the receiver horizon. The latest
end-to-end compute was 3.859 s for a 352.796 s acquisition; 0.359 s PSD,
0.008 s orbit prediction, 3.472 s candidate scoring, and 0.004 s model-only
scoring.

The real pass is a supported positive, but there is no reliable real negative
corpus. Real recall and false-alarm rate are therefore **not measured**.
Malformed/hash-mismatched inputs are rejected, and the three incorrect tracks
exercise unsupported-candidate handling. The classifier is genuinely trained
on 500 synthetic recordings but has no real training examples; real ML output
is explicitly experimental and uncalibrated.

The Streamlit startup health endpoint returned `ok`. Browser inspection covered
real/synthetic mode selection, bundled Analyze, Reset, upload controls,
provenance, actual waterfall, separate measured/predicted/fitted evidence,
candidate table, method cards, JSON export and historical benchmark labeling.

## Synthetic measured evaluation

Thresholds were fixed on validation seeds 20000–20159 at a target 5% FAR.
The final test used seeds 30000–30199: 100 signals and 100 negatives, including
32 negatives with stationary interference.

| Method | Detected signals | Recall | False alarms | FAR | Total CPU inference |
|---|---:|---:|---:|---:|---:|
| Signal strength | 9/100 | 0.09 | 7/100 | 0.07 | 0.0769 s |
| Physics search | 60/100 | 0.60 | 11/100 | 0.11 | 0.3075 s |
| Logistic regression | 60/100 | 0.60 | 8/100 | 0.08 | 0.3788 s |

ML time includes feature extraction; its model-only total was 0.0024 s. These
are historical machine-specific measurements, not live observation time.

## Remaining limits

The real example is one lossy, target-Doppler-corrected audio pass, not raw RF
I/Q or calibrated power. No real negative corpus, cross-pass training set,
general real recall/FAR, live SDR adapter, or STRF ingestion is present. The
synthetic 437 MHz carrier remains assumed. No real-world sensitivity, orbit
recovery, confirmed identity, or live detection claim is made.
