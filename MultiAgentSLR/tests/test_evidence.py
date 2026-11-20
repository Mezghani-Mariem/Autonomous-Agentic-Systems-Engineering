import json

import pytest

from slr.models import EvidenceLocation, SourceRecord
from slr.retrieval import build_corpus, extract_passages, retrieve, verify_excerpt
from slr.sources import consolidate, normalize_openalex, normalize_rows
from slr.synthesis import evidence_items
from test_review import workflow

from conftest import ControlledModel, Structured


def openalex_record():
    raw = {
        "id": "https://openalex.org/w-test",
        "title": "Evaluation of title screening",
        "abstract_inverted_index": {
            "reported.": [9], "Screening": [0], "Sensitivity": [6], "was": [1, 7],
            "by": [3], "two": [4], "reviewers.": [5], "evaluated": [2], "also": [8],
        },
    }
    return SourceRecord.model_validate(normalize_rows("openalex", [raw], normalize_openalex)[0])


def test_search_and_screening_handoff_keeps_reconstructed_abstract(tmp_path, config):
    record = openalex_record()

    class Search:
        def search(self, source, query, limit):
            return [record] if source == "openalex" else []

    run = workflow(tmp_path, source=Search()).start(config)
    assert run.status == "complete", run.error or run.outcome_reason
    paper, = run.search.papers
    assert paper.abstract == "Screening was evaluated by two reviewers. Sensitivity was also reported."
    decision, = run.screening.decisions
    assert decision.paper_id == paper.id and decision.final == "include"
    assert run.rag.corpus.model_dump() == {"included_abstracts": 1, "abstract_chunks": 1,
                                           "full_text_chunks": 0, "missing_text_paper_ids": []}
    chunk, = build_corpus([paper], {paper.id}, {})
    assert chunk.chunk_id == f"abstract:{paper.id}_c1" and chunk.page is None
    assert all(e.source_type == "abstract" and e.page is None and e.paper_id == paper.id
               and e.source_record_id == record.native_id and e.source == "openalex" and e.quote in chunk.text
               for e in run.rag.evidence)
    refs = {e.id for e in run.rag.evidence}
    assert set().union(*(set(c.evidence_ids) for c in run.retained_claims())) == refs
    assert all(item.page is None for item in evidence_items(run))
    assert [h.target for h in run.handoffs[-3:]] == ["writing", "quality", "finish"]
    assert all(item.judgment == "supported" for item in run.quality[-1].findings)


def test_abstract_chunks_are_stable_and_skip_missing_and_uncertain_papers():
    long_text = "Screening records were compared with independent annotations. " * 34
    first = openalex_record().model_copy(update={"abstract": long_text})
    records = [first, SourceRecord(source="crossref", native_id="no-text", title="No abstract"),
               SourceRecord(source="crossref", native_id="uncertain", title="Uncertain study", abstract="Full abstract.")]
    papers = consolidate(records)
    included = {p.id for p in papers if p.title != "Uncertain study"}
    chunks = build_corpus(papers, included, {})
    assert len(chunks) == 3 and chunks == build_corpus(papers, included, {})
    assert all(c.text in long_text and c.source_record_id == first.native_id and c.page is None for c in chunks)
    selected, result = retrieve(chunks, "records screening annotations", [], "RQ1", "classical", 2, 1)
    assert len(selected) == 2 and result.ranks == [item["chunk_id"] for item in selected]


@pytest.mark.parametrize("change,quote,expected", [
    ({}, "reviewers.", ""),
    ({}, "Reviewers.", "exact"),
    ({}, "[CHUNK abstract:P-test_c1]", "exact"),
    ({"paper_id": "another-paper"}, "reviewers.", "provenance"),
    ({"chunk_id": "abstract:unknown_c1"}, "reviewers.", "provenance"),
    ({"source_record_id": "wrong-record"}, "reviewers.", "provenance"),
])
def test_verification_checks_exact_quote_and_location(change, quote, expected):
    paper, = consolidate([openalex_record()])
    chunk, = build_corpus([paper], {paper.id}, {})
    location = EvidenceLocation.model_validate({**chunk.model_dump(), **change})
    failure = verify_excerpt(location, quote, chunk)
    assert expected in failure if expected else failure == ""
    assert "outside" in verify_excerpt(location, quote, None)


def test_mixed_evidence_and_cross_paper_selection_rejection():
    papers = consolidate([openalex_record(),
                          SourceRecord(source="crossref", native_id="pdf", title="Screening PDF study")])
    abstract, pdf = papers
    chunks = build_corpus(papers, {p.id for p in papers}, {pdf.id: ["", "PDF screening used independent reviewers."]})
    abstract_chunk, pdf_chunk = chunks

    class MixedSelections(Structured):
        def Extraction(self, prompt):
            assert "[PAGE" not in prompt and "supporting_quote" not in prompt
            options = json.loads(prompt.split("\nCandidates: ", 1)[1])
            first, last = options[0], options[-1]
            return {"selections": [
                {"chunk_id": "unknown", "candidate_id": first["candidate_id"]},
                {"chunk_id": pdf_chunk.chunk_id, "candidate_id": first["candidate_id"]},
                {"chunk_id": pdf_chunk.chunk_id, "candidate_id": 999},
                {"chunk_id": abstract_chunk.chunk_id, "candidate_id": first["candidate_id"]},
                {"chunk_id": pdf_chunk.chunk_id, "candidate_id": last["candidate_id"]},
            ]}

    class MixedModel(ControlledModel):
        def with_structured_output(self, schema):
            return MixedSelections(self, schema)

    corpus = {chunk.chunk_id: chunk for chunk in chunks}
    evidence, audit = extract_passages("How was screening evaluated?", "RQ1", [],
                                       [chunk.model_dump() for chunk in chunks], corpus, MixedModel(), [])
    assert [(p.paper_id, p.source_type, p.page) for p in evidence] == [
        (abstract.id, "abstract", None), (pdf.id, "full_text", 2),
    ]
    assert evidence[1].quote == "PDF screening used independent reviewers."
    assert audit.verified_count == 2 and audit.status == "verified"
    assert len(audit.rejections) == 3
    assert ["not retrieved" in audit.rejections[0], "does not belong" in audit.rejections[1],
            "not offered" in audit.rejections[2]] == [True, True, True]


def test_malformed_selection_is_audited_and_produces_no_evidence():
    paper, = consolidate([openalex_record()])
    chunk, = build_corpus([paper], {paper.id}, {})

    class Malformed(Structured):
        def Extraction(self, prompt):
            return {"selections": [{"chunk_id": chunk.chunk_id, "candidate_id": "1"}]}

    class MalformedModel(ControlledModel):
        def with_structured_output(self, schema):
            return Malformed(self, schema)

    evidence, audit = extract_passages("screening", "RQ1", [], [chunk.model_dump()], {chunk.chunk_id: chunk},
                                       MalformedModel(), [])
    assert not evidence and audit.verified_count == 0 and audit.status == "invalid_response"
