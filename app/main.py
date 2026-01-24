from fastapi import FastAPI
from app.lifespan import lifespan
from app.whatsapp import router as whatsapp_router

app = FastAPI(lifespan=lifespan)

@app.get("/")
def health():
    return {"status": "ok"}

app.include_router(whatsapp_router)
