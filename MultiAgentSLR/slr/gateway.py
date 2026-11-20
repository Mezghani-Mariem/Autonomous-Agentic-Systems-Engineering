from time import perf_counter, sleep

import httpx
from langchain_core.messages import AIMessage, HumanMessage
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama, OllamaEmbeddings
from pydantic import ValidationError

from .models import Event
from .storage import digest


class GatewayError(RuntimeError):
    """A provider or request reported a failure without exposing secrets."""


class InvalidModelOutput(GatewayError):
    pass


class Telemetry:
    def __init__(self, events=None, *, record_prompts=False):
        self.events = events if events is not None else []
        self.stage = "setup"
        self.prompts = [] if record_prompts else None

    def event(self, kind, operation, status, started, **kwargs):
        self.events.append(Event(stage=self.stage, kind=kind, operation=operation,
                                 status=status, seconds=perf_counter() - started, **kwargs))


class Calls:
    def __init__(self, store, telemetry, ttl):
        self.store, self.telemetry, self.ttl = store, telemetry, ttl

    def use(self, kind, operation, identity, fetch, *, retries=0, validator=None, tokens=False):
        started = perf_counter()
        key = digest(["slr-cache-v1", kind, operation, identity])
        hit = self.store.cache_get(key) if self.ttl else None
        if hit is not None:
            self.telemetry.event(kind, operation, "cache_hit", started)
            return validator(hit) if validator else hit
        for attempt in range(retries + 1):
            started = perf_counter()
            try:
                value = fetch()
                result = validator(value) if validator else value
            except Exception as exc:
                status = status_code(exc)
                message = f"HTTP {status}" if status else type(exc).__name__
                self.telemetry.event(kind, operation, "error", started, retry=attempt > 0, detail=message)
                retryable = (status in {429, 500, 502, 503, 504} or isinstance(exc, httpx.TransportError)
                             or isinstance(exc.__cause__, httpx.TransportError))
                if attempt < retries and retryable:
                    delay = retry_delay(exc)
                    if delay <= 3:
                        sleep(delay)
                        continue
                if isinstance(exc, (InvalidModelOutput, ValidationError, ValueError)) and kind == "llm":
                    raise InvalidModelOutput(f"{operation} returned an invalid response") from None
                raise GatewayError(f"{operation} failed ({message})") from None
            self.store.cache_put(key, value, self.ttl)
            usage = value.get("usage", {}) if tokens else {}
            self.telemetry.event(kind, operation, "ok", started, retry=attempt > 0,
                                 input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"))
            return result


def status_code(exc):
    status = getattr(exc, "status_code", None)
    return status or getattr(getattr(exc, "response", None), "status_code", None)


def retry_delay(exc):
    headers = getattr(getattr(exc, "response", None), "headers", {})
    value = headers.get("retry-after")
    if value is None:
        return 0.25
    try:
        return max(0, float(value))
    except ValueError:
        return float("inf")


def message_data(prompt):
    if isinstance(prompt, str):
        return prompt
    return [message.model_dump(mode="json") for message in prompt]


class StructuredCall:
    def __init__(self, model, schema):
        self.model, self.schema = model, schema

    def invoke(self, prompt):
        return self.model.structured(prompt, self.schema)


class MeasuredModel:
    def __init__(self, backend, provider, model_name, calls, endpoint=""):
        self.backend, self.provider, self.name, self.calls = backend, provider, model_name, calls
        self.identity = [provider, model_name, endpoint, 0]

    def _capture(self, operation, prompt, schema=None):
        if self.calls.telemetry.prompts is not None:
            self.calls.telemetry.prompts.append({
                "model": self.name, "provider": self.provider, "operation": operation,
                "messages": message_data(prompt), "schema": schema,
            })

    def invoke(self, prompt):
        self._capture("invoke", prompt)
        def fetch():
            response = self.backend.invoke(prompt)
            return {"message": response.model_dump(mode="json"), "usage": response.usage_metadata or {}}
        return self.calls.use("llm", f"{self.provider}:{self.name}/invoke",
                              [self.identity, message_data(prompt)], fetch, retries=1,
                              validator=lambda x: AIMessage.model_validate(x["message"]), tokens=True)

    def with_structured_output(self, schema):
        return StructuredCall(self, schema)

    def structured(self, prompt, schema):
        definition = schema.model_json_schema()
        if self.provider == "groq":
            import json
            instruction = "Return one JSON object matching this schema: " + json.dumps(definition, ensure_ascii=False)
            messages = [HumanMessage(content=prompt)] if isinstance(prompt, str) else list(prompt)
            messages.append(HumanMessage(content=instruction))
        else:
            messages = prompt
        self._capture(schema.__name__, messages, definition)

        def fetch():
            method = "json_mode" if self.provider == "groq" else "json_schema"
            output = self.backend.with_structured_output(schema, method=method, include_raw=True).invoke(messages)
            if output["parsing_error"] or output["parsed"] is None:
                raise InvalidModelOutput(f"Invalid {schema.__name__}")
            parsed = schema.model_validate(output["parsed"])
            usage = getattr(output["raw"], "usage_metadata", None) or {}
            return {"parsed": parsed.model_dump(mode="json"), "usage": usage}

        return self.calls.use("llm", f"{self.provider}:{self.name}/{schema.__name__}",
                              [self.identity, message_data(messages), definition], fetch, retries=1,
                              validator=lambda x: schema.model_validate(x["parsed"]), tokens=True)


def build_model(settings, provider, calls):
    if provider == "groq":
        if not settings.groq_key:
            raise GatewayError("Set GROQ_API_KEY before starting a Groq review.")
        backend = ChatGroq(model=settings.groq_model, api_key=settings.groq_key, temperature=0,
                           timeout=settings.timeout, max_retries=0)
        return MeasuredModel(backend, provider, settings.groq_model, calls)
    if provider == "ollama":
        backend = ChatOllama(model=settings.ollama_model, base_url=settings.ollama_url, temperature=0,
                             client_kwargs={"timeout": settings.timeout})
        return MeasuredModel(backend, provider, settings.ollama_model, calls, settings.ollama_url)
    raise ValueError("Unknown model provider")


class MeasuredEmbeddings:
    def __init__(self, settings, calls):
        self.backend = OllamaEmbeddings(model=settings.embedding_model, base_url=settings.ollama_url,
                                       client_kwargs={"timeout": settings.timeout})
        self.identity = [settings.ollama_url, settings.embedding_model]
        self.calls = calls

    def embed_query(self, query):
        return self.calls.use("embedding", "ollama:query", [self.identity, query],
                              lambda: self.backend.embed_query(query))

    def embed_documents(self, texts):
        return self.calls.use("embedding", "ollama:documents", [self.identity, texts],
                              lambda: self.backend.embed_documents(texts))
