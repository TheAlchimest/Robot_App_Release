# video_eye_player.py
# تحسينات: دعم عدة فيديوهات، transitions، أداء أفضل، تكامل مع النظام

import cv2
import time
import threading
import numpy as np
from pathlib import Path
from typing import Optional, List
from Config import Config

# ==========================================
# CONFIGURATION
# ==========================================

cfg = Config()

VIDEO_PATHS = {
    'idle': Path("Resources/eyes_idle.mp4"),
    'talking': Path("Resources/eyes_talking.mp4"),
    'blinking': Path("Resources/eyes_blink.mp4"),
    'looking_left': Path("Resources/eyes_left.mp4"),
    'looking_right': Path("Resources/eyes_right.mp4"),
}

WINDOW_NAME = "Robot Eyes Video"
FULLSCREEN = True
DISPLAY_OFFSET = getattr(cfg, 'SCREEN_MOVEMENT', 0)
FPS_TARGET = 30

# ==========================================
# STATE MANAGEMENT
# ==========================================

class VideoPlayerState:
    def __init__(self):
        self.running = True
        self.current_video = 'idle'
        self.next_video = None
        self.transition_progress = 0.0
        self.is_transitioning = False
        self._lock = threading.Lock()
    
    def set_video(self, video_name: str):
        """تغيير الفيديو مع transition"""
        with self._lock:
            if video_name in VIDEO_PATHS:
                self.next_video = video_name
                self.is_transitioning = True
                self.transition_progress = 0.0
    
    def get_current_video(self) -> str:
        with self._lock:
            return self.current_video
    
    def update_transition(self, dt: float) -> bool:
        """
        تحديث الـ transition
        Returns: True إذا انتهى التحول
        """
        with self._lock:
            if not self.is_transitioning:
                return False
            
            self.transition_progress += dt * 2.0  # سرعة التحول
            
            if self.transition_progress >= 1.0:
                self.current_video = self.next_video
                self.next_video = None
                self.is_transitioning = False
                self.transition_progress = 0.0
                return True
            
            return False
    
    def stop(self):
        with self._lock:
            self.running = False

# Global state
player_state = VideoPlayerState()


# ==========================================
# VIDEO LOADER
# ==========================================

class VideoLoader:
    """محمل فيديوهات مع caching"""
    
    def __init__(self):
        self.videos = {}
        self.load_all_videos()
    
    def load_all_videos(self):
        """تحميل كل الفيديوهات المتاحة"""
        print("📹 Loading videos...")
        
        for name, path in VIDEO_PATHS.items():
            if not path.exists():
                print(f"⚠️  Video not found: {name} ({path})")
                continue
            
            cap = cv2.VideoCapture(str(path))
            if not cap.isOpened():
                print(f"❌ Cannot open: {name}")
                continue
            
            # تحميل كل الـ frames (للسرعة)
            frames = []
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(frame)
            
            cap.release()
            
            if frames:
                self.videos[name] = frames
                print(f"✅ Loaded {name}: {len(frames)} frames")
            else:
                print(f"⚠️  Empty video: {name}")
        
        if not self.videos:
            print("❌ No videos loaded!")
        else:
            print(f"✅ Total videos loaded: {len(self.videos)}")
    
    def get_frame(self, video_name: str, frame_index: int) -> Optional[np.ndarray]:
        """الحصول على frame معين"""
        if video_name not in self.videos:
            return None
        
        frames = self.videos[video_name]
        if not frames:
            return None
        
        # Loop the video
        index = frame_index % len(frames)
        return frames[index].copy()
    
    def get_frame_count(self, video_name: str) -> int:
        """عدد الـ frames"""
        if video_name not in self.videos:
            return 0
        return len(self.videos[video_name])


# ==========================================
# TRANSITION EFFECTS
# ==========================================

def blend_frames(frame1: np.ndarray, frame2: np.ndarray, alpha: float) -> np.ndarray:
    """مزج بين frameين"""
    return cv2.addWeighted(frame1, 1 - alpha, frame2, alpha, 0)


def fade_transition(frame1: np.ndarray, frame2: np.ndarray, progress: float) -> np.ndarray:
    """Fade transition"""
    return blend_frames(frame1, frame2, progress)


def slide_transition(frame1: np.ndarray, frame2: np.ndarray, progress: float, direction='left') -> np.ndarray:
    """Slide transition"""
    h, w = frame1.shape[:2]
    offset = int(w * progress)
    
    result = np.zeros_like(frame1)
    
    if direction == 'left':
        result[:, :w-offset] = frame1[:, offset:]
        result[:, w-offset:] = frame2[:, :offset]
    else:  # right
        result[:, offset:] = frame1[:, :w-offset]
        result[:, :offset] = frame2[:, w-offset:]
    
    return result


# ==========================================
# MAIN PLAYER
# ==========================================

def run(default_video='idle'):
    """
    مشغل فيديو محسّن مع transitions
    """
    print("👁️  Starting video eye player...")
    
    # تحميل الفيديوهات
    loader = VideoLoader()
    
    if not loader.videos:
        print("❌ No videos to play")
        return
    
    # إعداد النافذة
    cv2.namedWindow(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN)
    if FULLSCREEN:
        cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    
    # State
    player_state.current_video = default_video
    current_frame_index = 0
    previous_frame_index = 0
    
    # FPS control
    frame_time = 1.0 / FPS_TARGET
    last_time = time.time()
    
    print(f"✅ Video player started")
    print(f"   Current video: {default_video}")
    print("   Press 'q' or ESC to quit")
    print("   Press '1-5' to switch videos:")
    print("     1: idle")
    print("     2: talking")
    print("     3: blinking")
    print("     4: looking left")
    print("     5: looking right")
    
    try:
        while player_state.running:
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time
            
            # Update transition
            transition_completed = player_state.update_transition(dt)
            if transition_completed:
                current_frame_index = 0
                print(f"✅ Switched to: {player_state.get_current_video()}")
            
            # Get current frame
            current_video = player_state.get_current_video()
            frame = loader.get_frame(current_video, current_frame_index)
            
            if frame is None:
                print(f"⚠️  No frame for {current_video}")
                time.sleep(0.1)
                continue
            
            # Apply transition if active
            if player_state.is_transitioning and player_state.next_video:
                next_frame = loader.get_frame(player_state.next_video, previous_frame_index)
                if next_frame is not None:
                    frame = fade_transition(frame, next_frame, player_state.transition_progress)
            
            # Display
            cv2.imshow(WINDOW_NAME, frame)
            if DISPLAY_OFFSET > 0:
                cv2.moveWindow(WINDOW_NAME, -DISPLAY_OFFSET, 0)
            
            # Keyboard input
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:  # ESC
                break
            elif key == ord('1'):
                player_state.set_video('idle')
            elif key == ord('2'):
                player_state.set_video('talking')
            elif key == ord('3'):
                player_state.set_video('blinking')
            elif key == ord('4'):
                player_state.set_video('looking_left')
            elif key == ord('5'):
                player_state.set_video('looking_right')
            
            # Update frame index
            if not player_state.is_transitioning:
                previous_frame_index = current_frame_index
                current_frame_index = (current_frame_index + 1) % loader.get_frame_count(current_video)
            
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
    """تنظيف الموارد"""
    print("\n🧹 Cleaning up...")
    player_state.stop()
    
    try:
        cv2.destroyAllWindows()
        print("✅ Windows closed")
    except Exception:
        pass


# ==========================================
# THREADED VERSION
# ==========================================

def run_video_player_threaded(video='idle'):
    """تشغيل video player في thread منفصل"""
    player_thread = threading.Thread(
        target=run,
        args=(video,),
        daemon=True,
        name="VideoEyePlayer"
    )
    player_thread.start()
    return player_thread


# ==========================================
# API للتحكم من main.py
# ==========================================

def switch_video(video_name: str):
    """تغيير الفيديو الحالي"""
    player_state.set_video(video_name)


def set_talking(talking: bool):
    """تغيير للوضع المناسب عند الكلام"""
    if talking:
        player_state.set_video('talking')
    else:
        player_state.set_video('idle')


def stop_player():
    """إيقاف المشغل"""
    player_state.stop()


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    import sys
    
    video = 'idle'
    if len(sys.argv) > 1:
        video = sys.argv[1]
    
    print("=" * 50)
    print("👁️  VIDEO EYE PLAYER - OPTIMIZED")
    print("=" * 50)
    print(f"Starting with: {video}")
    print("=" * 50)
    
    run(video)