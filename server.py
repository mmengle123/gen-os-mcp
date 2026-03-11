import os
import uvicorn
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def health():
    return {"status": "ok", "service": "Gen OS MCP"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)