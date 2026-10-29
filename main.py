import json
import logging
import time
from typing import Callable

from fastapi import FastAPI, Query, Request, Response
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

SERVICE_NAME = "blockbuster-premiere-rush"


# ---------------------------------------------------------------------------
# Logs da aplicação em JSON simples (trace_id / span_id quando disponíveis)
# ---------------------------------------------------------------------------
class SimpleJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None
        if ctx and ctx.is_valid:
            payload["trace_id"] = format(ctx.trace_id, "032x")
            payload["span_id"] = format(ctx.span_id, "016x")

        for key in ("user_id", "movie_id", "authorized", "resolution", "server_region"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> logging.Logger:
    handler = logging.StreamHandler()
    handler.setFormatter(SimpleJsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Mantém o access log do Uvicorn legível, sem misturar no JSON da app
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    return logging.getLogger(SERVICE_NAME)


logger = configure_logging()


# ---------------------------------------------------------------------------
# Tracing OpenTelemetry (sem exporter de console — evita ruído nos logs)
# ---------------------------------------------------------------------------
def configure_tracing() -> None:
    resource = Resource.create({"service.name": SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)


configure_tracing()


# ---------------------------------------------------------------------------
# Métricas RED (Rate, Errors, Duration)
# ---------------------------------------------------------------------------
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total de requisições HTTP (Rate)",
    ["method", "endpoint", "status_code"],
)
REQUEST_ERRORS = Counter(
    "http_request_errors_total",
    "Total de requisições HTTP com erro (Errors)",
    ["method", "endpoint", "status_code"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "Duração das requisições HTTP em segundos (Duration)",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


app = FastAPI(
    title="Blockbuster Premiere Rush",
    description="Serviço HTTP de autorização de streaming - Desafio Observabilidade B3",
    version="1.0.0",
)


@app.middleware("http")
async def red_metrics_middleware(request: Request, call_next: Callable):
    if request.url.path == "/metrics":
        return await call_next(request)

    method = request.method
    endpoint = request.url.path
    start = time.perf_counter()

    response = await call_next(request)

    duration = time.perf_counter() - start
    status_code = str(response.status_code)

    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
    REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)

    if response.status_code >= 400:
        REQUEST_ERRORS.labels(
            method=method, endpoint=endpoint, status_code=status_code
        ).inc()

    return response


@app.get("/")
def root():
    """Mensagem de boas-vindas com as rotas disponíveis."""
    return {
        "message": "Bem-vindo ao Blockbuster Premiere Rush!",
        "description": "Serviço de autorização de streaming — Desafio Observabilidade B3",
        "routes": {
            "GET /": "Esta mensagem de boas-vindas",
            "GET /stream/authorize": "Autorização de streaming (?user_id=&movie_id=)",
            "GET /metrics": "Métricas Prometheus (RED)",
            "GET /docs": "Documentação interativa (Swagger UI)",
        },
    }


@app.get("/stream/authorize")
def authorize_stream(
    user_id: str = Query(..., description="Identificador do usuário"),
    movie_id: str = Query(..., description="Identificador do filme"),
):
    """Autoriza o streaming e retorna resolução, DRM token e região do servidor."""
    decision = {
        "user_id": user_id,
        "movie_id": movie_id,
        "authorized": True,
        "resolution": "4K",
        "drm_token": "eyJhbGciOiJIUzI1NiIsInR5c...",
        "server_region": "sa-east-1",
    }

    logger.info(
        "Decisão de autorização de streaming",
        extra={
            "user_id": user_id,
            "movie_id": movie_id,
            "authorized": decision["authorized"],
            "resolution": decision["resolution"],
            "server_region": decision["server_region"],
        },
    )

    return decision


@app.get("/metrics")
def metrics():
    """Expõe métricas no formato Prometheus (RED: Rate, Errors, Duration)."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


FastAPIInstrumentor.instrument_app(app, excluded_urls="metrics")
