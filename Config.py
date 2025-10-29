# Config.py
# تحسينات: قيم افتراضية محسّنة، validation أفضل، performance tuning
# إضافة: دعم Vosk للـ STT المحلي (Offline)

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:

    ALLOW_INTERRUPTION = os.getenv("ALLOW_INTERRUPTION", "False").lower() == "true"
    ALLOW_WAKE_WORD = os.getenv("ALLOW_WAKE_WORD", "False").lower() == "true"
    DEVICE = os.getenv("DEVICE", "raspi5").strip()
    EYE_MODEL = os.getenv("EYE_MODEL", "img").strip()


    SERVER_API_URL = os.getenv("SERVER_API_URL", "http://127.0.0.1:5055").strip()

    # === API Keys (Required for ElevenLabs only) ===
    N8N_URL = os.getenv("N8N_URL", "").strip()
    HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "60"))
    RETRIES = int(os.getenv("RETRIES", "3"))


    # === Recorder Settings (16k/mono/16-bit) ===
    REC_SAMPLE_RATE = int(os.getenv("REC_SAMPLE_RATE", "16000"))
    REC_CHANNELS = int(os.getenv("REC_CHANNELS", "1"))
    REC_WIDTH = int(os.getenv("REC_WIDTH", "2"))
    #REC_DEVICE_INDEX = int(os.getenv("REC_DEVICE_INDEX", None))# None = default microphone
    REC_DEVICE_INDEX =  None # None = default microphone
    
    # ✅ Chunk size محسّن: أصغر = استجابة أسرع
    REC_CHUNK = int(os.getenv("REC_CHUNK", "256"))  # كان 512
    
    # ============ SESSION SETTINGS ============
    SESSION_ID = os.getenv("SESSION_ID", "robot-1").strip()

    # === Camera Settings (لو استخدمت Face Tracking) ===
    CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
    CAMERA_FLIP = os.getenv("CAMERA_FLIP", "False").strip().lower() in ("true", "1", "yes")
    SCREEN_MOVEMENT = int(os.getenv("SCREEN_MOVEMENT", "0"))

    # === Validation ===
    def __init__(self):
        print("⚙️  Config initiated")
       

# ==================== Main (للاختبار) ====================

if __name__ == "__main__":
    """Run validation when executed directly"""
    try:
        config = Config()
    except Exception as ex:
        print(f"\n❌ Configuration error: {ex}\n")
        exit(1)