# LastPing submission video script

About 90 seconds. Speak only what is on screen or in this script. Follow [DEMO.md](DEMO.md) so the recording is the bundled SatNOGS replay from commit `787332358c99af318137b44d563f8d0c9bc31a65`.

No video file was created in this session. `screencapture -V` exited immediately with status 1 and wrote no file, and `ffmpeg` is not installed. Manual capture steps are at the end.

## 0–15 seconds — the problem

Screen: LastPing is open. Sidebar shows **Real recording replay** and **Bundled validated SatNOGS observation**. Do not click yet. The title “Search for the signal that survived” is visible.

Narration: “A satellite-like trace is easy to confuse with noise, and more than one satellite can be a plausible match. LastPing takes one archived reception and asks which historical satellite tracks agree with the signal that was actually measured.”

## 15–30 seconds — the recording

Screen: At 15 seconds, click **Analyze recording** once. The observation id, time, and station are not on the empty screen; they appear on the source line when the result loads. Point to **Radio: archived real (not live)** and read that line. Do not change the source dropdown.

Narration: “This is archived replay, not a live receiver. The file is SatNOGS observation 6659851, acquired 26 October 2022 at 04:12:41 UTC by station PE0SAT-32. The scheduled signal is FUNCUBE-1 at 145.935 megahertz, BPSK.”

## 30–60 seconds — analysis

Screen: The result is on screen. Move in this order: **Candidate beacon** for FUNCUBE 1 / NORAD 39444, the identity caption, the waterfall and its legend, then the candidate table. Pause on the above-horizon column. Predicted tracks are dashed. The fitted template is the solid orange line. The independent ridge is the white markers.

Narration: “The waterfall is 706 by 1025 bins of that archived audio. The white ridge is energy measured from the spectrum before any template is applied. Dashed lines are historical Doppler tracks, and the orange line is the best fitted template. FUNCUBE-1 ranks first, with physics score 6.825, a −500 hertz offset, 0.993 above-horizon support, and a 283.8 hertz residual to the ridge. The other three candidates have zero above-horizon support. The label is Candidate beacon: a candidate match, not a confirmed identity.”

Read the processing time from the line that begins “Full processing” if it is already visible. Do not quote a time that is not on screen.

## 60–75 seconds — the model

Screen: Scroll to the caption under **Candidate evidence** and the ML card. The visible score is **1.000**. The card says **Experimental, uncalibrated on real RF**. The metric label is **synthetic-model score**.

Narration: “The classifier was trained on 500 synthetic examples. On this real recording the score is exploratory and uncalibrated. One point zero zero zero is not certainty, and it is not the probability that a satellite was recovered. Synthetic thresholds are not used to make this decision.”

## 75–90 seconds — what it establishes

Screen: Return to the candidate table so FUNCUBE-1’s 0.993 and the other candidates’ 0.000 above-horizon values are visible. Leave the synthetic mode, train button, and benchmark button untouched.

Narration: “This release validates one positive archived replay. The measured ridge agrees with FUNCUBE-1’s historical track, and the incorrect candidates are below the horizon. The useful next recording is another in-band pass where a competing satellite is actually above the horizon, so a real miss can be tested. It does not establish live reception or general identification accuracy.”

## Manual capture

No video was made.

1. Restart Streamlit using the commands in [DEMO.md](DEMO.md) and confirm commit `787332358c99af318137b44d563f8d0c9bc31a65`.
2. Open http://localhost:8503 in a normal browser, full width, with the sidebar visible. Close other windows.
3. Record with QuickTime Player → File → New Screen Recording, or, after macOS Screen Recording permission is granted:

```bash
screencapture -x -v -V 90 -k lastping-demo.mov
```

4. Speak this script while doing only the clicks above. Start on the empty bundled screen, click **Analyze recording** at 15 seconds, and stop at 90 seconds.
5. Play the file from start to end. Confirm the waterfall, FUNCUBE-1 row, and 1.000 caption are readable, and that the duration is about 90 seconds:

```bash
mdls -name kMDItemDurationSeconds lastping-demo.mov
```

6. If the on-screen score, time, or label differs from this script, keep the picture and change the narration. Do not edit the picture to invent a detection.
