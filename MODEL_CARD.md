# LastPing model card

## Model and intended use

The supervised method is a scikit-learn `StandardScaler` plus
`LogisticRegression` classifier for comparing methods on LastPing's synthetic
CubeSat-like beacon experiment. It is not a production RF classifier and its
score is not a calibrated probability of finding or recovering a satellite.

The saved model is synthetic-only. On real recordings, LastPing reuses its
observation-derived feature path for exploratory scoring but returns
`experimental_uncalibrated`, no ML decision, and no transferred threshold.

Inputs are six observation-derived features: normalized peak strength,
searched-track accumulation, track/background contrast, supported-bin
fraction, persistence, and contrast against stationary interference. No
preset, seed, injected strength/offset, presence flag, dropout mask, or ground
truth enters the detector.

## Training and thresholds

The saved model used 500 training examples (seeds 10000–10499). Thresholds for
all three methods were fixed on 160 validation examples (20000–20159) at a 5%
target empirical false-alarm rate. The physics threshold calibrates the maximum
over its complete 65-template search. The 200-example test split
(30000–30199) was untouched during threshold selection.

## Measured performance

### Real replay

One independently supported real positive pass is bundled. FUNCUBE-1 ranked
first with physics score 6.825, a fitted −500 Hz audio offset, 99.3% above-
horizon support, and 283.8 Hz RMS residual to the independently extracted
energy ridge. SatNOGS lists 53 decoded frames for the observation. Three
incorrect historical candidate satellites were compared; all were below the
receiver horizon. No verified real negative set is included, so real recall
and false-alarm rate are **not measured**. The synthetic-model score must not be
interpreted as real calibration or identification probability.

### Synthetic benchmark

On 100 signal and 100 negative test recordings, injected positive strength was
uniform from -6 to +5 dB. Baseline recall/FAR was 9/100 and 7/100; physics was
60/100 and 11/100; ML was 60/100 and 8/100. Exact measured CPU runtimes are in
`artifacts/benchmark.json` and exclude simulated recording duration. Thirty-two
of the 100 test negatives contained stationary interference. The latest totals
were 0.0769 s baseline, 0.3075 s physics, and 0.3788 s ML including features.

## Limitations

Performance measures one generator and one observer/pass geometry. Synthetic
noise and interference do not capture receiver hardware, propagation,
frequency calibration, modulation, or real operational distributions. Test FAR
can differ from the 5% validation target. Retrain and create a fresh holdout
after changing generator, features, template search, or detector semantics.
The real example is one lossy, target-Doppler-corrected BPSK audio pass; it does
not establish general real-world sensitivity or performance across receivers,
satellites, modes, or interference.

