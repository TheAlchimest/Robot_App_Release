# main3.py (مُصلح)
import time
import numpy as np
import sounddevice as sd
import io
import wave
from typing import Tuple

from text_to_speech import TextToSpeech
from ai_n8n import N8nClient
from audio_recorder import AudioRecorder
from speech_to_text import SpeechToText

# -------------------- Config --------------------
DEFAULT_API_BASE = "http://127.0.0.1:5055"
DEFAULT_SR = 16000
DEFAULT_SECONDS = 3

# تهيئة المكونات
tts = TextToSpeech()
n8n = N8nClient()
recorder = AudioRecorder()
stt = SpeechToText()


# -------------------- Helpers --------------------
def np_int16_to_wav_bytes(arr: np.ndarray, sample_rate: int, channels: int = 1) -> bytes:
    """
    Wrap an int16 mono numpy array into a WAV file in-memory.
    """
    if arr.dtype != np.int16:
        raise ValueError("Expected int16 array")
    if channels != 1:
        raise ValueError("Only mono supported here")

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sample_rate)
        wf.writeframes(arr.tobytes())
    return buf.getvalue()


def wav_bytes_to_np_int16(wav_bytes: bytes) -> Tuple[np.ndarray, int]:
    """
    Parse WAV bytes to (int16 mono numpy array, sample_rate).
    If source is stereo, average to mono.
    """
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        sr = wf.getframerate()
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
        frames = wf.readframes(wf.getnframes())

    if sw != 2:
        raise ValueError("Only 16-bit WAV supported")
    arr = np.frombuffer(frames, dtype=np.int16)
    if ch == 2:
        arr = arr.reshape(-1, 2).mean(axis=1).astype(np.int16)  # mono

    return arr, sr


def play_wav_bytes(wav_bytes: bytes) -> None:
    """
    Play WAV bytes fully in-memory using sounddevice.
    """
    audio, sr = wav_bytes_to_np_int16(wav_bytes)
    sd.play(audio, samplerate=sr, blocking=True)


def main():
    #===========================================
    print("\n" + "="*60)
    print("🤖 VOICE ASSISTANT WITH PIPER TTS")
    print("="*60 + "\n")
    #===========================================
    
    try:
        while True:
            print("ℹ️  Listening...")
            
            # 1) تسجيل الصوت (PCM خام)
            audio_pcm = recorder.record_until_silence(
                max_duration=25.0,
                noise_calib_duration=0.8,
                start_frames=3,
                end_frames=18,
                post_silence_hold=0.35,
                pre_roll_ms=350,
                min_speech_after_start=1.8,
                threshold_boost=3.0
            )

            if not audio_pcm:
                print("⚠️  No audio recorded")
                continue

            # 🔧 الإصلاح: تحويل PCM إلى WAV قبل الإرسال
            print("🔄 Converting PCM to WAV...")
            audio_wav = recorder.pcm_to_wav(audio_pcm)
            
            if not audio_wav:
                print("❌ Failed to convert PCM to WAV")
                continue

            print(f"✅ Audio ready: {len(audio_wav)} bytes")

            # 2) تحويل الصوت إلى نص (STT)
            try:
                user_input = stt.transcribe(DEFAULT_API_BASE, audio_wav)
                
                # التحقق من صيغة الرد
                if isinstance(user_input, dict):
                    user_text = user_input.get('text', '')
                else:
                    user_text = str(user_input)
                
                if not user_text or not user_text.strip():
                    print("⚠️  Empty transcription")
                    continue
                    
            except Exception as ex:
                print(f"❌ STT error: {ex}")
                import traceback
                traceback.print_exc()
                continue

            print(f"\n🎤 User: {user_text}")

            # 3) إرسال للـ AI والحصول على الرد
            try:
                ai_response = n8n.chat("123456", user_text)
                
                if not ai_response or not ai_response.strip():
                    print("⚠️  Empty AI response")
                    continue
                    
                print(f"🤖 AI: {ai_response}")
                
            except Exception as ex:
                print(f"❌ AI error: {ex}")
                continue

            # 4) تحويل النص إلى صوت (TTS)
            try:
                wav_reply = tts.tts(DEFAULT_API_BASE, ai_response, as_fmt="wav")
                
                if not wav_reply:
                    print("❌ No audio generated")
                    continue
                    
            except Exception as ex:
                print(f"❌ TTS error: {ex}")
                continue

            # 5) تشغيل الصوت من الذاكرة مباشرة
            try:
                print("🔊 Playing response...")
                play_wav_bytes(wav_reply)
                print("✅ Playback finished\n")
            except Exception as ex:
                print(f"❌ Playback error: {ex}")

    except KeyboardInterrupt:
        print("\n⛔ KeyboardInterrupt: stopping assistant.")
        
    finally:
        # تنظيف الموارد
        print("\n🧹 Cleaning up resources...")
        
        try:
            sd.stop()
            print("✅ Audio stopped")
        except Exception as ex:
            print(f"⚠️  Audio stop error: {ex}")
        
        try:
            tts.cleanup()
            print("✅ TTS cleaned")
        except Exception as ex:
            print(f"⚠️  TTS cleanup error: {ex}")
        
        try:
            stt.cleanup()
            print("✅ STT cleaned")
        except Exception as ex:
            print(f"⚠️  STT cleanup error: {ex}")
        
        try:
            recorder.close()
            print("✅ Recorder closed")
        except Exception as ex:
            print(f"⚠️  Recorder close error: {ex}")
        
        print("\n" + "="*60)
        print("✅ System stopped successfully")
        print("="*60 + "\n")


if __name__ == "__main__":
    main()