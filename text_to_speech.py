# text_to_speech.py (مُحسّن)
import requests
import json
from typing import Optional
from Config import Config
import logging

logger = logging.getLogger(__name__)


class TextToSpeech:
    """
    Text-to-Speech class using API endpoint
    Converts text to audio bytes (WAV or PCM format)
    """
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.api_base = self.config.SERVER_API_URL

    def tts(
        self, 
        text: str, 
        as_fmt: str = "wav",
        voice: Optional[str] = None,
        timeout: int = 120
    ) -> bytes:
        """
        Send text to /tts endpoint and get audio bytes.
        
        Args:
            api_base: Base URL of the API (e.g., "http://127.0.0.1:5055")
            text: Text to convert to speech
            as_fmt: Output format - "wav" or "pcm" (default: "wav")
            voice: Optional voice name (e.g., "en_US-lessac-medium")
            timeout: Request timeout in seconds
            
        Returns:
            Audio bytes (WAV or PCM format)
            
        Raises:
            ValueError: If text is empty
            requests.exceptions.RequestException: On API errors
        """
        api_base = self.config.SERVER_API_URL 


        if not text or not text.strip():
            raise ValueError("Empty text provided")
        
        text = text.strip()
        
        api_url = f"{api_base.rstrip('/')}/tts"
        
        # إعداد البيانات
        payload = {
            "text": text,
            "as": as_fmt.lower()
        }
        
        if voice:
            payload["voice"] = voice
        
        headers = {"Content-Type": "application/json"}
        
        logger.info(f"📤 Sending text to TTS: {api_url}")
        logger.debug(f"   Text: {text[:100]}{'...' if len(text) > 100 else ''}")
        logger.debug(f"   Format: {as_fmt}")
        
        try:
            resp = requests.post(
                api_url,
                data=json.dumps(payload),
                headers=headers,
                timeout=timeout
            )
            resp.raise_for_status()
            
            audio_bytes = resp.content
            
            if not audio_bytes:
                logger.warning("⚠️  Empty audio response")
                return b""
            
            logger.info(f"✅ TTS response: {len(audio_bytes)} bytes")
            
            # معلومات إضافية للـ PCM format
            if as_fmt.lower() == "pcm":
                sample_rate = resp.headers.get("x-sample-rate", "unknown")
                sample_format = resp.headers.get("x-sample-format", "unknown")
                channels = resp.headers.get("x-channels", "unknown")
                logger.debug(f"   Sample Rate: {sample_rate}Hz")
                logger.debug(f"   Format: {sample_format}")
                logger.debug(f"   Channels: {channels}")
            
            return audio_bytes
            
        except requests.exceptions.HTTPError as ex:
            logger.error(f"❌ HTTP Error: {ex}")
            
            # محاولة عرض رسالة الخطأ من السيرفر
            try:
                error_data = ex.response.json()
                logger.error(f"   Server Error: {error_data.get('error', 'Unknown')}")
            except:
                logger.error(f"   Response: {ex.response.text if ex.response else 'N/A'}")
            
            raise
            
        except requests.exceptions.ConnectionError as ex:
            logger.error(f"❌ Connection Error: {ex}")
            logger.error(f"   Is the API server running at {api_base}?")
            raise
            
        except requests.exceptions.Timeout as ex:
            logger.error(f"❌ Timeout Error: {ex}")
            raise
            
        except Exception as ex:
            logger.error(f"❌ Unexpected Error: {ex}")
            raise

    def cleanup(self):
        """Cleanup resources (if any)"""
        logger.debug("TTS cleanup called")
        pass