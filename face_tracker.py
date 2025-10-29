# face_tracker.py
# تحسينات: أداء أفضل، حركة أكثر سلاسة، blink واقعي، تكامل مع النظام

import cv2
import time
import random
import numpy as np
import threading
from pathlib import Path
from Config import Config

try:
    from cvzone.FaceDetectionModule import FaceDetector
    from cvzone.PIDModule import PID
    from cvzone.SerialModule import SerialObject
    HAS_CVZONE = True
except ImportError:
    HAS_CVZONE = False
    print("⚠️  cvzone not available, face tracking disabled")

# ==========================================
# GLOBAL STATE
# ==========================================
class EyeState:
    def __init__(self):
        self.running = True
        self.mode = "natural"  # "natural" or "tracking"
        self.blink_enabled = False
        self.talking = False  # للتكامل مع TTS
        self._lock = threading.Lock()
    
    def set_talking(self, talking: bool):
        with self._lock:
            self.talking = talking
    
    def is_talking(self) -> bool:
        with self._lock:
            return self.talking
    
    def stop(self):
        with self._lock:
            self.running = False

# Global state instance
eye_state = EyeState()

# ==========================================
# CONFIGURATION
# ==========================================
cfg = Config()

CAMERA_INDEX = getattr(cfg, 'CAMERA_INDEX', 0)
CAMERA_FLIP = getattr(cfg, 'CAMERA_FLIP', False)

# Eye images paths
EYE_BACKGROUND = Path("Resources/Eye-Background.png")
EYE_IRIS = Path("Resources/Eye-Ball.png")

# Display settings
WINDOW_NAME = "Robot Eyes"
FULLSCREEN = True
DISPLAY_OFFSET = getattr(cfg, 'SCREEN_MOVEMENT', 0)  # للشاشات المتعددة

# Performance settings
FPS_TARGET = 30
FACE_DETECTION_INTERVAL = 2  # كل كم frame نكشف الوجه

# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def load_eye_images():
    """تحميل صور العين مع error handling"""
    if not EYE_BACKGROUND.exists():
        print(f"❌ Eye background not found: {EYE_BACKGROUND}")
        return None, None
    
    if not EYE_IRIS.exists():
        print(f"❌ Eye iris not found: {EYE_IRIS}")
        return None, None
    
    background = cv2.imread(str(EYE_BACKGROUND), cv2.IMREAD_UNCHANGED)
    iris = cv2.imread(str(EYE_IRIS), cv2.IMREAD_UNCHANGED)
    
    if background is None or iris is None:
        print("❌ Failed to load eye images")
        return None, None
    
    print(f"✅ Loaded eye images: {background.shape}, {iris.shape}")
    return background, iris


def overlay_iris(background, iris, x, y, opacity=1.0):
    """رسم القزحية على الخلفية مع alpha blending محسّن"""
    h, w = iris.shape[:2]
    
    # Boundary checking
    if x < 0:
        iris = iris[:, -x:]
        w = iris.shape[1]
        x = 0
    if y < 0:
        iris = iris[-y:, :]
        h = iris.shape[0]
        y = 0
    
    if x + w > background.shape[1]:
        w = background.shape[1] - x
        iris = iris[:, :w]
    
    if y + h > background.shape[0]:
        h = background.shape[0] - y
        iris = iris[:h]
    
    if w <= 0 or h <= 0:
        return
    
    # Alpha blending
    alpha = (iris[:, :, 3] / 255.0) * opacity
    alpha_3d = np.stack([alpha] * 3, axis=2)
    
    background[y:y+h, x:x+w, :3] = (
        alpha_3d * iris[:, :, :3] + 
        (1 - alpha_3d) * background[y:y+h, x:x+w, :3]
    ).astype(np.uint8)


def create_blink_overlay(background, blink_amount):
    """
    إنشاء تأثير رمش واقعي
    blink_amount: 0 (مفتوح) إلى 1 (مغلق)
    """
    if blink_amount <= 0:
        return background
    
    overlay = background.copy()
    h, w = overlay.shape[:2]
    
    # حساب ارتفاع الإغلاق
    close_height = int(h * blink_amount * 0.5)
    
    if close_height > 0:
        # تعتيم من الأعلى (الجفن العلوي)
        overlay[:close_height, :] = (overlay[:close_height, :] * 0.2).astype(np.uint8)
        
        # تعتيم من الأسفل (الجفن السفلي - أقل)
        bottom_close = int(close_height * 0.6)
        if bottom_close > 0:
            overlay[h-bottom_close:, :] = (overlay[h-bottom_close:, :] * 0.3).astype(np.uint8)
    
    return overlay


def lerp(start, end, t):
    """Linear interpolation"""
    return start + (end - start) * t


def ease_in_out(t):
    """Smooth easing function"""
    return t * t * (3 - 2 * t)


# ==========================================
# BLINK CONTROLLER
# ==========================================

class BlinkController:
    """تحكم واقعي في الرمش"""
    
    def __init__(self):
        self.is_blinking = False
        self.blink_progress = 0.0
        self.blink_speed = 0.15  # سرعة الرمش
        self.last_blink_time = time.time()
        self.blink_interval = random.uniform(2.5, 5.0)
        self.double_blink = False  # رمش مزدوج أحياناً
    
    def update(self, dt: float) -> float:
        """
        تحديث حالة الرمش
        Returns: blink_amount (0-1)
        """
        current_time = time.time()
        
        # بدء رمش جديد
        if not self.is_blinking and current_time - self.last_blink_time >= self.blink_interval:
            self.is_blinking = True
            self.blink_progress = 0.0
            # 10% فرصة للرمش المزدوج
            self.double_blink = random.random() < 0.1
        
        # تحديث الرمش
        if self.is_blinking:
            self.blink_progress += self.blink_speed
            
            # انتهى الرمش
            if self.blink_progress >= 2.0:
                if self.double_blink:
                    # رمش مزدوج: رمش آخر سريع
                    self.double_blink = False
                    self.blink_progress = 0.0
                else:
                    self.is_blinking = False
                    self.blink_progress = 0.0
                    self.last_blink_time = current_time
                    # رمش أقل تكراراً عند الكلام
                    if eye_state.is_talking():
                        self.blink_interval = random.uniform(4.0, 7.0)
                    else:
                        self.blink_interval = random.uniform(2.5, 5.0)
        
        # حساب blink amount
        if self.blink_progress < 1.0:
            # الإغلاق
            blink_amount = ease_in_out(self.blink_progress)
        else:
            # الفتح
            blink_amount = ease_in_out(2.0 - self.blink_progress)
        
        return blink_amount if self.is_blinking else 0.0


# ==========================================
# MAIN FUNCTIONS
# ==========================================



def trackUserFace(enable_arduino=False):
    """
    تتبع وجه المستخدم (محسّن للأداء)
    """
    if not HAS_CVZONE:
        print("❌ cvzone not installed, cannot track faces")
        print("   Install with: pip install cvzone opencv-python mediapipe")
        return
    
    print("👁️  Starting face tracking...")
    
    # تحميل الصور
    background_img, iris_img = load_eye_images()
    if background_img is None or iris_img is None:
        return
    
    # الكاميرا
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"❌ Cannot open camera {CAMERA_INDEX}")
        return
    
    # Face detector
    detector = FaceDetector(minDetectionCon=0.7)
    
    # PID controller للحركة السلسة
    xPID = PID([0.03, 0, 0.06], 640 // 2, axis=0)
    
    # Arduino
    arduino = None
    xAngle = 90
    if enable_arduino:
        try:
            arduino = SerialObject(digits=3)
            print("✅ Arduino initialized")
        except Exception as e:
            print(f"⚠️  Arduino not available: {e}")
    
    # Blink controller
    blink_ctrl = BlinkController()
    
    # Eye positions (simplified for tracking)
    iris_position = (325, 225)
    
    # إنشاء نافذة
    cv2.namedWindow(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN)
    if FULLSCREEN:
        cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    
    # FPS control
    frame_count = 0
    last_time = time.time()
    
    print("✅ Face tracking started")
    print("   Press 'q' or ESC to quit")
    
    try:
        while eye_state.running:
            success, img = cap.read()
            if not success:
                print("⚠️  Failed to read from camera")
                time.sleep(0.1)
                continue
            
            if CAMERA_FLIP:
                img = cv2.flip(img, 0)
            
            # Face detection (كل بضعة frames للأداء)
            if frame_count % FACE_DETECTION_INTERVAL == 0:
                img, bboxs = detector.findFaces(img, draw=False)
                
                if bboxs:
                    cx = bboxs[0]['center'][0]
                    resultX = int(xPID.update(cx))
                    
                    # تحديد موضع القزحية
                    if CAMERA_FLIP:
                        if resultX > 1:
                            iris_position = (400, 225)
                        elif resultX < -1:
                            iris_position = (250, 225)
                        else:
                            iris_position = (325, 225)
                    else:
                        if resultX > 1:
                            iris_position = (250, 225)
                        elif resultX < -1:
                            iris_position = (400, 225)
                        else:
                            iris_position = (325, 225)
                    
                    # Arduino control
                    if arduino and abs(resultX) > 2:
                        xAngle += resultX
                        xAngle = max(60, min(120, xAngle))  # clamp
                        try:
                            arduino.sendData([0, 0, xAngle])
                        except Exception:
                            pass
            
            # Update blink
            blink_amount = blink_ctrl.update(0.033) if eye_state.blink_enabled else 0.0
            
            # رسم العين
            frame = background_img.copy()
            overlay_iris(frame, iris_img, iris_position[0], iris_position[1])
            
            if blink_amount > 0:
                frame = create_blink_overlay(frame, blink_amount)
            
            # عرض
            cv2.imshow(WINDOW_NAME, frame)
            if DISPLAY_OFFSET > 0:
                cv2.moveWindow(WINDOW_NAME, -DISPLAY_OFFSET, 0)
            
            # (اختياري) عرض الكاميرا للتشخيص
            # cv2.imshow("Camera", cv2.resize(img, (320, 240)))
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
            
            frame_count += 1
            
            # FPS info
            if frame_count % 30 == 0:
                current_time = time.time()
                fps = 30 / (current_time - last_time)
                last_time = current_time
                #print(f"FPS: {fps:.1f}")
    
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cap.release()
        cleanup(arduino)


def cleanup(arduino=None):
    """تنظيف الموارد"""
    print("\n🧹 Cleaning up...")
    
    if arduino:
        try:
            arduino.sendData([0, 0, 90])  # مركز
            print("✅ Arduino reset")
        except Exception:
            pass
    
    try:
        cv2.destroyAllWindows()
        print("✅ Windows closed")
    except Exception:
        pass


# ==========================================
# THREADED VERSION (للتكامل مع main.py)
# ==========================================

def run(enable_arduino=False):
    trackUserFace(enable_arduino)



# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    enable_arduino = False
    print("=" * 50)
    print("👁️  ROBOT EYES - OPTIMIZED")
    print("=" * 50)
    print(f"Arduino: {'enabled' if enable_arduino else 'disabled'}")
    print("=" * 50)
    run(enable_arduino)