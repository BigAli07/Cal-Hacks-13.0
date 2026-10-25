from __future__ import annotations

import json
from copy import deepcopy

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from core.engine import PRESETS, analyze, benchmark

DEFAULTS = {
    "observer_lat_deg": 37.7749,
    "observer_lon_deg": -122.4194,
    "preset": "faint_intermittent",
    "signal_excess_db": 6.0,
    "interference": False,
    "seed": 42,
}

PRESET_LABELS = {
    "strong_beacon": "Strong beacon",
    "faint_intermittent": "Faint intermittent beacon",
    "interference_only": "Interference only",
    "noise_only": "Noise only",
}

STATUS_LABELS = {
    "pending": "Pending",
    "candidate": "Candidate beacon",
    "insufficient_evidence": "Insufficient evidence",
    "unavailable": "Unavailable",
}

METHOD_TITLES = {
    "threshold": "Signal-strength threshold",
    "physics": "Physics-guided detection",
    "ml": "ML classifier",
}

ALLOWED_STATUS = set(STATUS_LABELS)


def _init_state() -> None:
    if "analysis" not in st.session_state:
        st.session_state.analysis = None
    if "benchmark" not in st.session_state:
        st.session_state.benchmark = None
    if "error" not in st.session_state:
        st.session_state.error = None
    if "loading" not in st.session_state:
        st.session_state.loading = False
    if "run_analyze" not in st.session_state:
        st.session_state.run_analyze = False
    if "run_benchmark" not in st.session_state:
        st.session_state.run_benchmark = False
    if "controls" not in st.session_state:
        st.session_state.controls = deepcopy(DEFAULTS)


def _current_config() -> dict:
    return {
        "observer_lat_deg": st.session_state.observer_lat_deg,
        "observer_lon_deg": st.session_state.observer_lon_deg,
        "preset": st.session_state.preset,
        "signal_excess_db": st.session_state.signal_excess_db,
        "interference": st.session_state.interference,
        "seed": int(st.session_state.seed),
    }


def _request_analyze() -> None:
    st.session_state.run_analyze = True
    st.session_state.error = None


def _request_reset() -> None:
    st.session_state.analysis = None
    st.session_state.benchmark = None
    st.session_state.error = None
    st.session_state.loading = False
    st.session_state.run_analyze = False
    st.session_state.run_benchmark = False
    for key, value in DEFAULTS.items():
        st.session_state[key] = value
    st.session_state.controls = deepcopy(DEFAULTS)
    st.session_state.show_prediction = True
    st.session_state.show_detected = True
    st.session_state.reveal_truth = False


def _request_benchmark() -> None:
    st.session_state.run_benchmark = True


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: radial-gradient(1200px 600px at 12% -10%, #15233d 0%, #0b1220 42%); }
        .block-container { padding-top: 1.4rem; padding-bottom: 2.4rem; max-width: 1280px; }
        h1, h2, h3 { letter-spacing: 0.02em; }
        .lp-kicker { color: #8aa0b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.16em; margin-bottom: 0.2rem; }
        h1 { font-size: 2.45rem !important; font-weight: 700 !important; color: #f4f7fb !important; letter-spacing: 0.01em; }
        .lp-sub { color: #9eb3c9; font-size: 1.05rem; margin: 0.1rem 0 0.85rem 0; }
        .lp-banner { background: rgba(192, 146, 54, 0.14); border: 1px solid rgba(232, 176, 74, 0.45); color: #f0d48a; padding: 0.7rem 0.95rem; border-radius: 10px; font-weight: 600; margin: 0.4rem 0 1rem 0; }
        .lp-badge { display: inline-block; background: #151e32; border: 1px solid rgba(62, 198, 224, 0.35); color: #8be0ef; padding: 0.28rem 0.7rem; border-radius: 999px; font-size: 0.78rem; margin-right: 0.4rem; margin-bottom: 0.35rem; }
        .lp-badge.amber { border-color: rgba(232, 176, 74, 0.45); color: #e8b04a; }
        .lp-meta { background: #151e32; border: 1px solid rgba(62, 198, 224, 0.18); border-radius: 12px; padding: 0.9rem 1rem; margin-bottom: 1rem; }
        .lp-meta span { display: inline-block; min-width: 46%; margin: 0.18rem 0; color: #c5d3e3; font-size: 0.92rem; }
        .lp-meta b { color: #e8eef7; }
        .lp-card { background: #151e32; border: 1px solid rgba(62, 198, 224, 0.2); border-radius: 12px; padding: 1rem 1.05rem 1.05rem; min-height: 168px; }
        .lp-card h4 { margin: 0 0 0.55rem 0; color: #d7e4f2; font-size: 0.95rem; }
        .lp-status { font-size: 1.15rem; font-weight: 700; margin: 0.15rem 0 0.4rem 0; }
        .lp-pending { color: #e8b04a; }
        .lp-candidate { color: #3ec6e0; }
        .lp-insufficient { color: #9aa7b8; }
        .lp-unavailable { color: #e08a3e; }
        .lp-score { color: #8aa0b8; font-size: 0.88rem; }
        .lp-empty { color: #9eb3c9; background: #121a2b; border: 1px dashed rgba(158, 179, 201, 0.35); border-radius: 12px; padding: 1.4rem; text-align: center; }
        .lp-error { background: rgba(176, 62, 62, 0.16); border: 1px solid rgba(224, 98, 98, 0.45); color: #f0b4b4; padding: 0.8rem 1rem; border-radius: 10px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _fmt(value, fallback="Unavailable") -> str:
    if value is None or value == "" or value == []:
        return fallback
    return str(value)


def _status_class(status: str) -> str:
    return {
        "pending": "lp-pending",
        "candidate": "lp-candidate",
        "insufficient_evidence": "lp-insufficient",
        "unavailable": "lp-unavailable",
    }.get(status, "lp-pending")


def _normalize_result_row(row: dict | None) -> dict:
    row = row or {}
    status = row.get("status") or "pending"
    if status not in ALLOWED_STATUS:
        status = "pending"
    score = row.get("score", None)
    return {"status": status, "score": score}


def _score_text(method_key: str, score) -> str:
    if score is None:
        return "Score unavailable"
    if method_key == "ml":
        return f"synthetic-model score: {score}"
    return f"Score: {score}"


def _provenance_badges(payload: dict | None) -> str:
    prov = (payload or {}).get("provenance") or {}
    radio = prov.get("radio", "simulated")
    orbit = prov.get("orbit", "unavailable")
    cache = prov.get("cache")
    model = prov.get("model", "missing")
    radio_label = f"Radio: {radio}"
    if orbit in {"real", "cached"}:
        orbit_label = f"Orbit: {orbit}"
        orbit_cls = "lp-badge"
    elif orbit == "synthetic":
        orbit_label = "Orbit: synthetic"
        orbit_cls = "lp-badge amber"
    else:
        orbit_label = "Orbit: unavailable"
        orbit_cls = "lp-badge amber"
    cache_label = f"Cache: {cache}" if cache else "Cache: none"
    model_label = "Model: missing" if model in {None, "missing", "unavailable"} else f"Model: {model}"
    return (
        f'<span class="lp-badge">{radio_label}</span>'
        f'<span class="{orbit_cls}">{orbit_label}</span>'
        f'<span class="lp-badge">{cache_label}</span>'
        f'<span class="lp-badge amber">{model_label}</span>'
    )


def _validate_spectrum(spectrum: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    times = np.asarray(spectrum.get("times_s") or [], dtype=float)
    freqs = np.asarray(spectrum.get("frequency_offsets_hz") or [], dtype=float)
    power = np.asarray(spectrum.get("power_db") or [], dtype=float)
    if power.ndim != 2:
        raise ValueError("spectrum.power_db must have shape [time][frequency].")
    if power.shape != (times.size, freqs.size):
        raise ValueError(
            f"Heatmap dimension mismatch: power_db {tuple(power.shape)} vs "
            f"times {times.size} × frequencies {freqs.size}."
        )
    return times, freqs, power


def _waterfall(payload: dict, show_pred: bool, show_det: bool, show_truth: bool) -> go.Figure:
    times, freqs, power = _validate_spectrum(payload.get("spectrum") or {})
    fig = go.Figure(
        data=[
            go.Heatmap(
                z=power,
                x=freqs,
                y=times,
                colorscale=[
                    [0.0, "#071018"],
                    [0.35, "#12324a"],
                    [0.65, "#1f8aa8"],
                    [0.85, "#3ec6e0"],
                    [1.0, "#e8b04a"],
                ],
                colorbar=dict(title="Relative power (dB)", thickness=16),
                hovertemplate="Δf %{x:.1f} Hz<br>t %{y:.2f} s<br>%{z:.2f} dB<extra></extra>",
            )
        ]
    )
    pred = payload.get("prediction") or {}
    if show_pred and pred.get("times_s") and pred.get("frequency_offsets_hz"):
        fig.add_trace(
            go.Scatter(
                x=pred["frequency_offsets_hz"],
                y=pred["times_s"],
                mode="lines",
                name="Predicted track",
                line=dict(color="#e8b04a", width=2),
            )
        )
    det = payload.get("detected_track")
    if show_det and isinstance(det, dict) and det.get("times_s") and det.get("frequency_offsets_hz"):
        fig.add_trace(
            go.Scatter(
                x=det["frequency_offsets_hz"],
                y=det["times_s"],
                mode="lines",
                name="Detected track",
                line=dict(color="#3ec6e0", width=2, dash="dash"),
            )
        )
    gt = payload.get("ground_truth") or {}
    if show_truth and gt.get("times_s") and gt.get("frequency_offsets_hz"):
        fig.add_trace(
            go.Scatter(
                x=gt["frequency_offsets_hz"],
                y=gt["times_s"],
                mode="markers",
                name="Simulated ground truth",
                marker=dict(color="#f4f7fb", size=5, opacity=0.7),
            )
        )
    fig.update_layout(
        margin=dict(l=50, r=20, t=30, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0b1220",
        font=dict(color="#e8eef7", size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        height=560,
        xaxis_title="Frequency offset (Hz)",
        yaxis_title="Elapsed seconds",
        yaxis=dict(autorange="reversed"),
    )
    return fig


def _method_card(key: str, payload: dict | None) -> None:
    results = (payload or {}).get("results") or {}
    row = _normalize_result_row(results.get(key))
    status = row["status"]
    label = STATUS_LABELS[status]
    extra = ""
    if key == "ml" and status in {"pending", "unavailable"}:
        extra = "<div class='lp-score'>No trained model is loaded.</div>"
    st.markdown(
        f"""
        <div class="lp-card">
          <h4>{METHOD_TITLES[key]}</h4>
          <div class="lp-status {_status_class(status)}">{label}</div>
          <div class="lp-score">{_score_text(key, row['score'])}</div>
          {extra}
        </div>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="LastPing", layout="wide")
_init_state()
_inject_css()

# Seed widget keys before sidebar widgets instantiate.
for _key, _value in DEFAULTS.items():
    st.session_state.setdefault(_key, _value)
st.session_state.setdefault("show_prediction", True)
st.session_state.setdefault("show_detected", True)
st.session_state.setdefault("reveal_truth", False)

with st.sidebar:
    st.markdown("**Observation**")
    st.number_input("Observer latitude (°)", -90.0, 90.0, step=0.0001, format="%.4f", key="observer_lat_deg")
    st.number_input("Observer longitude (°)", -180.0, 180.0, step=0.0001, format="%.4f", key="observer_lon_deg")
    st.selectbox(
        "Recording preset",
        options=list(PRESETS),
        format_func=lambda p: PRESET_LABELS[p],
        key="preset",
    )
    st.slider("Injected signal strength (dB excess)", -6.0, 24.0, step=0.5, key="signal_excess_db")
    st.toggle("Add interference", key="interference")
    st.number_input("Reproducible seed", min_value=0, max_value=1_000_000, step=1, key="seed")
    c1, c2 = st.columns(2)
    c1.button("Analyze", type="primary", on_click=_request_analyze, width="stretch")
    c2.button("Reset", on_click=_request_reset, width="stretch")
    st.caption("Controls do not regenerate results until Analyze.")

if st.session_state.run_analyze:
    st.session_state.run_analyze = False
    st.session_state.loading = True
    try:
        st.session_state.analysis = analyze(_current_config())
        st.session_state.error = None
    except Exception as exc:  # noqa: BLE001 — surface backend errors in the UI
        st.session_state.analysis = None
        st.session_state.error = str(exc)
    finally:
        st.session_state.loading = False

if st.session_state.run_benchmark:
    st.session_state.run_benchmark = False
    try:
        st.session_state.benchmark = benchmark()
    except Exception as exc:  # noqa: BLE001
        st.session_state.error = str(exc)

payload = st.session_state.analysis

st.markdown('<div class="lp-kicker">Mission console</div>', unsafe_allow_html=True)
st.title("LastPing")
st.markdown('<p class="lp-sub">Search for the signal that survived</p>', unsafe_allow_html=True)
st.markdown(_provenance_badges(payload), unsafe_allow_html=True)

mode = (payload or {}).get("mode", "placeholder")
if mode == "placeholder" or payload is None:
    st.markdown('<div class="lp-banner">Placeholder — backend pending</div>', unsafe_allow_html=True)

if st.session_state.error:
    st.markdown(f'<div class="lp-error">Analysis error: {st.session_state.error}</div>', unsafe_allow_html=True)

sat = (payload or {}).get("satellite") or {}
obs = (payload or {}).get("observation") or {}
m1, m2, m3 = st.columns(3)
m1.markdown(f"**Satellite**  \n{_fmt(sat.get('name'))}")
m1.markdown(f"**Catalog ID**  \n{_fmt(sat.get('catalog_id'))}")
m2.markdown(f"**Orbit epoch**  \n{_fmt(sat.get('orbit_epoch'))}")
m2.markdown(f"**Source**  \n{_fmt(sat.get('source'))}")
m3.markdown(f"**Observation time**  \n{_fmt(obs.get('time_utc'))}")
m3.markdown(
    f"**Observer**  \n{_fmt(obs.get('observer_lat_deg'), '—')}°, {_fmt(obs.get('observer_lon_deg'), '—')}°"
)

toggles = st.columns((1, 1, 1.3))
toggles[0].toggle("Predicted track", key="show_prediction")
toggles[1].toggle("Detected track", key="show_detected")
toggles[2].toggle("Reveal simulated ground truth", key="reveal_truth")

if st.session_state.loading:
    st.info("Analyzing recording… detectors are not trained on this rerun.")
elif payload is None:
    st.markdown(
        '<div class="lp-empty">No analysis yet. Set observer and recording controls, then choose Analyze.</div>',
        unsafe_allow_html=True,
    )
else:
    try:
        st.plotly_chart(
            _waterfall(
                payload,
                st.session_state.show_prediction,
                st.session_state.show_detected,
                st.session_state.reveal_truth,
            ),
            width="stretch",
        )
        spec = payload.get("spectrum") or {}
        power = np.asarray(spec.get("power_db") or [])
        st.caption(
            f"Heatmap {power.shape[0]} time bins × {power.shape[1]} frequency bins. "
            "Ground truth is display-only and is not fed back into analysis."
        )
    except Exception as exc:  # noqa: BLE001
        st.markdown(f'<div class="lp-error">Display error: {exc}</div>', unsafe_allow_html=True)

cards = st.columns(3)
for col, key in zip(cards, ("threshold", "physics", "ml")):
    with col:
        _method_card(key, payload)

st.subheader("Evidence")
evidence = (payload or {}).get("evidence") or []
if payload is None:
    st.caption("Evidence appears after Analyze.")
elif not evidence:
    st.info("No evidence items yet. Backend pending.")
else:
    for item in evidence:
        st.write(f"• {item}")

st.subheader("Benchmark")
st.button("Run benchmark", on_click=_request_benchmark)
bench = st.session_state.benchmark
if bench is None:
    st.caption("Benchmark is a separate action and does not train a model.")
else:
    status = bench.get("status", "pending")
    st.write(f"Status: {STATUS_LABELS.get(status, 'Pending')}")
    methods = bench.get("methods") or []
    if not methods:
        st.info("No measured performance yet. Do not treat pending scores as results.")
    else:
        st.dataframe(methods, width="stretch")
    metadata = bench.get("metadata") or {}
    if metadata:
        st.json(metadata)

with st.expander("Provenance and limitations"):
    st.write(
        "Radio recordings in this build are simulated. Orbital fields are unlabeled "
        "until public TLE/OMM data is wired in. Detector cards stay pending unless "
        "the backend returns an allowed status. ML scores are synthetic-model scores, "
        "not real-world probabilities. This interface never reports satellite recovery."
    )
    if payload:
        st.json(payload.get("provenance") or {})
        st.caption(f"Runtime: {_fmt((payload or {}).get('runtime_ms'))} ms · mode `{mode}`")

if payload:
    st.download_button(
        "Download JSON result",
        data=json.dumps(payload, indent=2),
        file_name="lastping_result.json",
        mime="application/json",
    )
