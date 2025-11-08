from fastapi import FastAPI
app = FastAPI(title="Setu API")

@app.get("/")
def read_root():
    return {"service": "Setu API", "status": "running"}