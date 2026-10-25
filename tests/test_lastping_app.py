from streamlit.testing.v1 import AppTest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app.py"
REAL_DIR = APP.parent / "data" / "real"


def test_controls_wait_for_analysis_and_reset():
    app = AppTest.from_file(APP).run(timeout=30)
    assert not app.exception
    app.radio[0].set_value("Synthetic experiment").run(timeout=30)
    original_scores = [metric.value for metric in app.metric]

    app.number_input[0].set_value(8).run(timeout=30)
    assert any("Controls have changed" in warning.value for warning in app.warning)
    assert [metric.value for metric in app.metric] == original_scores

    app.button[0].click().run(timeout=30)
    assert not any("Controls have changed" in warning.value for warning in app.warning)
    assert app.session_state.result["configuration"]["seed"] == 8

    app.toggle[0].set_value(True).run(timeout=30)
    app.button[1].click().run(timeout=30)
    assert app.number_input[0].value == 7
    assert app.selectbox[0].value == "faint_intermittent"
    assert app.checkbox[0].value is False
    assert app.toggle[0].value is False


def test_observer_and_interference_controls_reach_backend():
    app = AppTest.from_file(APP).run(timeout=30)
    app.radio[0].set_value("Synthetic experiment").run(timeout=30)
    app.checkbox[0].set_value(True)
    app.number_input[1].set_value(40.7128)
    app.number_input[2].set_value(-74.0060)
    app.button[0].click().run(timeout=30)
    assert not app.exception
    config = app.session_state.result["configuration"]
    assert config["interference"] is True
    assert config["observer"]["latitude_deg"] == 40.7128
    assert config["observer"]["longitude_deg"] == -74.0060


def test_bundled_real_replay_runs_only_on_analyze_and_reset_clears_it():
    app = AppTest.from_file(APP).run(timeout=30)
    assert app.radio[0].value == "Real recording replay"
    assert app.session_state.real_result is None
    app.button[0].click().run(timeout=30)
    assert not app.exception
    assert app.session_state.real_result["mode"] == "archived_real_recording"
    assert app.session_state.real_result["best_candidate"]["catalog_id"] == "39444"
    assert any(metric.label == "synthetic-model score" for metric in app.metric)
    app.button[1].click().run(timeout=30)
    assert app.session_state.real_result is None


def test_supported_upload_replays_the_same_validated_recording():
    app = AppTest.from_file(APP).run(timeout=30)
    app.selectbox[0].set_value("Upload recording and metadata").run(timeout=30)
    app.get("file_uploader")[0].upload(
        "satnogs_6659851_2022-10-26T04-12-41.ogg",
        (REAL_DIR / "satnogs_6659851_2022-10-26T04-12-41.ogg").read_bytes(),
        "audio/ogg",
    )
    app.get("file_uploader")[1].upload(
        "satnogs_6659851_manifest.json",
        (REAL_DIR / "satnogs_6659851_manifest.json").read_bytes(),
        "application/json",
    )
    app.run(timeout=30)
    app.button[0].click().run(timeout=30)
    assert not app.exception
    result = app.session_state.real_result
    assert result["recording"]["local_source"] == "uploaded recording"
    assert result["best_candidate"]["catalog_id"] == "39444"
