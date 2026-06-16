import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from .predict_sound import predict

app = FastAPI(title="Danger Sound Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/predict")
async def predict_sound(file: UploadFile = File(...)):
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"

    if suffix.lower() not in {".wav", ".mp3", ".ogg", ".flac"}:
        raise HTTPException(status_code=400, detail="Unsupported audio format")

    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            await file.seek(0)
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        result = predict(tmp_path)

        return JSONResponse(content=result)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
