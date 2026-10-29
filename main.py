from fastapi import FastAPI, Query, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

app = FastAPI(
    title="Blockbuster Premiere Rush",
    description="Serviço HTTP de autorização de streaming - Desafio Observabilidade B3",
    version="1.0.0",
)


@app.get("/stream/authorize")
def authorize_stream(
    user_id: str = Query(..., description="Identificador do usuário"),
    movie_id: str = Query(..., description="Identificador do filme"),
):
    """Autoriza o streaming e retorna resolução, DRM token e região do servidor."""
    return {
        "user_id": user_id,
        "movie_id": movie_id,
        "authorized": True,
        "resolution": "4K",
        "drm_token": "eyJhbGciOiJIUzI1NiIsInR5c...",
        "server_region": "sa-east-1",
    }


@app.get("/metrics")
def metrics():
    """Expõe métricas no formato Prometheus (RED: Rate, Errors, Duration)."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
