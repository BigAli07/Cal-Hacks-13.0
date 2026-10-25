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

CONCLUSION_LABELS = {
    "candidate_match": "Candidate beacon",
    "insufficient_evidence": "Insufficient evidence",
    "ambiguous": "Insufficient evidence",
}

PRESET_LABELS = {
    "strong_beacon": "Strong beacon",
    "faint_intermittent": "Faint intermittent beacon",
    "interference_only": "Interference only",
    "noise_only": "Noise only",
}

defaults = {
    "input_mode": "Real recording replay",
    "real_source": "Bundled validated SatNOGS observation",
    "real_result": None,
    "preset": "faint_intermittent",
    "seed": 7,
    "strength": -4.0,
    "interference": False,
    "observer_latitude": DEFAULT_OBSERVER["latitude_deg"],
    "observer_longitude": DEFAULT_OBSERVER["longitude_deg"],
    "observer_elevation": DEFAULT_OBSERVER["elevation_m"],
    "reveal_truth": False,
    "result": None,
}
for key, value in defaults.items():
    st.session_state.setdefault(key, value)


def reset_synthetic():
    for key in (
        "preset",
        "seed",
        "strength",
        "interference",
        "observer_latitude",
        "observer_longitude",
        "observer_elevation",
        "reveal_truth",
        "result",
    ):
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


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: radial-gradient(1200px 600px at 12% -10%, #15233d 0%, #0b1220 42%); }
        .block-container { padding-top: 1.3rem; padding-bottom: 2.2rem; max-width: 1280px; }
        .lp-kicker { color: #8aa0b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.16em; }
        h1 { font-size: 2.35rem !important; font-weight: 700 !important; color: #f4f7fb !important; }
        .lp-sub { color: #9eb3c9; font-size: 1.05rem; margin: 0.15rem 0 0.85rem 0; }
        .lp-badge { display: inline-block; background: #151e32; border: 1px solid rgba(62, 198, 224, 0.35);
                    color: #8be0ef; padding: 0.28rem 0.7rem; border-radius: 999px; font-size: 0.78rem;
                    margin-right: 0.4rem; margin-bottom: 0.35rem; }
        .lp-badge.amber { border-color: rgba(232, 176, 74, 0.45); color: #e8b04a; }
        .lp-card { background: #151e32; border: 1px solid rgba(62, 198, 224, 0.2); border-radius: 12px;
                   padding: 1rem 1.05rem; min-height: 148px; }
        .lp-card h4 { margin: 0 0 0.45rem 0; color: #d7e4f2; font-size: 0.95rem; }
        .lp-status { font-size: 1.08rem; font-weight: 700; margin: 0.1rem 0 0.35rem 0; color: #3ec6e0; }
        .lp-status.warn { color: #e8b04a; }
        .lp-score { color: #8aa0b8; font-size: 0.88rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def heatmap_layout(fig: go.Figure, xaxis: str, yaxis: str, height: int = 560) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0b1220",
        font=dict(color="#e8eef7", size=13),
        xaxis_title=xaxis,
        yaxis_title=yaxis,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0, "font": {"size": 10}},
        margin={"t": 105, "l": 50, "r": 20, "b": 50},
    )
    return fig


def track_array(values):
    return np.asarray([np.nan if value is None else value for value in values], dtype=float)


def conclusion_text(result: dict) -> str:
    return CONCLUSION_LABELS.get(result.get("conclusion"), "Insufficient evidence")


def method_score_text(method: dict) -> str:
    score = method.get("score")
    if score is None:
        return "Score unavailable"
    label = method.get("score_label", "measured score")
    return f"{label}: {score:.3f}"


inject_css()
st.markdown('<div class="lp-kicker">Mission console</div>', unsafe_allow_html=True)
st.title("LastPing")
st.markdown('<p class="lp-sub">Search for the signal that survived</p>', unsafe_allow_html=True)

with st.sidebar:
    st.radio("Input mode", ["Real recording replay", "Synthetic experiment"], key="input_mode")
    st.divider()
    if st.session_state.input_mode == "Real recording replay":
        st.selectbox(
            "Recording source",
            ["Bundled validated SatNOGS observation", "Upload recording and metadata"],
            key="real_source",
        )
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
                        st.session_state.real_result = replay_real(
                            uploaded_recording.getvalue(),
                            uploaded_metadata.getvalue(),
                        )
            except RecordingValidationError as exc:
                st.error(f"Recording validation failed: {exc}")
            except Exception as exc:  # noqa: BLE001 — surface unexpected backend failures
                st.error(f"Analysis error: {exc}")
    else:
        st.selectbox(
            "Experiment preset",
            list(PRESETS),
            key="preset",
            format_func=PRESET_LABELS.get,
            on_change=apply_preset_defaults,
        )
        st.number_input("Simulation seed", min_value=0, max_value=1_000_000, step=1, key="seed")
        st.slider(
            "Injected peak signal excess (dB)",
            -10.0,
            10.0,
            step=0.5,
            key="strength",
            help="Injected peak excess power relative to mean background; not measured RF SNR.",
        )
        st.checkbox("Add stationary interference", key="interference")
        st.number_input(
            "Observer latitude (deg)",
            min_value=-90.0,
            max_value=90.0,
            step=0.1,
            format="%.4f",
            key="observer_latitude",
        )
        st.number_input(
            "Observer longitude (deg)",
            min_value=-180.0,
            max_value=180.0,
            step=0.1,
            format="%.4f",
            key="observer_longitude",
        )
        st.number_input(
            "Observer elevation (m)",
            min_value=-500.0,
            max_value=9000.0,
            step=10.0,
            key="observer_elevation",
        )
        run_synthetic = st.button("Run analysis", type="primary", width="stretch")
        st.button("Reset controls", on_click=reset_synthetic, width="stretch")
        if run_synthetic or st.session_state.result is None:
            try:
                st.session_state.result = analyze(current_synthetic_config())
            except Exception as exc:  # noqa: BLE001
                st.error(f"Analysis error: {exc}")
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


def render_real(result):
    recording = result["recording"]
    st.markdown(
        '<span class="lp-badge amber">Radio: archived real (not live)</span>'
        '<span class="lp-badge">Orbit: historical TLE</span>'
        '<span class="lp-badge amber">ML: uncalibrated on real RF</span>',
        unsafe_allow_html=True,
    )
    st.warning(
        "Archived replay — not live reception. Audio is lossy, target-Doppler-corrected mono, "
        "not raw RF I/Q. Amplitudes are relative and uncalibrated."
    )
    label = conclusion_text(result)
    st.write(
        f"**Result:** {label} · **Best candidate:** {result['best_candidate']['name']} "
        f"(NORAD {result['best_candidate']['catalog_id']})"
    )
    st.caption(
        f"Source: {recording['label']} · SatNOGS observation {recording['observation_id']} · "
        f"acquired {recording['acquisition_start_utc']} · "
        f"{recording['receiver'].get('station_name', 'unknown station')} · "
        f"{recording['transmitter']['frequency_hz'] / 1e6:.6f} MHz {recording['transmitter']['mode']} · "
        f"SHA-256 {recording['sha256']}"
    )
    if recording.get("known_limitations"):
        st.caption("Known limitations: " + "; ".join(recording["known_limitations"][:3]))

    power = np.asarray(result["observed_power"])
    time_s = np.asarray(result["axes"]["time_s"])
    frequency_hz = np.asarray(result["axes"]["audio_frequency_hz"])
    fig = go.Figure(
        go.Heatmap(
            x=time_s,
            y=frequency_hz / 1000.0,
            z=10 * np.log10(power.T + 1e-30),
            colorscale=[
                [0.0, "#071018"],
                [0.35, "#12324a"],
                [0.65, "#1f8aa8"],
                [0.85, "#3ec6e0"],
                [1.0, "#e8b04a"],
            ],
            colorbar_title="Relative PSD dB/Hz",
        )
    )
    colors = ["#e8b04a", "#f0d48a", "#9eb3c9", "#8be0ef"]
    for color, candidate in zip(colors, result["candidates"]):
        fig.add_trace(
            go.Scatter(
                x=time_s,
                y=track_array(candidate["predicted_track_hz"]) / 1000.0,
                name=f"predicted: {candidate['name']}",
                line={"color": color, "dash": "dash", "width": 1},
            )
        )
    best = result["candidates"][0]
    fig.add_trace(
        go.Scatter(
            x=time_s,
            y=track_array(best["fitted_template_hz"]) / 1000.0,
            name="best fitted template",
            line={"color": "#e08a3e", "width": 2},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=time_s,
            y=track_array(result["observed_ridge_hz"]) / 1000.0,
            name="independent measured ridge",
            mode="markers",
            marker={"color": "#f4f7fb", "size": 3},
        )
    )
    heatmap_layout(fig, "Seconds after acquisition start", "Doppler-corrected audio frequency (kHz)", 620)
    st.plotly_chart(fig, width="stretch")
    st.caption(
        f"Waterfall {power.shape[0]} time bins × {power.shape[1]} frequency bins. "
        "The measured ridge is extracted independently of candidate templates."
    )

    st.subheader("Candidate evidence")
    rows = []
    for candidate in result["candidates"]:
        ml_score = candidate["ml"].get("score")
        rows.append(
            {
                "Candidate": candidate["name"],
                "NORAD": candidate["catalog_id"],
                "Physics score": round(candidate["score"], 3),
                "Frequency offset (Hz)": candidate["best_frequency_offset_hz"],
                "Above-horizon support": round(candidate["above_horizon_support"], 3),
                "Ridge RMS residual (Hz)": candidate["ridge_residual_rms_hz"],
                "Synthetic-model score (uncalibrated)": None if ml_score is None else round(ml_score, 3),
            }
        )
    st.dataframe(rows, width="stretch", hide_index=True)

    cols = st.columns(3)
    cards = [
        ("Signal-strength threshold", result["methods"]["baseline"], "Measured; no real threshold", "warn"),
        ("Physics-guided ranking", result["methods"]["physics"], label, ""),
        ("ML classifier", result["methods"]["ml"], "Experimental, uncalibrated on real RF", "warn"),
    ]
    for col, (title, method, decision, klass) in zip(cols, cards):
        with col:
            if method.get("status") == "unavailable":
                extra = method.get("setup_instruction", "No trained model is loaded.")
                st.markdown(
                    f"<div class='lp-card'><h4>{title}</h4>"
                    f"<div class='lp-status warn'>Unavailable</div>"
                    f"<div class='lp-score'>{method_score_text(method)}</div>"
                    f"<div class='lp-score'>{extra}</div></div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div class='lp-card'><h4>{title}</h4>"
                    f"<div class='lp-status {klass}'>{decision}</div>"
                    f"<div class='lp-score'>{method_score_text(method)}</div></div>",
                    unsafe_allow_html=True,
                )
            if method.get("score_label") == "synthetic-model score":
                st.metric("synthetic-model score", "Unavailable" if method.get("score") is None else f"{method['score']:.3f}")

    st.caption(
        f"Full processing: {result['timings']['total_processing_s']:.3f} s; acquisition duration: "
        f"{result['signal_processing']['decoded_duration_s']:.3f} s. These are separate quantities."
    )
    st.info(result["calibration"]["warning"])

    with st.expander("Recording provenance, calibration and evaluation evidence"):
        st.json(
            {
                "recording": recording,
                "signal_processing": result["signal_processing"],
                "calibration": result["calibration"],
                "evaluation": result["evaluation"],
                "timings": result["timings"],
            }
        )
    export = {key: value for key, value in result.items() if key != "observed_power"}
    st.download_button(
        "Download real-analysis JSON",
        json.dumps(export, indent=2, allow_nan=False),
        "lastping_real_analysis.json",
        "application/json",
    )


def render_synthetic(result):
    analyzed = result["configuration"]
    controls_changed = any(
        [
            analyzed["preset"] != st.session_state.preset,
            analyzed["seed"] != int(st.session_state.seed),
            analyzed["signal_excess_db"] != float(st.session_state.strength),
            analyzed.get("interference") != bool(st.session_state.interference),
            analyzed["observer"] != current_synthetic_config()["observer"],
        ]
    )
    if controls_changed:
        st.warning("Controls have changed since this result was computed. Select **Run analysis** to update it.")
    provenance = result["provenance"]
    orbit = provenance["orbit"]
    st.markdown(
        '<span class="lp-badge amber">Radio: simulated</span>'
        f'<span class="lp-badge{" amber" if orbit["kind"] == "synthetic_orbit_fallback" else ""}">'
        f'Orbit: {orbit["kind"]}</span>'
        '<span class="lp-badge">Experiment: synthetic (not a recording)</span>',
        unsafe_allow_html=True,
    )
    if orbit["kind"] == "synthetic_orbit_fallback":
        st.warning("No verified orbit cache is available. Geometry is an explicitly synthetic LEO fallback.")
    else:
        st.success(
            f"Synthetic experiment · orbit: {orbit['satellite_name']} (NORAD {orbit['catalog_id']}) via CelesTrak"
        )
        if orbit["stale_warning"]:
            st.warning(
                f"Orbital elements are stale for this recording ({orbit['tle_age_at_recording_days']:.1f} days)."
            )
        st.caption(
            f"Orbital epoch: {orbit['orbital_epoch_utc']} · Replay start: {orbit['recording_start_utc']} · "
            f"Source: {orbit['source_url']}"
        )
    st.info("Radio provenance: simulated power spectrogram—not recorded raw I/Q. Carrier is an assumed 437 MHz.")

    power = np.asarray(result["observed_power"])
    times = np.asarray(result["axes"]["time_s"])
    freq = np.asarray(result["axes"]["frequency_hz"])
    fig = go.Figure(
        go.Heatmap(
            x=times,
            y=freq / 1000.0,
            z=10 * np.log10(power.T + 1e-9),
            colorscale=[
                [0.0, "#071018"],
                [0.35, "#12324a"],
                [0.65, "#1f8aa8"],
                [0.85, "#3ec6e0"],
                [1.0, "#e8b04a"],
            ],
            colorbar_title="Relative power (dB)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=times,
            y=track_array(result["tracks"]["predicted_hz"]) / 1000.0,
            name="predicted track",
            line={"color": "#e8b04a", "dash": "dash"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=times,
            y=track_array(result["tracks"]["detected_hz"]) / 1000.0,
            name="detected track",
            line={"color": "#3ec6e0"},
        )
    )
    truth = result["tracks"]["ground_truth_hz"]
    if st.toggle("Reveal simulation ground truth", key="reveal_truth") and truth is not None:
        fig.add_trace(
            go.Scatter(
                x=times,
                y=track_array(truth) / 1000.0,
                name="simulated ground truth",
                line={"color": "#f4f7fb", "dash": "dot"},
            )
        )
    heatmap_layout(fig, "Elapsed seconds", "Offset from assumed 437 MHz (kHz)", 520)
    st.plotly_chart(fig, width="stretch")
    st.caption(f"Waterfall {power.shape[0]} time bins × {power.shape[1]} frequency bins. Ground truth is display-only.")

    cols = st.columns(3)
    for col, key, title in zip(
        cols,
        ["baseline", "physics", "ml"],
        ["Signal-strength threshold", "Physics-guided detection", "ML classifier"],
    ):
        method = result["methods"][key]
        with col:
            if method["status"] != "ok":
                st.markdown(
                    f"<div class='lp-card'><h4>{title}</h4>"
                    f"<div class='lp-status warn'>Unavailable</div>"
                    f"<div class='lp-score'>{method.get('setup_instruction', 'No trained model is loaded.')}</div></div>",
                    unsafe_allow_html=True,
                )
                st.metric("Status", "Unavailable")
                st.caption(method.get("setup_instruction", ""))
            else:
                decision = method["decision"]
                if decision is None:
                    decision_text = "Not calibrated"
                elif decision:
                    decision_text = "Candidate beacon"
                else:
                    decision_text = "Insufficient evidence"
                st.markdown(
                    f"<div class='lp-card'><h4>{title}</h4>"
                    f"<div class='lp-status'>{decision_text}</div>"
                    f"<div class='lp-score'>{method_score_text(method)}</div></div>",
                    unsafe_allow_html=True,
                )
                st.metric(method.get("score_label", "measured score"), f"{method['score']:.3f}")
                st.caption(f"Inference runtime: {method['runtime_s'] * 1000:.2f} ms")

    with st.expander("Provenance and measured details"):
        st.json({"orbit": orbit, "radio": provenance["radio"], "ground_truth": result["ground_truth"]})
    export = {key: value for key, value in result.items() if key != "observed_power"}
    st.download_button(
        "Download synthetic-analysis JSON",
        json.dumps(export, indent=2, allow_nan=False),
        "lastping_synthetic_analysis.json",
        "application/json",
    )


if st.session_state.input_mode == "Real recording replay":
    if st.session_state.real_result is None:
        st.info(
            "Select **Analyze recording** to run the bundled, validated SatNOGS observation entirely offline. "
            "The included audio is an archived real reception, not a live receiver or synthetic substitute."
        )
    else:
        render_real(st.session_state.real_result)
else:
    if st.session_state.result is None:
        st.error("Synthetic analysis has not produced a result yet.")
    else:
        render_synthetic(st.session_state.result)

if "benchmark" in st.session_state:
    st.subheader("Fresh synthetic benchmark")
    st.caption("This block is from an explicit **Run synthetic benchmark** click, not a Streamlit rerun.")
    st.json(st.session_state.benchmark)
with st.expander("Saved synthetic benchmark (historical measurements)"):
    st.caption(
        "These timings were measured when the saved artifact was created; opening this section does not rerun evaluation."
    )
    st.json(saved_benchmark())
