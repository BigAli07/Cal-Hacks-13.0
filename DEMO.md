# LastPing verified 90-second demo

## What the verified application supports

LastPing replays one documented, hash-verified SatNOGS BPSK observation and
compares its measured audio ridge with historical Doppler tracks for four real
satellite candidates. This is an **archived replay**, not live reception. The
result supports a narrow candidate-match claim; it does not prove identity,
recover an orbit, or establish real-world detector performance.

## Start the verified build

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lastping.txt
.venv/bin/streamlit run app.py
```

Leave **Real recording replay** and **Bundled validated SatNOGS observation**
selected.

## Demo sequence

1. **Frame the problem (0–10 s).** A weak, intermittent satellite signal can
   be difficult to distinguish from interference. LastPing asks whether known
   orbital motion provides additional evidence.
2. **Show provenance (10–23 s).** Click **Analyze recording**. Point out
   SatNOGS observation 6659851, receiver PE0SAT-32, acquisition start
   `2022-10-26T04:12:41Z`, 145.935 MHz BPSK, 352.796 seconds at 48 kHz, and the
   validated source hashes. The analyzed waterfall has 706 time bins by 1,025
   frequency bins.
3. **Explain the evidence (23–43 s).** Dashed lines are predictions from
   historical TLEs. Red is the best searched candidate template. Cyan is the
   measured ridge extracted independently from signal energy in a fixed audio
   band—it is not copied from any candidate track.
4. **Explain receiver correction (43–55 s).** SatNOGS produced target-Doppler-
   corrected audio. LastPing therefore models audio IF plus each candidate's
   Doppler minus the scheduled target's Doppler. The scheduled target TLE is
   used for this receiver correction, not as a ranking feature.
5. **Show the ranking (55–69 s).** FUNCUBE-1 / catalog 39444 ranks first with a
   physics score of 6.825, margin 4.177, fitted offset −500 Hz, 99.3% visibility
   support, and 283.8 Hz ridge RMS residual. The other three rows are genuine
   historical-TLE comparisons and are below the receiver horizon.
6. **Describe ML honestly (69–79 s).** The logistic model was trained on 500
   synthetic recordings. Its score is labelled experimental and uncalibrated
   on real RF, and it does not determine the archived replay decision.
7. **Close with performance and limits (79–90 s).** Processing took about four
   seconds, separate from the 352.796-second acquisition. The synthetic-only
   benchmark reports baseline 9% recall / 7% false-alarm rate, physics 60% /
   11%, and ML 60% / 8%. One real positive replay and 53 independently
   published SatNOGS frames do not measure real recall or false-alarm rate.

## Optional verification beats

- Upload the bundled `.ogg` and its manifest together; the same result appears.
- Download and open the JSON export.
- Switch to upload mode or submit a missing/invalid pair; the app clears the old
  result and shows a validation error.
- Show synthetic mode only as a separately labelled simulation.

