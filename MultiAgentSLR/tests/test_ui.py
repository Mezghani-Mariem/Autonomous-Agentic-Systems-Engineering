from pathlib import Path

from streamlit.testing.v1 import AppTest
from slr.storage import DiskStore
from slr.supervisor import Supervisor
from conftest import ControlledModel, CourseSnapshot, TOPIC


def test_streamlit_chat_starts(tmp_path, monkeypatch):
    monkeypatch.setenv("SLR_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SLR_ACCESS_TOKEN", "")
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
    assert not at.exception
    assert len(at.chat_input) == 1
    assert at.title[0].value == "Multi-Agent SLR"


def test_streamlit_chat_runs_and_renders_report(tmp_path, monkeypatch):
    monkeypatch.setenv("SLR_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SLR_ACCESS_TOKEN", "")
    original = Supervisor.__init__

    def controlled(self, store, settings, **kwargs):
        original(self, store, settings, model=ControlledModel(), sources=CourseSnapshot())

    monkeypatch.setattr(Supervisor, "__init__", controlled)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=15).run()
    at.chat_input[0].set_value(TOPIC).run()
    assert not at.exception
    assert any("Review status · **complete**" in node.value for node in at.markdown)
    assert len(at.get("download_button")) == 2


def test_streamlit_saves_short_screening_reason_for_the_correct_paper(tmp_path, monkeypatch):
    monkeypatch.setenv("SLR_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SLR_ACCESS_TOKEN", "")
    original = Supervisor.__init__
    record = CourseSnapshot(missing_abstract=True).record

    class TwoPending:
        def search(self, source, query, limit):
            if source != record.source:
                return []
            return [record, record.model_copy(update={"native_id": "fixture-second", "doi": "",
                                                      "title": "Second title with no abstract"})]

    def controlled(self, store, settings, **kwargs):
        original(self, store, settings, model=ControlledModel(), sources=TwoPending())

    monkeypatch.setattr(Supervisor, "__init__", controlled)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=15).run()
    mode = next(widget for widget in at.radio if widget.label == "Execution mode")
    assert mode.value == "automatic"
    mode.set_value("human_in_the_loop").run()
    at.chat_input[0].set_value(TOPIC).run()
    store = DiskStore(tmp_path)
    paused = store.recent()[0]
    assert paused.status == "awaiting_screening"
    first, second = paused.screening.decisions
    key = f"screen-{paused.id}-{second.paper_id}"
    at.radio(key=f"{key}-decision").set_value("exclude")
    at.text_area(key=f"{key}-reason").set_value("No.")
    buttons = [widget for widget in at.button if widget.label == "Save screening decision"]
    buttons[1].click().run()
    assert not at.exception
    assert not any("Provide a reason" in item.value for item in at.error)
    saved = {item.paper_id: item for item in store.load(paused.id).screening.decisions}
    assert saved[first.paper_id].final == "uncertain"
    assert (saved[second.paper_id].final, saved[second.paper_id].reason) == ("exclude", "No.")
