from pathlib import Path

import httpx
import pytest
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from slr.gateway import Calls, MeasuredModel, Telemetry
from slr.models import Passage, ReviewConfig, ReviewRun, ScreeningDecision
from slr.settings import Settings
from slr.sources import ScientificSources, normalize_doi
from slr.storage import DiskStore, StaleRunError


def test_resume_persists_and_checks_version(tmp_path):
    run = ReviewRun(config=ReviewConfig(topic="Automatic screening in systematic reviews"))
    DiskStore(tmp_path).save(run)
    store = DiskStore(tmp_path)
    stale = store.load(run.id)
    store.save(run)
    assert store.load(run.id).version == 2
    with pytest.raises(StaleRunError):
        store.save(stale)


def test_validation_rejects_invalid_contracts():
    with pytest.raises(ValidationError):
        ReviewConfig(topic="Automatic screening in systematic reviews", provider="other")
    with pytest.raises(ValidationError):
        Passage(id="e", rq_id="RQ1", paper_id="p", chunk_id="c", quote="Title", kind="full_text")
    with pytest.raises(ValidationError):
        ScreeningDecision(paper_id="p", final="uncertain", decided_by="automatic", reason="missing")


def test_http_rate_limit_retry_and_cache(tmp_path):
    requests = []
    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"message": {"items": [{"title": ["Bibliography"], "DOI": "10.1/real"}]}})

    settings = Settings()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        telemetry = Telemetry()
        calls = Calls(DiskStore(tmp_path), telemetry, 120)
        source = ScientificSources(settings, calls, client)
        assert source.search("crossref", "literature", 1)[0].doi == "10.1/real"
        again = ScientificSources(settings, Calls(DiskStore(tmp_path), telemetry, 120), client)
        assert again.search("crossref", "literature", 1)[0].title == "Bibliography"
    assert len(requests) == 2
    assert [e.status for e in telemetry.events] == ["error", "ok", "cache_hit"]
    assert telemetry.events[1].retry
    assert normalize_doi("https://doi.org/10.1/REAL") == "10.1/real"


def test_model_cache_counts_only_actual_tokens(tmp_path):
    class Fake:
        def invoke(self, prompt):
            return AIMessage(content="Answer", usage_metadata={"input_tokens": 7, "output_tokens": 1, "total_tokens": 8})
    telemetry = Telemetry()
    model = MeasuredModel(Fake(), "ollama", "test-model", Calls(DiskStore(tmp_path), telemetry, 120))
    assert model.invoke("RQ").content == model.invoke("RQ").content
    assert [e.input_tokens for e in telemetry.events] == [7, None]
