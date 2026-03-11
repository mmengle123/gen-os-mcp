import os
from fastapi import FastAPI
from fastmcp import FastMCP

# Create MCP server
mcp = FastMCP("Gen OS Memory")

# Create FastAPI app
app = FastAPI(title="Gen OS MCP")

# Mount MCP under /mcp
app.mount("/mcp", mcp.streamable_http_app())


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "Gen OS MCP",
        "message": "MCP wrapper online"
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/health_check")
async def health_check():
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{BRIDGE_BASE_URL}/")
        response.raise_for_status()
        return response.json()


@app.post("/load_gen_memory")
async def load_gen_memory():
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{BRIDGE_BASE_URL}/load_gen_memory", json={})
        response.raise_for_status()
        return response.json()


@app.post("/read_memory")
async def read_memory(request: Request):
    payload = await request.json()
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{BRIDGE_BASE_URL}/read_memory", json=payload)
        response.raise_for_status()
        return response.json()


@app.post("/query_memory")
async def query_memory(request: Request):
    payload = await request.json()
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{BRIDGE_BASE_URL}/query_memory", json=payload)
        response.raise_for_status()
        return response.json()


@app.post("/append_memory")
async def append_memory(request: Request):
    payload = await request.json()
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{BRIDGE_BASE_URL}/append_memory", json=payload)
        response.raise_for_status()
        return response.json()


@app.post("/replace_memory")
async def replace_memory(request: Request):
    payload = await request.json()
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{BRIDGE_BASE_URL}/replace_memory", json=payload)
        response.raise_for_status()
        return response.json()


@app.post("/log_reflection")
async def log_reflection(request: Request):
    payload = await request.json()
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{BRIDGE_BASE_URL}/log_reflection", json=payload)
        response.raise_for_status()
        return response.json()


@app.post("/log_learning")
async def log_learning(request: Request):
    payload = await request.json()
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{BRIDGE_BASE_URL}/log_learning", json=payload)
        response.raise_for_status()
        return response.json()