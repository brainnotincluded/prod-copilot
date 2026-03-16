"""Mock MLOps service — runs locally, no torch/transformers needed.

Responds to all endpoints the backend expects with realistic fake data.
Start: python mock_mlops.py  (runs on port 8001)
"""

import json
import random

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

app = FastAPI(title="Mock MLOps", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "service": "mock-mlops", "version": "0.1.0"}


# ---------------------------------------------------------------------------
# POST /api/translate — just echo back
# ---------------------------------------------------------------------------

@app.post("/api/translate")
async def translate(request: Request):
    body = await request.json()
    query = body.get("query", "")
    return {"translated": query, "source_lang": "ru", "target_lang": "en"}


# ---------------------------------------------------------------------------
# POST /api/embeddings — random 384-dim vectors
# ---------------------------------------------------------------------------

@app.post("/api/embeddings")
async def embeddings(request: Request):
    body = await request.json()
    texts = body.get("texts", [])
    # 384-dim like all-MiniLM-L6-v2
    vecs = []
    for _ in texts:
        vec = [random.gauss(0, 0.1) for _ in range(384)]
        norm = sum(v * v for v in vec) ** 0.5
        vecs.append([v / norm for v in vec])
    return {"embeddings": vecs}


# ---------------------------------------------------------------------------
# POST /api/orchestrate — sync orchestration
# ---------------------------------------------------------------------------

@app.post("/api/orchestrate")
async def orchestrate(request: Request):
    body = await request.json()
    query = body.get("query", "")
    endpoints = body.get("endpoints", [])

    # Pick relevant endpoints (top 3)
    chosen = endpoints[:3] if endpoints else []

    steps = []
    for i, ep in enumerate(chosen, 1):
        steps.append({
            "step": i,
            "action": "api_call",
            "description": f"{ep.get('method', 'GET')} {ep.get('path', '/')} — {ep.get('summary', 'call')}",
            "status": "completed",
            "result": {
                "status_code": 200,
                "sample": {"id": i, "name": f"item_{i}", "value": random.randint(100, 9999)},
            },
        })

    return {
        "type": "text",
        "data": {
            "content": f"Выполнено {len(steps)} шагов для запроса: '{query}'. "
                       f"Использовано {len(chosen)} из {len(endpoints)} доступных эндпоинтов.",
            "steps": steps,
        },
        "metadata": {
            "total_steps": len(steps),
            "duration_ms": random.randint(200, 2000),
            "endpoints_used": len(chosen),
        },
    }


# ---------------------------------------------------------------------------
# POST /api/orchestrate/stream — SSE streaming
# ---------------------------------------------------------------------------

@app.post("/api/orchestrate/stream")
async def orchestrate_stream(request: Request):
    body = await request.json()
    query = body.get("query", "")
    endpoints = body.get("endpoints", [])

    async def event_generator():
        chosen = endpoints[:5] if endpoints else []

        # 1. Plan event
        plan_steps = []
        for i, ep in enumerate(chosen, 1):
            plan_steps.append({
                "step": i,
                "action": "api_call",
                "endpoint": f"{ep.get('method', 'GET')} {ep.get('path', '/')}",
                "description": ep.get("summary", "API call"),
            })

        yield f"event: plan\ndata: {json.dumps({'steps': plan_steps, 'total': len(plan_steps)})}\n\n"

        # 2. Execute each step
        for i, ep in enumerate(chosen, 1):
            method = ep.get("method", "GET")
            path = ep.get("path", "/")
            summary = ep.get("summary", "API call")

            # step_start
            yield f"event: step_start\ndata: {json.dumps({'step': i, 'action': 'api_call', 'description': f'{method} {path} — {summary}'})}\n\n"

            # step_complete
            result = {
                "status_code": 200,
                "data": {"id": i, "name": f"item_{i}", "value": random.randint(100, 9999)},
            }
            yield f"event: step_complete\ndata: {json.dumps({'step': i, 'action': 'api_call', 'description': f'{method} {path}', 'result': result})}\n\n"

        # 3. Final result
        result_data = {
            "type": "text",
            "data": {
                "content": f"Выполнено {len(chosen)} шагов для: '{query}'.",
            },
            "metadata": {
                "total_steps": len(chosen),
                "duration_ms": random.randint(200, 2000),
            },
        }
        yield f"event: result\ndata: {json.dumps(result_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# GET /api/sandbox/files/{session_id}/{filename} — stub
# ---------------------------------------------------------------------------

@app.get("/api/sandbox/files/{session_id}/{filename}")
async def sandbox_file(session_id: str, filename: str):
    return {"error": "Mock MLOps: no sandbox files available"}


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    print("Mock MLOps starting on http://localhost:8001")
    print("Endpoints: /health, /api/translate, /api/embeddings, /api/orchestrate, /api/orchestrate/stream")
    uvicorn.run(app, host="0.0.0.0", port=8001)
