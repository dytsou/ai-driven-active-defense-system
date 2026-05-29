from fastapi import FastAPI

app = FastAPI(title="Active Defense")


@app.get("/health")
def health():
    return {"status": "ok"}
