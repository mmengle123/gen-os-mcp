from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "plain fastapi test is alive"
    }