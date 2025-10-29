# face_tracker.py
# تحسينات: أداء أفضل، حركة أكثر سلاسة، blink واقعي، تكامل مع النظام

import cv2
import time
import random
import numpy as np
import threading
from pathlib import Path
from Config import Config

# ==========================================
# GLOBAL STATE
# ==========================================
class EyeState:
    def __init__(self):
        self.running = True
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
# EYE MOVEMENT CONTROLLER
# ==========================================

class EyeMovementController:
    """تحكم في حركة العين الطبيعية"""
    
    # مواضع العين (x, y)
    POSITIONS = {
        'center': (325, 225),
        'right': (400, 225),
        'left': (250, 225),
        'up': (325, 200),
        'down': (325, 250),
        'up_right': (380, 210),
        'up_left': (270, 210),
        'down_right': (380, 240),
        'down_left': (270, 240),
    }
        
    def __init__(self):
        self.current_pos = 'center'
        self.target_pos = 'center'
        self.current_x = float(self.POSITIONS['center'][0])
        self.current_y = float(self.POSITIONS['center'][1])
        self.target_x = self.current_x
        self.target_y = self.current_y
        
        # Micro-movements (حركات صغيرة واقعية)
        self.micro_x = 0
        self.micro_y = 0
        self.micro_time = time.time()
        
        # Transition
        self.is_transitioning = False
        self.transition_progress = 0.0
        self.transition_speed = 0.08
        
        # Timing
        self.last_movement_time = time.time()
        self.hold_duration = random.uniform(2.0, 4.0)
    
    def update(self, dt: float):
        """تحديث موضع العين"""
        current_time = time.time()
        
        # Micro-movements (كل 100ms)
        if current_time - self.micro_time > 0.1:
            self.micro_x = random.uniform(-2, 2)
            self.micro_y = random.uniform(-1, 1)
            self.micro_time = current_time
        
        # بدء حركة جديدة
        if not self.is_transitioning and current_time - self.last_movement_time >= self.hold_duration:
            self.start_new_movement()
        
        # Smooth transition
        if self.is_transitioning:
            self.transition_progress += self.transition_speed
            
            if self.transition_progress >= 1.0:
                self.is_transitioning = False
                self.transition_progress = 1.0
                self.current_x = self.target_x
                self.current_y = self.target_y
            else:
                # Smooth interpolation with easing
                t = ease_in_out(self.transition_progress)
                self.current_x = lerp(self.current_x, self.target_x, t)
                self.current_y = lerp(self.current_y, self.target_y, t)
        
        # الموضع النهائي مع micro-movements
        final_x = int(self.current_x + self.micro_x)
        final_y = int(self.current_y + self.micro_y)
        
        return final_x, final_y
    
    def start_new_movement(self):
        """بدء حركة عين جديدة"""
        self.is_transitioning = True
        self.transition_progress = 0.0
        self.current_pos = self.target_pos
        
        # اختيار موضع جديد
        # 60% فرصة للعودة للمركز
        if random.random() < 0.6 and self.current_pos != 'center':
            self.target_pos = 'center'
        else:
            positions = list(self.POSITIONS.keys())
            positions.remove(self.current_pos)
            self.target_pos = random.choice(positions)
        
        self.target_x = float(self.POSITIONS[self.target_pos][0])
        self.target_y = float(self.POSITIONS[self.target_pos][1])
        
        
        self.last_movement_time = time.time()
        # مدة أطول عند النظر للمركز
        if self.target_pos == 'center':
            self.hold_duration = random.uniform(3.0, 5.0)
        else:
            self.hold_duration = random.uniform(2.0, 4.0)
    
    def look_at_position(self, position: str):
        """النظر لموضع معين"""
        if position in self.POSITIONS:
            self.target_pos = position
            self.target_x = float(self.POSITIONS[position][0])
            self.target_y = float(self.POSITIONS[position][1])
            self.is_transitioning = True
            self.transition_progress = 0.0
            



# ==========================================
# MAIN FUNCTIONS
# ==========================================

def run():
    """
    حركة عين طبيعية بدون كاميرا (محسّنة)
    """
    print("👁️  Starting natural eye movement...")
    
    # تحميل الصور
    background_img, iris_img = load_eye_images()
    if background_img is None or iris_img is None:
        print("❌ Cannot load eye images")
        return
    
    
    # Controllers
    blink_ctrl = BlinkController()
    movement_ctrl = EyeMovementController()
    
    # إنشاء نافذة
    cv2.namedWindow(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN)
    if FULLSCREEN:
        cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    
    # FPS control
    frame_time = 1.0 / FPS_TARGET
    last_time = time.time()
    
    print(f"✅ Eye movement started (FPS: {FPS_TARGET})")
    print("   Press 'q' or ESC to quit")
    print("   Press 'b' to toggle blinking")
    print("   Press 'c' to look at center")
    
    try:
        while eye_state.running:
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time
            
            # Update controllers
            iris_x, iris_y = movement_ctrl.update(dt)
            blink_amount = blink_ctrl.update(dt) if eye_state.blink_enabled else 0.0
            
            # رسم العين
            frame = background_img.copy()
            overlay_iris(frame, iris_img, iris_x, iris_y)
            
            # تطبيق الرمش
            if blink_amount > 0:
                frame = create_blink_overlay(frame, blink_amount)
            
            # عرض
            cv2.imshow(WINDOW_NAME, frame)
            if DISPLAY_OFFSET > 0:
                cv2.moveWindow(WINDOW_NAME, -DISPLAY_OFFSET, 0)
            
            # Keyboard input
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:  # ESC
                break
            elif key == ord('b'):
                eye_state.blink_enabled = not eye_state.blink_enabled
                print(f"Blinking: {'ON' if eye_state.blink_enabled else 'OFF'}")
            elif key == ord('c'):
                movement_ctrl.look_at_position('center')
                print("Looking at center")
            
            # FPS limiting
            elapsed = time.time() - current_time
            if elapsed < frame_time:
                time.sleep(frame_time - elapsed)
    
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup()


def cleanup():
    eye_state.stop()
    """تنظيف الموارد"""
    print("\n🧹 Cleaning up...")
    
    
    try:
        cv2.destroyAllWindows()
        print("✅ Windows closed")
    except Exception:
        pass


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    import sys
    print("=" * 50)
    print("👁️  ROBOT EYES - OPTIMIZED")
    print("=" * 50)
    print("=" * 50)
    
    run()