# LastPing 90-second demo

## Supported claim

LastPing can validate and replay one documented SatNOGS BPSK observation,
calculate a numerical spectrogram, model the receiver's target-specific Doppler
correction with historical TLEs, and compare measured support for four satellite
candidates. It does not identify arbitrary satellites or establish real-world
sensitivity from one pass.

## Live demo sequence

1. Start with `.venv/bin/streamlit run app.py` and leave **Real recording
   replay** selected.
2. Show the bundled source and select **Analyze recording**.
3. Point out the archived-real banner, observation 6659851, acquisition UTC,
   PE0SAT-32 receiver, 145.935 MHz BPSK metadata, and file hash.
4. On the real waterfall, distinguish:
   - dashed historical predictions;
   - red best-fitting searched template;
   - cyan independently measured energy ridge.
5. Show the candidate table. FUNCUBE-1 ranks first at 6.825 with −500 Hz
   offset, 99.3% above-horizon support and 283.8 Hz ridge RMS residual. The
   three incorrect candidates are below the horizon.
6. Show the three method cards. The ML output is explicitly a
   **synthetic-model score** and **experimental, uncalibrated on real RF**.
7. Expand provenance: SatNOGS independently published 53 decoded frames. Full
   processing is about four seconds versus 352.796 seconds of archived audio.
8. Download the JSON, then select **Reset**. Briefly show the separately
   labelled synthetic mode if time remains.

## Required closing limitation

This is one lossy, target-Doppler-corrected positive audio pass—not raw I/Q or
calibrated power. A real negative corpus is unavailable, so real recall and
false-alarm rate are not measured. The result is a candidate match, not
confirmed identity or orbit recovery.

