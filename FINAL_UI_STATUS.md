# Final UI status — LastPing

Update: 2026-10-25, after the interface fixes.  
Repository: https://github.com/BigAli07/Cal-Hacks-13.0  
Branch: `cursor/lastping-integrated`  
Owned files: `app.py`, `.streamlit/config.toml` (unchanged), this file. `core/`, models, artifacts, and backend reports were not edited.

## Server actually verified

The earlier browser session was still serving `fd52f2d` because Watchdog is not installed. That process on port 8502 was stopped.

Streamlit was started again after these edits:

- Command: `.venv/bin/streamlit run app.py --server.headless true --server.port 8503`
- Working directory: `/Users/big_ali07/Cal-Hacks-13.0-cursor`
- Started: 2026-10-25 06:52 local
- `git rev-parse --short HEAD` at process start: `432f030` (Codex backend audit only), plus the uncommitted `app.py` loaded by that process
- Browser: fresh load of `http://localhost:8503/?v=ui2` and `?v=ui3`

The commit that records this file is the UI fix commit on `cursor/lastping-integrated`. The running process was already executing that `app.py`.

## Fixes

1. **390px sidebar.** `initial_sidebar_state="auto"`. Under 480px, an open sidebar (`data-collapsed="false"`) stacks above the main column at full width instead of covering it. Collapsed, the sidebar stays off-canvas and the main column is the full 390px. At 1280px the sidebar stays on the left (300px) and the main column starts beside it.
2. **Waterfall.** The chart is responsive and stretches to the column. The legend sits above the axes. The colorbar sits to the right of the heatmap. Time and frequency axes, units, predicted tracks, fitted template, and the independent ridge are unchanged.
3. **Empty states.** Bundled mode says to analyze the bundled SatNOGS observation. Upload mode asks for both an OGG/WAV and the JSON manifest and says that mode does not use the bundled observation.
4. **Candidate table.** Physics score, above-horizon support, and the synthetic-model score display to three decimals. Ridge RMS displays to one decimal (283.8 Hz). Values stay numeric, so column sorting is numeric. The column is labeled uncalibrated, and the caption states that 1.000 is not certainty and is not a recovery probability.
5. **Orbit badges.** `real_public_orbital_elements` displays as “Cached public orbital elements.” `synthetic_orbit_fallback` displays as “Synthetic orbit.” Archived replay stays “Orbit: historical TLE” and “Radio: archived real (not live).”
6. **Ambiguity.** `ambiguous` displays as “Ambiguous,” with a caption that the rankings are too close to prefer one candidate. A `candidate_match` result includes “A candidate match does not confirm satellite identity.”

## What this browser session showed

Restarted server, desktop 1280×900 and phone 390×844.

- Bundled replay: badges “Radio: archived real (not live)”, “Orbit: historical TLE”, “ML: uncalibrated on real RF”. Result “Candidate beacon” for FUNCUBE 1 / NORAD 39444, plus the identity disclaimer. Waterfall 706 × 1025. Axes: seconds after acquisition start, Doppler-corrected audio frequency (kHz). Legend contains predicted tracks, best fitted template, and the independent measured ridge, and does not cover the heatmap. Colorbar “Relative PSD dB/Hz” sits to the right of the heat (desktop gap about 48px; at 390px the colorbar starts just after the heat).
- Candidate grid display values: physics 6.825, above-horizon 0.993, ridge RMS 283.8, synthetic-model score 1.000. The column header is “Synthetic-model score (uncalibrated)”. Underlying cell values stay floats.
- Upload empty state, after selecting “Upload recording and metadata”: “Upload both an OGG or WAV recording and its LastPing metadata manifest (JSON)… This mode does not use the bundled observation.” Both file controls are present.
- Bundled empty state, after switching back: the bundled-analysis sentence, not the upload sentence.
- 390×844, sidebar open: sidebar width 390 at the top, main width 390 below it. Collapsed: sidebar off-canvas, main 390×844, heading visible, expand control present.
- 1280×900: sidebar 300px on the left, main 980px beside it. Real heatmap about 565px wide inside an 820px chart.
- Synthetic mode: “Radio: simulated”, “Orbit: Cached public orbital elements”, “Experiment: synthetic (not a recording)”, CUTE-1 (CO-55) NORAD 27844. The raw token `real_public_orbital_elements` is not on the page. Axes: elapsed seconds, offset from assumed 437 MHz (kHz). Heatmap fills the plot box (635px) and neither the legend nor the colorbar overlaps it.

`pytest tests/test_lastping_app.py`: 5 passed.

## Not shown in this browser session

- A result whose conclusion is `ambiguous`. The label and caption are in `app.py`. This bundled replay is `candidate_match`.
- Attaching a real OGG and manifest in the browser (`DOM.setFileInputFiles` is denied). The upload AppTest still passes.
- Fetch cache, train, and a fresh benchmark click. Those controls were not part of these fixes.
