import os
from fastapi import FastAPI
from fastmcp import FastMCP

# --- Create MCP server ---
mcp = FastMCP("Gen OS Memory")

# --- Create FastAPI app ---
app = FastAPI()

# Health check (Railway requires this)
@app.get("/")
async def root():
    return {"status": "ok", "service": "Gen OS MCP"}

# Mount MCP at /mcp
app.mount("/mcp", mcp.app)

# --- IMPORTANT: Run using Railway's dynamic port ---
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )