from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import Callable, Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response
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

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "blockbuster-premiere-rush")
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
EXTERNAL_API_FAILURE_RATE = float(os.getenv("EXTERNAL_API_FAILURE_RATE", "0.05"))


# ---------------------------------------------------------------------------
# Exceptions de resiliência (API externa simulada)
# ---------------------------------------------------------------------------
class ExternalServiceError(Exception):
    """Falha interna na API externa / banco simulado."""


class ExternalServiceUnavailable(Exception):
    """API externa temporariamente indisponível."""


# ---------------------------------------------------------------------------
# Logs JSON estritos com trace_id / span_id (correlação Loki ↔ Tempo)
# ---------------------------------------------------------------------------
class StrictJsonFormatter(logging.Formatter):
    """Formata 100% das linhas de log em JSON estrito."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": SERVICE_NAME,
        }

        span = trace.get_current_span()
        ctx = span.get_span_context() if span is not None else None
        if ctx is not None and ctx.is_valid:
            payload["trace_id"] = format(ctx.trace_id, "032x")
            payload["span_id"] = format(ctx.span_id, "016x")
        else:
            payload["trace_id"] = getattr(record, "otelTraceID", "") or ""
            payload["span_id"] = getattr(record, "otelSpanID", "") or ""

        for key in (
            "user_id",
            "movie_id",
            "authorized",
            "resolution",
            "server_region",
            "error_type",
            "http_status",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


class TraceContextFilter(logging.Filter):
    """Garante injeção automática de trace_id/span_id em todo LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        span = trace.get_current_span()
        ctx = span.get_span_context() if span is not None else None
        if ctx is not None and ctx.is_valid:
            record.otelTraceID = format(ctx.trace_id, "032x")
            record.otelSpanID = format(ctx.span_id, "016x")
        else:
            record.otelTraceID = getattr(record, "otelTraceID", "") or ""
            record.otelSpanID = getattr(record, "otelSpanID", "") or ""
        return True


def _try_configure_otlp_logging(resource: Resource) -> Optional[logging.Handler]:
    """Configura LoggingHandler OTel → OTLP (Loki). Retorna None se indisponível."""
    try:
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    except ImportError:
        return None

    logger_provider = LoggerProvider(resource=resource)
    set_logger_provider(logger_provider)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=OTLP_ENDPOINT, insecure=True))
    )
    handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
    handler.addFilter(TraceContextFilter())
    return handler


def configure_logging() -> logging.Logger:
    resource = Resource.create({"service.name": SERVICE_NAME})

    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(StrictJsonFormatter())
    stdout_handler.addFilter(TraceContextFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(stdout_handler)

    otel_handler = _try_configure_otlp_logging(resource)
    if otel_handler is not None:
        root.addHandler(otel_handler)

    root.setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    return logging.getLogger(SERVICE_NAME)


def configure_tracing() -> None:
    resource = Resource.create({"service.name": SERVICE_NAME})
    provider = TracerProvider(resource=resource)

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True))
        )
    except Exception:
        # Ambiente local sem coletor OTLP: tracing in-process continua ativo
        pass

    trace.set_tracer_provider(provider)


logger = configure_logging()
configure_tracing()
tracer = trace.get_tracer(SERVICE_NAME)


# ---------------------------------------------------------------------------
# Métricas RED (Rate, Errors, Duration/p95) — Prometheus
# ---------------------------------------------------------------------------
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total de requisições HTTP (Rate / RPS)",
    ["method", "endpoint", "status_code"],
)
REQUEST_ERRORS = Counter(
    "http_request_errors_total",
    "Total de requisições HTTP com erro (Errors)",
    ["method", "endpoint", "status_code"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "Duração das requisições HTTP em segundos (Latency / p95)",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


# ---------------------------------------------------------------------------
# Simulação de dependência externa (DRM / catálogo)
# ---------------------------------------------------------------------------
def call_external_authorization_api(user_id: str, movie_id: str) -> dict:
    """Simula chamada a API externa/banco com falhas controladas."""
    with tracer.start_as_current_span("external.authorization_api") as span:
        span.set_attribute("user_id", user_id)
        span.set_attribute("movie_id", movie_id)

        time.sleep(random.uniform(0.01, 0.05))

        roll = random.random()
        if roll < EXTERNAL_API_FAILURE_RATE * 0.4:
            span.set_attribute("error", True)
            raise ExternalServiceUnavailable(
                "Serviço de DRM/catálogo temporariamente indisponível"
            )
        if roll < EXTERNAL_API_FAILURE_RATE:
            span.set_attribute("error", True)
            raise ExternalServiceError("Falha interna ao consultar autorização externa")

        return {
            "user_id": user_id,
            "movie_id": movie_id,
            "authorized": True,
            "resolution": "4K",
            "drm_token": "eyJhbGciOiJIUzI1NiIsInR5c...",
            "server_region": "sa-east-1",
        }


# ---------------------------------------------------------------------------
# App FastAPI
# ---------------------------------------------------------------------------
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

    try:
        response = await call_next(request)
    except Exception:
        duration = time.perf_counter() - start
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code="500").inc()
        REQUEST_ERRORS.labels(method=method, endpoint=endpoint, status_code="500").inc()
        REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)
        raise

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
            "GET /metrics": "Métricas Prometheus (RED: Rate, Errors, Duration/p95)",
            "GET /docs": "Documentação interativa (Swagger UI)",
        },
    }


@app.get("/stream/authorize")
def authorize_stream(
    user_id: str = Query(..., description="Identificador do usuário"),
    movie_id: str = Query(..., description="Identificador do filme"),
):
    """
    Autoriza o streaming consultando API externa simulada.
    Em falha, retorna 500/503 controlados sem derrubar o processo.
    """
    try:
        decision = call_external_authorization_api(user_id, movie_id)
    except ExternalServiceUnavailable as exc:
        logger.error(
            "API externa indisponível durante autorização",
            extra={
                "user_id": user_id,
                "movie_id": movie_id,
                "error_type": "ExternalServiceUnavailable",
                "http_status": 503,
            },
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_unavailable",
                "message": str(exc),
                "user_id": user_id,
                "movie_id": movie_id,
            },
        ) from exc
    except ExternalServiceError as exc:
        logger.error(
            "Erro interno na API externa durante autorização",
            extra={
                "user_id": user_id,
                "movie_id": movie_id,
                "error_type": "ExternalServiceError",
                "http_status": 500,
            },
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": str(exc),
                "user_id": user_id,
                "movie_id": movie_id,
            },
        ) from exc
    except Exception as exc:
        logger.exception(
            "Falha inesperada na autorização de streaming",
            extra={
                "user_id": user_id,
                "movie_id": movie_id,
                "error_type": type(exc).__name__,
                "http_status": 500,
            },
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "unexpected_error",
                "message": "Erro inesperado ao processar autorização",
                "user_id": user_id,
                "movie_id": movie_id,
            },
        ) from exc

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
    """Expõe métricas Prometheus (Rate, Errors, Duration) para dashboards Grafana."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


FastAPIInstrumentor.instrument_app(app, excluded_urls="metrics")
