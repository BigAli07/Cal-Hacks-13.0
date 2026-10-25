"""Single Streamlit interface for real replay and the synthetic LastPing experiment."""
from __future__ import annotations

import json

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from core.engine import analyze, benchmark, replay_real, saved_benchmark
from core.orbit import DEFAULT_OBSERVER, fetch_celestrak_cache
from core.real_data import RecordingValidationError
from core.simulation import PRESETS, PRESET_DEFAULT_STRENGTH_DB
from core.training import train

st.set_page_config(page_title="LastPing", layout="wide")
st.title("LastPing: satellite radio evidence")
st.caption("Archived real recording replay and a separately labelled synthetic beacon experiment.")

defaults = {
    "input_mode": "Real recording replay",
    "real_source": "Bundled validated SatNOGS observation",
    "real_result": None,
    "preset": "faint_intermittent", "seed": 7, "strength": -4.0,
    "interference": False,
    "observer_latitude": DEFAULT_OBSERVER["latitude_deg"],
    "observer_longitude": DEFAULT_OBSERVER["longitude_deg"],
    "observer_elevation": DEFAULT_OBSERVER["elevation_m"],
    "reveal_truth": False, "result": None,
}
for key, value in defaults.items():
    st.session_state.setdefault(key, value)


def reset_synthetic():
    for key in ("preset", "seed", "strength", "interference", "observer_latitude",
                "observer_longitude", "observer_elevation", "reveal_truth", "result"):
        st.session_state[key] = defaults[key]


def reset_real():
    st.session_state.real_source = defaults["real_source"]
    st.session_state.real_result = None


def apply_preset_defaults():
    preset = st.session_state.preset
    st.session_state.strength = PRESET_DEFAULT_STRENGTH_DB[preset]
    st.session_state.interference = preset == "interference_only"


def current_synthetic_config():
    return {
        "preset": st.session_state.preset,
        "seed": int(st.session_state.seed),
        "signal_excess_db": float(st.session_state.strength),
        "interference": bool(st.session_state.interference),
        "observer": {
            "latitude_deg": float(st.session_state.observer_latitude),
            "longitude_deg": float(st.session_state.observer_longitude),
            "elevation_m": float(st.session_state.observer_elevation),
        },
    }


PRESET_LABELS = {
    "strong_beacon": "Strong beacon", "faint_intermittent": "Faint intermittent beacon",
    "interference_only": "Interference only", "noise_only": "Noise only",
}

with st.sidebar:
    st.radio("Input mode", ["Real recording replay", "Synthetic experiment"], key="input_mode")
    st.divider()
    if st.session_state.input_mode == "Real recording replay":
        st.selectbox("Recording source", ["Bundled validated SatNOGS observation",
                                          "Upload recording and metadata"], key="real_source")
        uploaded_recording = uploaded_metadata = None
        if st.session_state.real_source == "Upload recording and metadata":
            uploaded_recording = st.file_uploader("OGG or WAV recording", type=["ogg", "wav"])
            uploaded_metadata = st.file_uploader("LastPing metadata manifest (JSON)", type=["json"])
        run_real = st.button("Analyze recording", type="primary", width="stretch")
        st.button("Reset", on_click=reset_real, width="stretch")
        if run_real:
            try:
                with st.spinner("Validating recording, calculating spectrogram and ranking candidates…"):
                    if st.session_state.real_source == "Bundled validated SatNOGS observation":
                        st.session_state.real_result = replay_real()
                    elif uploaded_recording is None or uploaded_metadata is None:
                        st.error("Select both a supported OGG/WAV recording and its metadata JSON.")
                    else:
                        st.session_state.real_result = replay_real(uploaded_recording.getvalue(),
                                                                    uploaded_metadata.getvalue())
            except RecordingValidationError as exc:
                st.error(f"Recording validation failed: {exc}")
    else:
        st.selectbox("Experiment preset", list(PRESETS), key="preset",
                     format_func=PRESET_LABELS.get, on_change=apply_preset_defaults)
        st.number_input("Simulation seed", min_value=0, max_value=1_000_000, step=1, key="seed")
        st.slider("Injected peak signal excess (dB)", -10.0, 10.0, step=0.5, key="strength",
                  help="Injected peak excess power relative to mean background; not measured RF SNR.")
        st.checkbox("Add stationary interference", key="interference")
        st.number_input("Observer latitude (deg)", min_value=-90.0, max_value=90.0,
                        step=0.1, format="%.4f", key="observer_latitude")
        st.number_input("Observer longitude (deg)", min_value=-180.0, max_value=180.0,
                        step=0.1, format="%.4f", key="observer_longitude")
        st.number_input("Observer elevation (m)", min_value=-500.0, max_value=9000.0,
                        step=10.0, key="observer_elevation")
        run_synthetic = st.button("Run analysis", type="primary", width="stretch")
        st.button("Reset controls", on_click=reset_synthetic, width="stretch")
        if run_synthetic or st.session_state.result is None:
            st.session_state.result = analyze(current_synthetic_config())
    st.divider()
    if st.button("Fetch/refresh public orbit cache", width="stretch"):
        try:
            with st.spinner("Fetching CelesTrak…"):
                st.success(f"Cached at {fetch_celestrak_cache()['retrieved_utc']}")
        except Exception as exc:
            st.error(str(exc))
    if st.button("Train synthetic classifier", width="stretch"):
        with st.spinner("Generating train/validation sets and fitting…"):
            st.success(f"Trained on {train()['counts']['training']} synthetic recordings.")
    if st.button("Run synthetic benchmark", width="stretch"):
        with st.spinner("Evaluating fixed synthetic thresholds…"):
            report = benchmark()
            st.session_state["benchmark"] = report
            st.success("Benchmark complete." if report["status"] == "ok" else report["setup_instruction"])


def track_array(values):
    return np.asarray([np.nan if value is None else value for value in values], dtype=float)


def render_real(result):
    recording = result["recording"]
    st.success(f"Archived real recording · SatNOGS observation {recording['observation_id']}")
    st.warning("Replay—not live reception. Audio amplitudes are relative and uncalibrated; this is not raw RF I/Q.")
    st.write(f"**Result:** {result['conclusion_label']} · **Best candidate:** {result['best_candidate']['name']} "
             f"(NORAD {result['best_candidate']['catalog_id']})")
    st.caption(f"Acquired {recording['acquisition_start_utc']} · {recording['receiver']['station_name']} · "
               f"{recording['transmitter']['frequency_hz']/1e6:.6f} MHz {recording['transmitter']['mode']} · "
               f"SHA-256 {recording['sha256']}")

    power = np.asarray(result["observed_power"])
    time_s = np.asarray(result["axes"]["time_s"])
    frequency_hz = np.asarray(result["axes"]["audio_frequency_hz"])
    fig = go.Figure(go.Heatmap(x=time_s, y=frequency_hz / 1000.0,
                               z=10 * np.log10(power.T + 1e-30), colorscale="Viridis",
                               colorbar_title="Relative PSD dB/Hz"))
    colors = ["white", "orange", "magenta", "lime"]
    for color, candidate in zip(colors, result["candidates"]):
        fig.add_trace(go.Scatter(x=time_s, y=track_array(candidate["predicted_track_hz"]) / 1000.0,
                                 name=f"predicted: {candidate['name']}",
                                 line={"color": color, "dash": "dash", "width": 1}))
    best = result["candidates"][0]
    fig.add_trace(go.Scatter(x=time_s, y=track_array(best["fitted_template_hz"]) / 1000.0,
                             name="best fitted template", line={"color": "red", "width": 2}))
    fig.add_trace(go.Scatter(x=time_s, y=track_array(result["observed_ridge_hz"]) / 1000.0,
                             name="independent measured ridge", mode="markers",
                             marker={"color": "cyan", "size": 3}))
    fig.update_layout(height=620, xaxis_title="Seconds after acquisition start",
                      yaxis_title="Doppler-corrected audio frequency (kHz)",
                      legend={"orientation": "h", "yanchor": "bottom", "y": 1.02,
                              "xanchor": "left", "x": 0, "font": {"size": 10}},
                      margin={"t": 105})
    st.plotly_chart(fig, width="stretch")

    st.subheader("Candidate evidence")
    rows = []
    for candidate in result["candidates"]:
        rows.append({"Candidate": candidate["name"], "NORAD": candidate["catalog_id"],
                     "Physics score": round(candidate["score"], 3),
                     "Frequency offset (Hz)": candidate["best_frequency_offset_hz"],
                     "Above-horizon support": round(candidate["above_horizon_support"], 3),
                     "Ridge RMS residual (Hz)": candidate["ridge_residual_rms_hz"],
                     "Synthetic-model score": candidate["ml"]["score"]})
    st.dataframe(rows, width="stretch", hide_index=True)

    cols = st.columns(3)
    cards = [
        ("Signal strength", result["methods"]["baseline"], "Measured; no real threshold"),
        ("Physics candidate ranking", result["methods"]["physics"], result["conclusion_label"]),
        ("Supervised ML", result["methods"]["ml"], "Experimental, uncalibrated on real RF"),
    ]
    for col, (title, method, decision) in zip(cols, cards):
        with col:
            st.subheader(title)
            score = method.get("score")
            st.metric(method.get("score_label", "measured score"), "Unavailable" if score is None else f"{score:.3f}")
            st.write(decision)
    st.caption(f"Full processing: {result['timings']['total_processing_s']:.3f} s; acquisition duration: "
               f"{result['signal_processing']['decoded_duration_s']:.3f} s. These are separate quantities.")

    with st.expander("Recording provenance, calibration and evaluation evidence"):
        st.json({"recording": recording, "signal_processing": result["signal_processing"],
                 "calibration": result["calibration"], "evaluation": result["evaluation"],
                 "timings": result["timings"]})
    export = {key: value for key, value in result.items() if key != "observed_power"}
    st.download_button("Download real-analysis JSON", json.dumps(export, indent=2, allow_nan=False),
                       "lastping_real_analysis.json", "application/json")


def render_synthetic(result):
    analyzed = result["configuration"]
    controls_changed = any([
        analyzed["preset"] != st.session_state.preset,
        analyzed["seed"] != int(st.session_state.seed),
        analyzed["signal_excess_db"] != float(st.session_state.strength),
        analyzed.get("interference") != bool(st.session_state.interference),
        analyzed["observer"] != current_synthetic_config()["observer"],
    ])
    if controls_changed:
        st.warning("Controls have changed since this result was computed. Select **Run analysis** to update it.")
    provenance = result["provenance"]
    orbit = provenance["orbit"]
    if orbit["kind"] == "synthetic_orbit_fallback":
        st.warning("No verified orbit cache is available. Geometry is an explicitly synthetic LEO fallback.")
    else:
        st.success(f"Synthetic experiment · orbit: {orbit['satellite_name']} (NORAD {orbit['catalog_id']}) via CelesTrak")
        if orbit["stale_warning"]:
            st.warning(f"Orbital elements are stale for this recording ({orbit['tle_age_at_recording_days']:.1f} days).")
        st.caption(f"Orbital epoch: {orbit['orbital_epoch_utc']} · Replay start: {orbit['recording_start_utc']} · Source: {orbit['source_url']}")
    st.info("Radio provenance: simulated power spectrogram—not recorded raw I/Q. Carrier is an assumed 437 MHz.")

    power = np.asarray(result["observed_power"])
    times = np.asarray(result["axes"]["time_s"])
    freq = np.asarray(result["axes"]["frequency_hz"])
    fig = go.Figure(go.Heatmap(x=times, y=freq / 1000.0, z=10 * np.log10(power.T + 1e-9),
                               colorscale="Viridis", colorbar_title="Power dB"))
    for name, color, dash in [("predicted_hz", "white", "dash"), ("detected_hz", "red", "solid")]:
        fig.add_trace(go.Scatter(x=times, y=track_array(result["tracks"][name]) / 1000.0,
                                 name=name.replace("_hz", "").replace("_", " "),
                                 line={"color": color, "dash": dash}))
    truth = result["tracks"]["ground_truth_hz"]
    if st.toggle("Reveal simulation ground truth", key="reveal_truth") and truth is not None:
        fig.add_trace(go.Scatter(x=times, y=track_array(truth) / 1000.0, name="ground truth",
                                 line={"color": "cyan", "dash": "dot"}))
    fig.update_layout(xaxis_title="Time (s)", yaxis_title="Offset from assumed 437 MHz (kHz)", height=520)
    st.plotly_chart(fig, width="stretch")

    cols = st.columns(3)
    for col, key, title in zip(cols, ["baseline", "physics", "ml"],
                               ["Signal strength", "Physics accumulation", "Supervised ML"]):
        method = result["methods"][key]
        with col:
            st.subheader(title)
            if method["status"] != "ok":
                st.metric("Status", "Unavailable")
                st.caption(method["setup_instruction"])
            else:
                st.metric(method.get("score_label", "measured score"), f"{method['score']:.3f}")
                decision = method["decision"]
                st.write("Decision: **not calibrated**" if decision is None else
                         f"Decision: **{'detected' if decision else 'insufficient evidence'}**")
                st.caption(f"Inference runtime: {method['runtime_s'] * 1000:.2f} ms")
    with st.expander("Provenance and measured details"):
        st.json({"orbit": orbit, "radio": provenance["radio"], "ground_truth": result["ground_truth"]})
    export = {key: value for key, value in result.items() if key != "observed_power"}
    st.download_button("Download synthetic-analysis JSON", json.dumps(export, indent=2, allow_nan=False),
                       "lastping_synthetic_analysis.json", "application/json")


if st.session_state.input_mode == "Real recording replay":
    if st.session_state.real_result is None:
        st.info("Select **Analyze recording** to run the bundled, validated SatNOGS observation entirely offline. "
                "The included audio is an archived real reception, not a live receiver or synthetic substitute.")
    else:
        render_real(st.session_state.real_result)
else:
    render_synthetic(st.session_state.result)

if "benchmark" in st.session_state:
    st.subheader("Fresh synthetic benchmark")
    st.json(st.session_state.benchmark)
with st.expander("Saved synthetic benchmark (historical measurements)"):
    st.caption("These timings were measured when the saved artifact was created; opening this section does not rerun evaluation.")
    st.json(saved_benchmark())
