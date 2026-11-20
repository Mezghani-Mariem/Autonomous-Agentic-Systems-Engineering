import re
import unicodedata
from collections import defaultdict
from functools import partial
from urllib.parse import unquote
from html import unescape

import httpx

from .course.react_agent import run_react_agent
from .course.tools import SearchTool, ToolRegistry
from .course.workflow import run_tool_workflow
from .gateway import GatewayError
from .models import SOURCES, SearchBatch, SourceRecord, Study
from .storage import digest

ENDPOINTS = {
    "openalex": "https://api.openalex.org/works",
    "semantic_scholar": "https://api.semanticscholar.org/graph/v1/paper/search",
    "crossref": "https://api.crossref.org/works",
}


def clean_text(text):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", text or "")).split())


def normalize_doi(doi):
    return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "",
                  unquote(doi or "").strip().casefold())


def normalize_openalex(item):
    positions = [(position, word) for word, indexes in (item.get("abstract_inverted_index") or {}).items()
                 for position in indexes]
    location = item.get("primary_location") or {}
    return {
        "native_id": (item.get("id") or "").rsplit("/", 1)[-1],
        "title": item.get("display_name") or item.get("title"),
        "abstract": " ".join(word for _, word in sorted(positions)),
        "doi": item.get("doi"),
        "url": location.get("landing_page_url") or item.get("id"),
        "authors": [(a.get("author") or {}).get("display_name") for a in item.get("authorships", [])],
        "year": item.get("publication_year"),
        "open_access": (item.get("open_access") or {}).get("is_oa"),
    }


def normalize_semantic(item):
    return {
        "native_id": item.get("paperId"), "title": item.get("title"),
        "abstract": item.get("abstract"), "doi": (item.get("externalIds") or {}).get("DOI"),
        "url": item.get("url"), "authors": [a.get("name") for a in item.get("authors") or []],
        "year": item.get("year"), "open_access": item.get("isOpenAccess"),
    }


def normalize_crossref(item):
    date = item.get("published") or item.get("issued") or {}
    year = next(iter((date.get("date-parts") or [[]])[0]), None)
    return {
        "native_id": item.get("DOI") or item.get("URL"), "title": (item.get("title") or [""])[0],
        "abstract": item.get("abstract"), "doi": item.get("DOI"), "url": item.get("URL"),
        "authors": [" ".join(filter(None, (a.get("given"), a.get("family")))) or a.get("name")
                    for a in item.get("author") or []],
        "year": year, "open_access": None,
    }


def normalize_rows(source, rows, mapper):
    if not isinstance(rows, list):
        raise ValueError("Expected a list of works")
    result = []
    for item in rows:
        row = mapper(item)
        title = clean_text(row["title"])
        if not row["native_id"] or not title:
            continue
        record = SourceRecord(source=source, native_id=row["native_id"], title=title,
                              abstract=clean_text(row["abstract"]), doi=normalize_doi(row["doi"]),
                              url=row["url"] or "", authors=[a for a in row["authors"] if a],
                              year=row["year"], open_access=row["open_access"])
        result.append(record.model_dump(mode="json"))
    return result


class ScientificSources:
    def __init__(self, settings, calls, client):
        self.settings, self.calls, self.client = settings, calls, client

    def search(self, source, query, limit):
        url = ENDPOINTS[source]
        if source == "openalex":
            params = {"search": query, "per-page": limit}
            headers = ({"Authorization": f"Bearer {self.settings.openalex_key}"}
                       if self.settings.openalex_key else {})
            rows = lambda data: data["results"]
            mapper = normalize_openalex
        elif source == "semantic_scholar":
            params = {"query": query, "limit": limit,
                      "fields": "title,abstract,externalIds,url,authors,year,isOpenAccess"}
            headers = ({"x-api-key": self.settings.semantic_key} if self.settings.semantic_key else {})
            rows = lambda data: data.get("data", []) if data.get("total") == 0 else data["data"]
            mapper = normalize_semantic
        else:
            params = {"query.bibliographic": query, "rows": limit}
            if self.settings.crossref_email:
                params["mailto"] = self.settings.crossref_email
            headers = {}
            rows = lambda data: data["message"]["items"]
            mapper = normalize_crossref

        def fetch():
            response = self.client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return normalize_rows(source, rows(response.json())[:limit], mapper)

        try:
            data = self.calls.use("api", source, [url, query, limit], fetch, retries=1)
        except GatewayError as exc:
            status = re.search(r"\(HTTP (\d+)\)$", str(exc))
            request = httpx.Request("GET", url)
            if status:
                response = httpx.Response(int(status[1]), request=request)
                raise httpx.HTTPStatusError(str(exc), request=request, response=response) from None
            raise httpx.RequestError(str(exc), request=request) from None
        return [SourceRecord.model_validate(row) for row in data]


def title_key(record):
    text = unicodedata.normalize("NFKC", record.title).casefold()
    return " ".join(re.findall(r"\w+", text))


def consolidate(records):
    doi_by_title = defaultdict(set)
    for record in records:
        if record.doi:
            doi_by_title[title_key(record)].add(record.doi)
    groups = defaultdict(list)
    for row in records:
        candidates = doi_by_title[title_key(row)]
        doi = row.doi or (next(iter(candidates)) if len(candidates) == 1 else "")
        key = f"doi:{doi}" if doi else f"title:{title_key(row)}:{row.year or ''}"
        if not doi and not title_key(row):
            key = f"{row.source}:{row.native_id}"
        groups[key].append(row)

    papers = []
    for key, rows in groups.items():
        rows = sorted(rows, key=lambda r: (SOURCES.index(r.source), r.native_id))
        abstract = max(rows, key=lambda r: len(r.abstract))
        authors = next((row.authors for row in rows if row.authors), [])
        year = next((row.year for row in rows if row.year is not None), None)
        doi = next((row.doi for row in rows if row.doi), "")
        url = f"https://doi.org/{doi}" if doi else next((row.url for row in rows if row.url), "")
        aliases = {(row.source, row.native_id): row for row in rows}
        papers.append(Study(id=f"P-{digest(key)[:16]}", title=abstract.title,
                            abstract=abstract.abstract, doi=doi, url=url, year=year, authors=authors,
                            abstract_source=abstract.source if abstract.abstract else None,
                            sources=list(aliases.values())))
    return papers


def react_policy(queries, limit):
    def decide(state, allowed):
        tried = {observation.tool for observation in state.observations}
        remaining = [source for source in allowed if source not in tried]
        if not remaining:
            return {"action": "finish"}
        # A throttled or empty first source triggers the public Crossref fallback.
        last = state.observations[-1] if state.observations else None
        if last and last.status != "success" and "crossref" in remaining:
            selected = "crossref"
        else:
            selected = remaining[0]
        return {"action": "search", "tool": selected, "query": queries[selected], "limit": limit}
    return decide


def search_review(topic, queries, limit, mode, source_gateway):
    records = []

    def adapter(source, query, cap):
        rows = source_gateway.search(source, query, cap)
        records.extend(rows)
        return [dict(id=row.native_id, title=row.title, abstract=row.abstract, doi=row.doi,
                     url=row.url, open_access=bool(row.open_access)) for row in rows]

    queries = {source: queries[source] for source in SOURCES}
    registry = ToolRegistry([SearchTool(source, partial(adapter, source)) for source in SOURCES])
    if mode == "react":
        state = run_react_agent(topic, queries, registry, react_policy(queries, limit),
                                max_steps=len(SOURCES) + 1, target_papers=len(SOURCES) * limit + 1)
    else:
        state = run_tool_workflow(topic, queries, registry, limit)
    papers = consolidate(records)
    return SearchBatch(papers=papers, discovered=len(records), duplicates=len(records) - len(papers), state=state)
