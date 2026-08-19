from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import tempfile
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app", "ml"))

from predict_sound import load_model, predict, predict_with_debug

app = FastAPI(title="Danger Sound Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_DIR = Path(__file__).resolve().parent
YAMNET_MODEL_DIR = MODEL_DIR / "yamnet_model"
YAMNET_MODEL_PATH = MODEL_DIR / "yamnet_classifier.pkl"

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

@app.on_event("startup")
async def startup():
    try:
        load_model()
        print("Model loaded successfully")
    except Exception as exc:
        print(f"Model load failed: {exc}")

@app.post("/predict")
async def predict_sound(file: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        result = predict(tmp_path)
        os.unlink(tmp_path)
        return JSONResponse(content=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
