# -*- coding: utf-8 -*-
import os, time, platform
import pygame

RENDER_W, RENDER_H = 480, 320
BG_COLOR  = (0, 0, 0)
EYE_COLOR = (255, 255, 255)
EYE_SIZE  = 120
BLINK_DELAY = 0.25
BLINK_PAUSE = 2.5

def is_pi():
    m = platform.machine().lower()
    return ("arm" in m) or ("aarch64" in m) or ("raspberry" in platform.platform().lower())

def init_display():
    """
    يحاول يفتح الشاشة بالترتيب:
    1) X11 لو فيه DISPLAY
    2) KMSDRM على الكونسول
    3) fbcon كحل أخير
    ويجبر Software Renderer علشان ماينشئش GL context
    """
    # امنع أي تسريع OpenGL/ES
    os.environ["SDL_RENDER_DRIVER"] = "software"
    os.environ["PYGAME_BLEND_ALPHA_SDL2"] = "1"  # آمن

    drivers = []
    if os.environ.get("DISPLAY"):
        drivers = ["x11", "kmsdrm", "fbcon"]
    else:
        # على الراسبي بدون سطح مكتب
        drivers = ["kmsdrm", "fbcon"]

    last_err = None
    for drv in drivers:
        try:
            os.environ["SDL_VIDEODRIVER"] = drv
            pygame.display.quit()
            pygame.display.init()
            flags = pygame.FULLSCREEN | pygame.SCALED | pygame.DOUBLEBUF
            screen = pygame.display.set_mode((RENDER_W, RENDER_H), flags, 32)
            pygame.mouse.set_visible(False)
            return screen
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"Failed to init display with software renderer. Last error: {last_err}")

# --- نفس دالة الرسم بتاعتك ---
def draw_eyes(screen, state):
    screen.fill(BG_COLOR)
    spacing = 60
    total_width = (EYE_SIZE * 2) + spacing
    start_x = (RENDER_W - total_width) // 2
    y_center = RENDER_H // 2

    if state == 0:
        h_factor = 1.0
    elif state == 1:
        h_factor = 0.5
    else:
        h_factor = 0.1

    new_h = int(EYE_SIZE * h_factor)
    y_top = y_center - new_h // 2

    pygame.draw.rect(screen, EYE_COLOR, (start_x, y_top, EYE_SIZE, new_h))
    pygame.draw.rect(screen, EYE_COLOR, (start_x + EYE_SIZE + spacing, y_top, EYE_SIZE, new_h))
    pygame.display.flip()

def run():
    # pygame.init()
    screen = init_display()  # ← الجديد
    blink_sequence = [0, 1, 2, 1, 0]
    running = True
    last_blink = time.time()

    # ارسم أول لقطة مفتوحة فورًا
    draw_eyes(screen, 0)

    try:
        while running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    running = False

            now = time.time()
            if now - last_blink >= BLINK_PAUSE:
                for state in blink_sequence:
                    draw_eyes(screen, state)
                    time.sleep(BLINK_DELAY)
                last_blink = time.time()
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    finally:
        pygame.quit()

if __name__ == "__main__":
    run()
