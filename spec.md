Markdown
# Spec - Blockbuster Premiere Rush (Backend & Observabilidade)

## 1. Visão Geral
Serviço HTTP de autorização de streaming desenvolvido em Python (FastAPI) para o desafio técnico de Observabilidade B3 (Cenário 2). O sistema decide a resolução de transmissão com base na carga simulada e injeta telemetria completa via OpenTelemetry.

## 2. Stack Tecnológica
- Linguagem/Framework: Python 3.10+ com FastAPI e Uvicorn.
- Instrumentação: OpenTelemetry (Metrics, Logs, Traces) com exportação Prometheus/OTLP.
- Resiliência: Tratamento de falhas para simular instabilidade em API externa ou banco de dados (retornando HTTP 500/503 controlado sem crashar).

## 3. Endpoints Obrigatórios
- `GET /stream/authorize?user_id={user_id}&movie_id={movie_id}`
  - **Resposta de Sucesso (200 OK):**
json
{
"user_id": "usr_99823",
"movie_id": "mov_dune_part2",
"authorized": true,
"resolution": "4K",
"drm_token": "eyJhbGciOiJIUzI1NiIsInR5c...",
"server_region": "sa-east-1"
}

- `GET /metrics`
- Exposição de métricas no formato Prometheus (RED: Rate, Errors, Duration).

## 4. Requisitos de Observabilidade
- **Logs estruturados em JSON** contendo o `trace_id` e `span_id` injetados automaticamente.
- **Tracing distribuído** capturando o ciclo de vida da requisição.