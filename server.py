from fastapi import FastAPI
from fastmcp import FastMCP

# Create FastAPI app
app = FastAPI()

# Create MCP server
mcp = FastMCP("Gen OS Memory")

# Normal root route for Railway/browser health checks
@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Gen OS MCP wrapper online"
    }

# Mount MCP at /mcp
app.mount("/mcp", mcp.streamable_http_app())