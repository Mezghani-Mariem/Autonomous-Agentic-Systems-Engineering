import json

import pytest
from langchain_core.messages import AIMessage

from evaluation.benchmarks import dataset, records_from_course
from slr.models import ReviewConfig, SOURCES

TOPIC = "Large language models for title and abstract screening in systematic literature reviews"


class CourseSnapshot:
    def __init__(self, missing_abstract=False):
        rows = records_from_course(dataset("screening_snapshot.json")["papers"])
        self.record = next(row for row in rows if "screening" in row.abstract.lower())
        if missing_abstract:
            self.record = self.record.model_copy(update={"abstract": ""})

    def search(self, source, query, limit):
        return [self.record] if self.record.source == source else []


class ControlledModel:
    def __init__(self, *, first_invalid=False, invalid_citation=False, reject_claim=False):
        self.first_invalid = first_invalid
        self.invalid_citation = invalid_citation
        self.reject_claim = reject_claim
        self.raw_calls = 0
        self.writer_calls = 0

    def invoke(self, prompt):
        self.raw_calls += 1
        return AIMessage(content="Invalid" if self.first_invalid and self.raw_calls == 1 else (
            "RQ1. What screening outcomes are reported in the studies?\n"
            "RQ2. How were screening methods evaluated in the studies?\n"
            "RQ3. What limitations affect screening in the studies?"
        ))

    def with_structured_output(self, schema):
        return Structured(self, schema)


class Structured:
    def __init__(self, model, schema):
        self.model, self.schema = model, schema

    def invoke(self, prompt):
        return self.schema.model_validate(getattr(self, self.schema.__name__)(prompt))

    def ProtocolProposal(self, prompt):
        return {
            "queries": {source: "large language models systematic review screening" for source in SOURCES},
            "questions": [
                {"rq_id": f"RQ{i}", "terms": ["screening"], "facets": [
                    {"id": "screening", "label": "Screening practices", "keywords": ["screening"],
                     "query_hint": "systematic review screening"}
                ]} for i in range(1, 4)
            ],
            "include_signals": ["screening"], "exclude_signals": ["clinical trial"],
        }

    def LLMScreeningDecision(self, messages):
        abstract = str(messages[-1].content).partition("Résumé : ")[2]
        return {"paper_id": "input-controlled", "decision": "include", "confidence": 0.95,
                "reasons": ["The abstract refers to screening."],
                "evidence": " ".join(abstract.split()[:18]),
                "needs_human_review": False}

    def Extraction(self, prompt):
        options = json.loads(prompt.split("\nCandidates: ", 1)[1])
        return {"selections": [{"chunk_id": item["chunk_id"], "candidate_id": item["candidate_id"]}
                               for item in options[:1]]}

    def ClaimProposal(self, prompt):
        self.model.writer_calls += 1
        evidence = json.loads(prompt.split("Verified excerpts: ", 1)[1].split("\nPrevious draft:", 1)[0])
        claims = [{"id": e["rq_id"], "rq_id": e["rq_id"], "text": e["quote"], "evidence_ids": [e["id"]]}
                  for e in evidence]
        if self.model.invalid_citation and self.model.writer_calls == 1:
            claims[0]["evidence_ids"] = ["UNKNOWN"]
        return {"claims": claims}

    def JudgeResponse(self, prompt):
        claims = json.loads(prompt.split("Items: ", 1)[1])
        return {"findings": [
            {"claim_id": item["claim_id"], "judgment": "unsupported" if self.model.reject_claim else "supported",
             "reason": "Scripted response for the test."} for item in claims
        ]}


@pytest.fixture
def config():
    return ReviewConfig(topic=TOPIC, per_source=1)
