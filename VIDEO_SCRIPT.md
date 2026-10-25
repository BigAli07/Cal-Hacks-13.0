# LastPing verified video script (90 seconds)

## Script and screen direction

**0–10 seconds — Problem**

Show the title and archived replay controls.

“Weak intermittent satellite signals can disappear into noise and
interference. LastPing tests whether known orbital motion adds useful evidence,
without treating a Doppler match as proof of identity.”

**10–23 seconds — Real archived source**

Click **Analyze recording**, then point to provenance.

“This is hash-verified SatNOGS observation 6659851 from 2022—not a simulation
and not live. It is a 352.796-second BPSK recording from receiver PE0SAT-32 at
145.935 megahertz.”

**23–43 seconds — Measured evidence versus predictions**

Pan across the waterfall and legend.

“The waterfall is calculated from the recording. Dashed lines are historical
orbital predictions, red is the searched best-fit template, and cyan is an
independently extracted measured energy ridge. Candidate templates do not
create that ridge.”

**43–59 seconds — Receiver correction and ranking**

Show the candidate table.

“Because SatNOGS corrected this audio for its scheduled target, LastPing
subtracts that target's predicted Doppler when reconstructing every comparison.
The scheduled identity is not a ranking feature. FUNCUBE-1 ranks first at
6.825, with a 4.177 margin and 99.3 percent visibility support.”

**59–72 seconds — Incorrect candidates**

Move down the remaining table rows.

“The three alternatives are genuine satellites with historical TLEs, not
fabricated negatives. All are below this receiver's horizon for the pass.
SatNOGS independently published 53 decoded frames for the scheduled target.”

**72–82 seconds — ML contribution**

Show the method cards and warning text.

“The ML model was trained on 500 synthetic recordings. Its real score is
explicitly experimental and uncalibrated, and it does not decide this archived
result.”

**82–90 seconds — Measured performance and next work**

Show processing time, then the closing limitation.

“Analysis took about four seconds. Synthetic tests measure 60 percent recall
and 8 percent false alarms for ML, but one real positive cannot measure either
on real RF. Next we need verified real negatives and diverse receivers.”

## Exact capture instructions

1. Start the verified app with `.venv/bin/streamlit run app.py`.
2. Set the browser viewport to at least 1280×720 and keep the sidebar open.
3. Begin before analysis with the bundled archived source selected.
4. Record the Analyze click, archived-real banner, provenance, waterfall legend,
   candidate table, method cards, processing time, JSON download, and Reset.
5. Capture system audio only if desired; record narration on a quiet microphone.
6. Export 1920×1080 H.264 with AAC audio, then play the entire exported file and
   verify readable labels, synchronized audio, and no spinner in the final shot.

No draft video was recorded during verification. The environment exposed only
the static `screencapture` utility; neither FFmpeg nor OBS (nor another verified
screen-recording workflow) was available. The live app was visually inspected
in both the in-app browser and Chrome.
