# eye_player_pi_simple.py
# مشغل فيديو بسيط يعمل على Raspberry Pi بدون threading
import cv2
import os

# علم تحكم للإيقاف
_stop_flag = False


def stop():
    """إيقاف الفيديو من أي مكان (تُستدعى من main)."""
    global _stop_flag
    _stop_flag = True


def play(video_path="Resources/eye_videos/01.mp4", fullscreen=True, scale=1.0):
    """
    تشغيل الفيديو في حلقة مستمرة مع إمكانية الإيقاف عبر stop()
    - fullscreen: لعرض ملء الشاشة (أفضل أداءً على Pi)
    - scale: لتكبير/تصغير الإطار عند عدم استخدام fullscreen
    """
    global _stop_flag
    _stop_flag = False

    # تأكد من وجود الملف
    if not os.path.exists(video_path):
        print(f"❌ الملف غير موجود: {video_path}")
        # البحث عن mp4 بدائل
        for root, _, files in os.walk("Resources"):
            for f in files:
                if f.lower().endswith(".mp4"):
                    print(f"📂 تم العثور على {f} في {root}")
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ فشل في فتح الفيديو: {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    delay = int(1000 / fps) if fps and fps > 0 else 33  # تأخير آمن

    window_name = "Eye"
    if fullscreen:
        cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    else:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    loops = 0

    try:
        while not _stop_flag:
            ret, frame = cap.read()
            if not ret:
                loops += 1
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            if not fullscreen and scale != 1.0:
                h, w = frame.shape[:2]
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

            cv2.imshow(window_name, frame)

            # الخروج بالمفتاح أو إغلاق النافذة
            key = cv2.waitKey(delay) & 0xFF
            if key in (ord("q"), 27):  # q أو ESC
                break

            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                break

            if _stop_flag:
                break

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print(f"✅ تم الإيقاف بعد {loops} دورة إعادة.")


def run():
    """تشغيل افتراضي."""
    play(video_path="Resources/eye_videos/01.mp4", fullscreen=True, scale=1.0)


# مثال استخدام:
# from eye_player_pi_simple import run, stop
# run()   # لتشغيل الفيديو
# stop()  # لإيقافه

if __name__ == "__main__":
    run()
