from fastapi import FastAPI

app = FastAPI(title="TransmiApp API")


@app.get("/api/salud")
def salud():
    return {"ok": True}
