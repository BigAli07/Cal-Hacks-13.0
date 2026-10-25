# LastPing judge demo

Release: `787332358c99af318137b44d563f8d0c9bc31a65`  
Branch: `cursor/lastping-integrated`  
Repository: https://github.com/BigAli07/Cal-Hacks-13.0.git

Supported claim, and the only claim to speak:

> We analyze a real archived satellite reception and compare its measured signal evidence with historical candidate satellite tracks.

Do not say live reception, recovered satellite, general identification accuracy, or calibrated real-data machine learning.

This walkthrough uses only the bundled SatNOGS observation. Do not upload a file, switch to **Synthetic experiment**, train a model, refresh the orbit cache, or run the synthetic benchmark during the judge demo.

## Startup

From a checkout of the release:

```bash
git fetch origin cursor/lastping-integrated
git checkout cursor/lastping-integrated
git merge --ff-only 787332358c99af318137b44d563f8d0c9bc31a65
git rev-parse HEAD
```

`git rev-parse HEAD` must print `787332358c99af318137b44d563f8d0c9bc31a65`.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-lastping.txt
.venv/bin/streamlit run app.py --server.headless true --server.port 8503
```

Open http://localhost:8503 in a normal browser window. The first screen is **Real recording replay** with source **Bundled validated SatNOGS observation**. The main panel says to select **Analyze recording** for the bundled SatNOGS observation and says that audio is an archived reception, not a live receiver.

The process restarted for this release printed that same commit before serving http://localhost:8503.

## Walkthrough

1. Leave **Input mode** on **Real recording replay**.
2. Leave **Recording source** on **Bundled validated SatNOGS observation**.
3. Read the empty-state sentence. Do not describe the bundled file as an upload.
4. Click **Analyze recording**. In the timed video this click is at 15 seconds, because the observation id, acquisition time, and station appear only after the result loads.
5. Wait for the spinner: “Validating recording, calculating spectrogram and ranking candidates…”. This takes a few seconds. Do not click again.
6. When the result appears, show these items in order:
   - Badges: **Radio: archived real (not live)**, **Orbit: historical TLE**, **ML: uncalibrated on real RF**.
   - The amber warning that this is an archived replay, not live reception, and that the audio is lossy target-Doppler-corrected mono rather than raw I/Q.
   - **Result: Candidate beacon · Best candidate: FUNCUBE 1 (NORAD 39444)**.
   - The caption: “A candidate match does not confirm satellite identity.”
   - Source line: SatNOGS observation **6659851**, acquired **2022-10-26T04:12:41Z**, station **PE0SAT-32**, **145.935000 MHz BPSK**, SHA-256 `c317e44ccddb890023a1b863c326fb856525902da3aeefa3355d566fe64aaf63`.
   - Waterfall. Horizontal axis: seconds after acquisition start. Vertical axis: Doppler-corrected audio frequency in kHz. The caption reports **706 time bins × 1025 frequency bins** and says the measured ridge is extracted independently of candidate templates.
   - Legend: dashed predicted tracks, the solid orange **best fitted template**, and the white **independent measured ridge** markers.
   - **Candidate evidence** table. Read the displayed values, which are:
     - FUNCUBE 1, NORAD 39444: physics **6.825**, frequency offset **−500 Hz**, above-horizon support **0.993**, ridge RMS residual **283.8 Hz**, synthetic-model score **1.000**.
     - AAUSAT CUBESAT 2 (32788), OSCAR 7 (7530), and OSCAR 11 (UoSAT 2) (14781): above-horizon support **0.000**.
   - The caption under the table: a displayed **1.000** is not certainty and is not a probability of satellite recovery.
   - The three method cards. The ML card is **Experimental, uncalibrated on real RF**, and the metric is **synthetic-model score 1.000**.
   - The processing line. Read the seconds printed after “Full processing”. Acquisition duration stays **352.796 s**. The release check measured **3.5565 s**; a later run can differ by a fraction of a second. Speak the number on screen.
   - The calibration notice: “Synthetic thresholds and probabilities are not transferred to real RF decisions.”

7. Stop. Do not open **Reveal simulation ground truth**; that control belongs to the synthetic experiment, not this recording.

## If the app needs a restart

Watchdog is not installed, so an already running Streamlit process will keep the code it loaded at startup.

```bash
kill $(lsof -ti tcp:8503)
git rev-parse HEAD
.venv/bin/streamlit run app.py --server.headless true --server.port 8503
```

Confirm the printed revision is `787332358c99af318137b44d563f8d0c9bc31a65`, then reload http://localhost:8503. Click **Reset** if a previous result is still on screen, then **Analyze recording** once.

If the page says “Select both a supported OGG/WAV recording and its metadata JSON,” the source was switched to upload. Set **Recording source** back to **Bundled validated SatNOGS observation** and analyze again. Do not substitute another file.

If analysis shows `Recording validation failed` or `Analysis error`, restart from the verified commit. Do not retrain and do not refresh the public orbit cache to repair the bundled demo.
