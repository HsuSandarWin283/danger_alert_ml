import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from .predict_sound import predict, predict_with_debug

app = FastAPI(title="Danger Sound Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _save_upload(file: UploadFile) -> str:
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    allowed_suffixes = {".wav", ".mp3", ".ogg", ".flac", ".webm", ".m4a"}

    if suffix.lower() not in allowed_suffixes:
        raise HTTPException(status_code=400, detail="Unsupported audio format")

    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        with tmp:
            tmp.write(file.file.read())
        return tmp.name
    except Exception:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        raise


@app.post("/predict")
async def predict_sound(file: UploadFile = File(...)):
    tmp_path = None

    try:
        tmp_path = _save_upload(file)
        result = predict(tmp_path)
        print(f"[predict] filename={file.filename} result={result}")
        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as exc:
        print(f"[predict] error filename={file.filename} error={exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/debug-predict")
async def debug_predict(file: UploadFile = File(...)):
    tmp_path = None

    try:
        tmp_path = _save_upload(file)
        result = predict_with_debug(tmp_path)
        print(f"[debug-predict] filename={file.filename} result={result}")

        return {
            "filename": file.filename,
            "sample_rate": result["audio_info"]["sample_rate"],
            "channels": result["audio_info"]["channels"],
            "duration": result["audio_info"]["duration"],
            "feature_shape": result["feature_shape"],
            "class_probabilities": result["class_probabilities"],
            "predicted_class": result["predicted_class"],
            "confidence": result["confidence"],
            "model_classes": result["model_classes"],
            "model_sample_rate": result["model_sample_rate"],
            "feature_version": result["feature_version"],
            "model_feature_version": result["model_feature_version"],
            "warnings": result["warnings"],
        }

    except HTTPException:
        raise
    except Exception as exc:
        print(f"[debug-predict] error filename={file.filename} error={exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
