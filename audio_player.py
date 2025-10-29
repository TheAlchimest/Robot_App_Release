# audio_player.py (PyAudio edition)
# -------------------------------------------------------------------
# Unified audio playback (async + blocking) via a single worker thread
# Uses PyAudio under the hood. Safe for concurrent calls.
# -------------------------------------------------------------------

from __future__ import annotations
from dataclasses import dataclass, field
from threading import Event, Thread, Lock
from queue import Queue, Empty
from typing import Optional
import time
import os
import wave
import audioop  # لخفض/رفع الصوت برمجيًا بدون numpy
import pyaudio


@dataclass
class AudioJob:
    path: str
    blocking: bool = False          # True => caller waits until done
    volume: float = 1.0             # 0.0 .. 1.0
    done: Event = field(default_factory=Event)
    # يُستخدم لإلغاء الحالية عند المقاطعة
    canceled: Event = field(default_factory=Event)


class AudioPlayer:
    """
    Threaded audio playback manager (PyAudio).
    - play_async(path): يشغّل الصوت في الخلفية فورًا ولا يوقف مسار التنفيذ.
    - play_blocking(path): يرسل job للثريد وينتظر حتى انتهاء التشغيل.
    - stop_current(): يوقف أي صوت قيد التشغيل فورًا.
    - shutdown(): يغلق الثريد و PyAudio بأمان.

    ملاحظات:
      * احرص على استدعاء start() مرّة واحدة بعد الإنشاء.
      * يدعم ملفات WAV (PCM 16-bit LE) مباشرةً.
      * لا يقوم بإعادة التشكيل Resample لتقليل الاستهلاك (أفضلية ملفات 16kHz mono).
    """

    def __init__(
        self,
        sample_rate: int = 16000,   # تلميح/افتراضي فقط (لن نستخدمه لو الملف مختلف)
        channels: int = 1,          # تلميح/افتراضي فقط
        frames_per_buffer: int = 1024
    ) -> None:
        self._queue: Queue[AudioJob] = Queue(maxsize=8)
        self._worker: Optional[Thread] = None
        self._running: bool = False
        self._lock = Lock()

        self._sample_rate = sample_rate
        self._channels = channels
        self._frames_per_buffer = frames_per_buffer

        self._pa: Optional[pyaudio.PyAudio] = None
        self._current_job: Optional[AudioJob] = None

        # آخر تشغيل لنفس الملف (لـ debounce اختياري)
        self._last_play_ts: dict[str, float] = {}
        self._min_gap_sec: float = 0.35  # تجاهل تكرارات أسرع من 350ms

    # ---------------- Lifecycle ----------------

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            try:
                self._pa = pyaudio.PyAudio()
            except Exception as e:
                print(f"⚠️ PyAudio init failed: {e}")
                self._pa = None

            self._running = True
            self._worker = Thread(target=self._run, name="AudioPlayerWorker", daemon=True)
            self._worker.start()

    def shutdown(self, join_timeout: float = 2.0) -> None:
        # أوقف الثريد
        with self._lock:
            self._running = False

        # أيقظ الثريد لو نائم
        try:
            self._queue.put_nowait(AudioJob(path="", blocking=False))
        except:
            pass

        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=join_timeout)

        # اغلق PyAudio
        try:
            if self._pa is not None:
                self._pa.terminate()
        except:
            pass
        finally:
            self._pa = None

    # ---------------- Public API ----------------

    def play_async(self, path: str, volume: float = 1.0) -> AudioJob:
        """شغّل الصوت في الخلفية (لا يحجب التنفيذ)."""
        if not path:
            return AudioJob(path="")
        if self._debounced(path):
            # تجاهل السبام السريع لنفس الملف
            return AudioJob(path=path, blocking=False)
        job = AudioJob(path=path, blocking=False, volume=max(0.0, min(1.0, volume)))
        self._safe_put(job)
        return job

    def play_blocking(self, path: str, volume: float = 1.0, timeout: Optional[float] = None) -> bool:
        """شغّل الصوت وانتظر حتى نهايته (أو حتى timeout)."""
        if not path:
            return True
        job = AudioJob(path=path, blocking=True, volume=max(0.0, min(1.0, volume)))
        self._safe_put(job)
        job.done.wait(timeout=timeout)
        return job.done.is_set()

    def stop_current(self) -> None:
        """إيقاف فوري لأي صوت جارٍ + إلغاء الـ job الجاري."""
        # علّم المهمة الحالية أنها مُلغاة
        cj = self._current_job
        if cj is not None:
            cj.canceled.set()

        # تفريغ أي عناصر "قديمة" بالطابور (اختياري)
        self.flush_queue()

    # ---------------- Internal ----------------

    def _safe_put(self, job: AudioJob) -> None:
        try:
            self._queue.put_nowait(job)
        except:
            # لو الطابور ممتلئ، اسحب أقدم عنصر وارمِه ثم ضع الجديد
            try:
                _ = self._queue.get_nowait()
            except Empty:
                pass
            self._queue.put_nowait(job)

    def _run(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break

            try:
                job = self._queue.get(timeout=0.5)
            except Empty:
                continue

            # end condition / wake worker
            if job.path == "" and not self._running:
                job.done.set()
                break

            # دعم أمان لو تم تمرير string مكان AudioJob
            if not isinstance(job, AudioJob):
                job = AudioJob(path=str(job), blocking=False)

            # مسار غير موجود
            if not os.path.exists(job.path):
                print(f"⚠️ Missing audio file: {job.path}")
                job.done.set()
                continue

            # شغّل الملف
            self._play_wav_job(job)

            # علّم المُرسل بانتهاء التشغيل
            job.done.set()
            # سجّل توقيت آخر تشغيل لهذا المسار (لـ debounce)
            self._last_play_ts[job.path] = time.time()

    def _play_wav_job(self, job: AudioJob) -> None:
        """تشغيل ملف WAV باستخدام PyAudio مع دعم الإلغاء والتحكم في الصوت."""
        if self._pa is None:
            print("⚠️ PyAudio not initialized.")
            return

        self._current_job = job
        wf = None
        stream = None
        try:
            # افتح الملف
            wf = wave.open(job.path, "rb")

            # تحقق من التنسيق
            sampwidth = wf.getsampwidth()  # يُفضّل 2 (16-bit)
            channels = wf.getnchannels()
            framerate = wf.getframerate()

            # افتح stream متوافق مع الملف (أخف على الـ Pi من إعادة التشكيل)
            try:
                stream = self._pa.open(
                    format=self._pa.get_format_from_width(sampwidth),
                    channels=channels,
                    rate=framerate,
                    output=True,
                    frames_per_buffer=self._frames_per_buffer
                )
            except Exception as e:
                print(f"❌ Cannot open audio stream: {e}")
                return

            # اقرأ وافرغ في الـ stream على دفعات صغيرة
            vol = float(job.volume)
            chunk = wf.readframes(self._frames_per_buffer)
            while chunk:
                # إلغاء فوري؟
                if job.canceled.is_set():
                    break

                # تحكم في الصوت برمجيًا (audioop.mul) — يعمل بدون numpy
                if vol < 0.999:  # تجنب كلفة غير ضرورية عند 1.0
                    try:
                        # factor في audioop.mul يكون float بين 0..N
                        # width = sampwidth (1=8bit, 2=16bit ...)
                        chunk = audioop.mul(chunk, sampwidth, vol)
                    except Exception as _:
                        # في حال فشل الضبط لأي سبب، اكتب الخام
                        pass

                try:
                    stream.write(chunk)
                except Exception as e:
                    # أحياناً ALSA يقطع عند تبديل أجهزة — تجاهل الخطأ وأنهِ
                    print(f"⚠️ stream write error: {e}")
                    break

                # التالي
                chunk = wf.readframes(self._frames_per_buffer)

        except wave.Error as e:
            print(f"❌ WAV error: {e}")
        except FileNotFoundError:
            print(f"⚠️ File not found: {job.path}")
        except Exception as e:
            print(f"❌ Audio playback error: {e}")
        finally:
            # أغلق الموارد بهدوء
            try:
                if stream is not None:
                    try:
                        stream.stop_stream()
                    except:
                        pass
                    stream.close()
            except:
                pass

            try:
                if wf is not None:
                    wf.close()
            except:
                pass

            self._current_job = None

    def _debounced(self, path: str) -> bool:
        last = self._last_play_ts.get(path)
        if last is None:
            return False
        return (time.time() - last) < self._min_gap_sec

    # مسح تراكم SFX الخلفية (اختياري)
    def flush_queue(self) -> None:
        try:
            while True:
                self._queue.get_nowait()
        except Empty:
            pass
