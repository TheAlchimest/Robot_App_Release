# speech_to_text.py (مُحسّن)
import requests
from typing import Optional, Union, Dict
from Config import Config
import logging

logger = logging.getLogger(__name__)


class SpeechToText:
    """
    Speech-to-Text class using API endpoint
    """
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.api_base =self.config.SERVER_API_URL

    def transcribe(
        self, 
        wav_bytes: bytes, 
        language: Optional[str] = None,
        timeout: int = 120
    ) -> Union[str, Dict]:
        """
        Send WAV bytes to /stt endpoint.
        
        Args:
            api_base: Base URL of the API (e.g., "http://127.0.0.1:5055")
            wav_bytes: WAV audio bytes (must have valid WAV header)
            language: Optional language code (e.g., "ar", "en")
            timeout: Request timeout in seconds
            
        Returns:
            Transcribed text as string, or full JSON dict if needed
            
        Raises:
            requests.exceptions.RequestException: On API errors
        """
        api_base = self.config.SERVER_API_URL 

        if not wav_bytes:
            raise ValueError("Empty audio data provided")
        
        # التحقق من أن البيانات WAV صحيحة
        if not wav_bytes.startswith(b"RIFF"):
            raise ValueError(
                "Audio data must be in WAV format (starting with RIFF header). "
                "Use recorder.pcm_to_wav() to convert PCM to WAV first."
            )
        
        api_url = f"{api_base.rstrip('/')}/stt"
        
        # إضافة معامل اللغة إذا وُجد
        params = {}
        if language:
            params["language"] = language
        
        files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
        
        logger.info(f"📤 Sending audio to STT: {api_url}")
        logger.debug(f"   Audio size: {len(wav_bytes)} bytes")
        
        try:
            resp = requests.post(
                api_url, 
                files=files, 
                params=params,
                timeout=timeout
            )
            resp.raise_for_status()
            
            result = resp.json()
            logger.info(f"✅ STT response: {result}")
            
            # إرجاع النص مباشرة للسهولة
            if isinstance(result, dict) and "text" in result:
                return result["text"]
            
            return result
            
        except requests.exceptions.HTTPError as ex:
            logger.error(f"❌ HTTP Error: {ex}")
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
        logger.debug("STT cleanup called")
        pass