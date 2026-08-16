import gc
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app", "ml"))

from fastapi import FastAPI, File, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import shutil
import tempfile
import time
from pathlib import Path

from predict_sound import load_model, predict, predict_with_debug

logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, messaging
    _firebase_initialized = False

    def _init_firebase():
        global _firebase_initialized
        if _firebase_initialized:
            return
        sa_path = Path(__file__).resolve().parent / "app" / "ml" / "service-account.json"
        if sa_path.exists():
            cred = credentials.Certificate(str(sa_path))
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info("Firebase Admin initialized for emergency alerts")
        else:
            logger.warning("service-account.json not found — emergency alerts will fail")

    _init_firebase()

except Exception as exc:
    logger.warning("firebase-admin not available: %s", exc)

app = FastAPI(title="Danger Sound Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEBUG_AUDIO_DIR = Path(__file__).resolve().parent / "app" / "ml" / "debug_audio"
_model_loaded = False


@app.on_event("startup")
async def startup_load_model():
    global _model_loaded
    DEBUG_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    try:
        load_model()
        _model_loaded = True
        logger.info("Model loaded successfully at startup")
    except Exception as exc:
        logger.exception("Failed to load model at startup — /predict will return 503")


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


def _save_debug_audio(src_path: str, filename: str) -> str | None:
    try:
        ts = int(time.time() * 1000)
        safe_name = f"{ts}_{filename}"
        dst = str(DEBUG_AUDIO_DIR / safe_name)
        shutil.copy2(src_path, dst)
        logger.info("[debug-audio] saved %s (%d bytes)", dst, os.path.getsize(dst))
        return dst
    except Exception as exc:
        logger.warning("[debug-audio] failed to save: %s", exc)
        return None


@app.post("/predict")
async def predict_sound(file: UploadFile = File(...)):
    if not _model_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded yet. Try again later.")
    tmp_path = None

    try:
        tmp_path = _save_upload(file)

        _save_debug_audio(tmp_path, file.filename or "unknown.wav")

        result = predict(tmp_path)
        logger.info(
            "[predict] filename=%s prediction=%s confidence=%.4f probs=%s",
            file.filename,
            result["prediction"],
            result["confidence"],
            {k: f"{v:.4f}" for k, v in result.get("probabilities", {}).items()},
        )
        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("[predict] error filename=%s", file.filename)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        gc.collect()


@app.post("/debug-predict")
async def debug_predict(file: UploadFile = File(...)):
    if not _model_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded yet. Try again later.")
    tmp_path = None

    try:
        tmp_path = _save_upload(file)

        _save_debug_audio(tmp_path, file.filename or "unknown.wav")

        result = predict_with_debug(tmp_path)
        logger.info(
            "[debug-predict] filename=%s predicted_class=%s confidence=%.4f",
            file.filename,
            result["predicted_class"],
            result["confidence"],
        )

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
            "debug": result.get("debug", {}),
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("[debug-predict] error filename=%s", file.filename)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        gc.collect()


@app.get("/health")
async def health_check():
    if not _model_loaded:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "model_loaded": False, "detail": "Model not loaded yet"},
        )
    return {"status": "healthy", "model_loaded": True}


@app.post("/emergency-alert")
async def emergency_alert(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    sender_id = body.get("senderId")
    receiver_ids = body.get("receiverIds", [])
    sender_name = body.get("senderName", "")
    danger_type = body.get("dangerType", "trouble")
    location_name = body.get("locationName", "")
    alert_msg = body.get("alertMsg", "Emergency alert")

    if not sender_id or not receiver_ids:
        raise HTTPException(status_code=400, detail="senderId and receiverIds are required")

    if not _firebase_initialized:
        raise HTTPException(status_code=503, detail="Firebase not initialized")

    sent = 0
    db = firestore.client()

    for uid in receiver_ids:
        try:
            user_doc = db.collection("users").document(uid).get()
            fcm_token = None
            if user_doc.exists:
                data = user_doc.to_dict() or {}
                fcm_token = data.get("fcmToken") or data.get("fcm_token")

            if not fcm_token:
                continue

            title = f"{sender_name} needs help!" if sender_name else "Emergency Alert"
            message = messaging.Message(
                data={
                    "type": "help_message",
                    "route": "/help-alert",
                    "title": title,
                    "body": alert_msg,
                    "senderName": sender_name or "",
                    "dangerType": danger_type,
                    "locationName": location_name or "",
                    "alertMsg": alert_msg,
                },
                token=fcm_token,
                android=messaging.AndroidConfig(priority="high"),
            )
            messaging.send(message)
            sent += 1
        except Exception as exc:
            logger.warning("FCM failed for %s: %s", uid, exc)

    help_ref = db.collection("help_history").document()
    help_ref.set({
        "senderId": sender_id,
        "senderName": sender_name,
        "receiverIds": receiver_ids,
        "dangerType": danger_type,
        "alertMsg": alert_msg,
        "locationName": location_name,
        "createdAt": firestore.SERVER_TIMESTAMP,
    })

    return {"sent": sent, "total": len(receiver_ids)}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
