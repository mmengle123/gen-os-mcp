from fastapi import FastAPI
from fastmcp import FastMCP

mcp = FastMCP("Gen OS Memory")

# Create the MCP ASGI app
mcp_app = mcp.http_app(path="/mcp")

# Important: pass lifespan
app = FastAPI(
    title="Gen OS MCP",
    lifespan=mcp_app.lifespan,
)

@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "Gen OS MCP",
        "message": "MCP wrapper online"
    }

# Mount MCP
app.mount("/", mcp_app)