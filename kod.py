import numpy as np
import cv2
from mss import mss
import pyautogui
import time
import random
import threading
from pynput.mouse import Controller, Button

mouse = Controller()

THRESHOLD = 5  # maksymalny dystans Hamming
pyautogui.FAILSAFE = True

# TU wpiszesz swoje docelowe hashe
ALLOWED_HASHES = {
    "Okropieństwo": "0000000010000000010011000111111101011111010111111111111100000000",
    "Penelopa": "0000000000000000001111000011111001111110001111100011111000001100",
    "Statek_widmo": "0000000010000100011001000111111111111111011111111111111101000000",
    "Potwór_z_mackami": "0000000000000000100010101111111111101101111011111111111100000000",
}

# ====== PARAMETRY DO STROJENIA ======
LOWER_GREEN = np.array([35, 80, 80])   # dolny zakres HSV
UPPER_GREEN = np.array([85, 255, 255]) # górny zakres HSV

MIN_WIDTH = 70     # minimalna szerokość paska
MAX_HEIGHT = 11    # maksymalna wysokość paska
MIN_RATIO = 2      # szerokość / wysokość
# =====================================

def extract_fixed_roi(frame, x1, y1, x2, y2):
    """
    Wytnij stały prostokątny obszar z ekranu.
    Współrzędne w pikselach.
    """
    return frame[y1:y2, x1:x2]

def detect_color_presence(frame, lower_hsv, upper_hsv, min_pixels=50):
    """
    Sprawdza czy w danym ROI występuje określony kolor (w HSV).
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_hsv, upper_hsv)

    count = cv2.countNonZero(mask)

    return count > min_pixels, count

def apply_elliptical_roi(frame, radius_x_ratio=0.223, radius_y_ratio=0.27):
    h, w = frame.shape[:2]
    center_x = w // 2
    center_y = h // 2 + 50

    radius_x = int(w * radius_x_ratio)
    radius_y = int(h * radius_y_ratio)

    mask = np.zeros((h, w), dtype=np.uint8)

    cv2.ellipse(
        mask,
        (center_x, center_y),       # środek
        (radius_x, radius_y),       # promienie X i Y
        0,                          # obrót (stopnie)
        0,
        360,
        255,
        -1
    )

    roi = cv2.bitwise_and(frame, frame, mask=mask)
    return roi

def detect_green_bars(frame_bgr):
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, LOWER_GREEN, UPPER_GREEN)

    # Usunięcie drobnego szumu
    # kernel = np.ones((3,3), np.uint8)
    # mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        ratio = w / max(h, 1)

        if w > MIN_WIDTH and h < MAX_HEIGHT and ratio > MIN_RATIO:
            boxes.append((x, y, w, h))

    return boxes, mask

def extract_label_region(frame, x, y, w, h, height_above=16, label_height=12):
    """
    Wytnij region nad paskiem HP.
    """
    top = max(y - height_above, 0)
    bottom = max(y - height_above + label_height, 0)

    left = x
    right = x + w

    return frame[top:bottom, left:right]

def normalize_label(img, target_size=(64, 16)):
    # Resize
    resized = cv2.resize(img, target_size, interpolation=cv2.INTER_AREA)

    # Grayscale
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    # Binary threshold (automatyczny)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return thresh

def average_hash(img, hash_size=8):
    # Resize do małej siatki
    small = cv2.resize(img, (hash_size, hash_size), interpolation=cv2.INTER_AREA)

    # Średnia jasność
    avg = small.mean()

    # Tworzymy hash
    diff = small > avg

    # Zamiana na 64-bitowy string
    return ''.join(['1' if v else '0' for v in diff.flatten()])

def hamming_distance(h1, h2):
    return sum(c1 != c2 for c1, c2 in zip(h1, h2))

def find_matches(hash_value):
    matches = []

    for name, allowed_hash in ALLOWED_HASHES.items():
        dist = hamming_distance(hash_value, allowed_hash)

        if dist <= THRESHOLD:
            matches.append((name, dist))

    return matches







def random_sleep(min_s, max_s):
    time.sleep(random.uniform(min_s, max_s))

def random_click_in_radius(center_x, center_y, radius):
    angle = random.uniform(0, 2 * np.pi)
    r = random.uniform(0, radius)

    x = int(center_x + r * np.cos(angle))
    y = int(center_y + r * np.sin(angle))

    # losowy czas ruchu (bardziej ludzki)
    move_time = random.uniform(0.12, 0.35)

    # lekki overshoot (czasem)
    if random.random() < 0.3:
        overshoot_x = x + random.randint(-5, 5)
        overshoot_y = y + random.randint(-5, 5)
        pyautogui.moveTo(overshoot_x, overshoot_y,
                         duration=move_time * 0.6)
        pyautogui.moveTo(x, y,
                         duration=move_time * 0.4)
    else:
        pyautogui.moveTo(x, y, duration=move_time)

    # mikro pauza przed kliknięciem
    time.sleep(random.uniform(0.02, 0.06))

    pyautogui.click()

def random_click_not_center(screen_w, screen_h, min_radius=50, max_radius=400):
    cx = screen_w // 2
    cy = screen_h // 2

    while True:
        angle = random.uniform(0, 2 * np.pi)
        r = random.uniform(min_radius, max_radius)

        x = int(cx + r * np.cos(angle))
        y = int(cy + r * np.sin(angle))

        if np.hypot(x - cx, y - cy) > 50:
            break

    pyautogui.moveTo(x, y, duration=random.uniform(0.1, 0.2))
    pyautogui.click()

def slight_random_mouse_move():
    dx = random.randint(-4, 4)
    dy = random.randint(-4, 4)
    pyautogui.moveRel(dx, dy, duration=random.uniform(0.05, 0.15))



def random_click_on_color(frame, center_x, center_y,
                          min_radius, max_radius,
                          lower_hsv, upper_hsv,
                          max_attempts=30):

    h, w = frame.shape[:2]
    hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    for attempt in range(max_attempts):

        angle = random.uniform(0, 2 * np.pi)
        r = random.uniform(min_radius, max_radius)

        x = int(center_x + r * np.cos(angle))
        y = int(center_y + r * np.sin(angle))

        if x < 0 or y < 0 or x >= w or y >= h:
            continue

        pixel = hsv_frame[y, x]

        if np.all(pixel >= lower_hsv) and np.all(pixel <= upper_hsv):

            pyautogui.moveTo(
                x,
                y,
                duration=random.uniform(0.12, 0.3)
            )

            time.sleep(random.uniform(0.02, 0.05))
            pyautogui.click()

            return True

        # krótkie opóźnienie przed kolejną próbą
        time.sleep(random.uniform(0.03, 0.08))

    # jeśli nie znalazł
    return False



def main():
    previous_state = None
    attack_lock_until = 0
    attack_start_time = None

    with mss() as sct:
        monitor = sct.monitors[1]

        # ✅ policz raz środek ekranu
        screen_w = monitor["width"]
        screen_h = monitor["height"]
        screen_left = monitor["left"]
        screen_top = monitor["top"]

        center_x = screen_left + screen_w // 2
        center_y = screen_top + screen_h // 2

        try:
            while True:
                screenshot = sct.grab(monitor)
                frame = np.array(screenshot)
                frame = frame[:, :, :3]
                frame = frame.copy()

                # ===== DEATH ROI =====
                death_roi = extract_fixed_roi(frame, 750, 500, 820, 530)

                LOWER_BLACK = np.array([0, 0, 0])
                UPPER_BLACK = np.array([0, 0, 0])

                is_dead, _ = detect_color_presence(
                    death_roi,
                    LOWER_BLACK,
                    UPPER_BLACK,
                    min_pixels=2050
                )

                # ===== ATTACK ROI =====
                attack_roi = extract_fixed_roi(frame, 277, 250, 450, 277)
	
                LOWER_BG = np.array([95, 180, 40])
                UPPER_BG = np.array([110, 255, 120])

                hsv = cv2.cvtColor(attack_roi, cv2.COLOR_BGR2HSV)
                mask = cv2.inRange(hsv, LOWER_BG, UPPER_BG)

                pixel_count = cv2.countNonZero(mask)

                # 🔥 logika odwrócona
                if pixel_count >= 1:
                    is_attacking = False
                    print(f"Not attacking, searching for npc")
                else:
                    is_attacking = True

                roi_frame = apply_elliptical_roi(frame, 0.223, 0.27)
                boxes, _ = detect_green_bars(roi_frame)

                # ===== STATE LOGIC =====
                if is_dead:
                    current_state = "DEAD"
                    attack_start_time = None
                elif is_attacking:
                    if previous_state != "ATTACKING":
                        attack_start_time = time.time()

                        current_state = "ATTACKING"
                else:
                    current_state = "SEARCHING"
                    attack_start_time = None

                if current_state != previous_state:
                    previous_state = current_state


                # 🔴 przerwanie klawiszem Q
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("Zatrzymano program.")
                    break





                if current_state == "DEAD":
                    print("Dead, Respawning...")

                    random_sleep(1, 7)
                    random_click_in_radius(1071, 590, 30)

                    random_sleep(0.2, 0.28)
                
                    pyautogui.press('9')
                    print("Using Light of Tortuga")
                
                    time.sleep(1)

                    continue

                if current_state == "ATTACKING":

                    elapsed = time.time() - attack_start_time

                    minutes = int(elapsed // 60)
                    seconds = int(elapsed % 60)

                    print(f"Cannon fire continues... {minutes:02d}:{seconds:02d}")

                    if elapsed > 240:  # 4 minuty
                        print("Attack timeout (4 min). Switching to SEARCHING.")
                        current_state = "SEARCHING"
                        attack_start_time = None
                        continue

                    time.sleep(6)
                    continue

                if current_state == "SEARCHING":

                    valid_targets = []

                    for (x, y, w, h) in boxes:
                        label_img = extract_label_region(roi_frame, x, y, w, h)

                        if label_img.size == 0:
                            continue

                        normalized = normalize_label(label_img)
                        hash_value = average_hash(normalized)
                        matches = find_matches(hash_value)

                        if matches:
                            valid_targets.append((x, y, w, h))

                    if valid_targets:
                        x, y, w, h = random.choice(valid_targets)

                        monitor_left = monitor["left"]
                        monitor_top = monitor["top"]

                        local_x = x + w // 2
                        local_y = y + h // 2

                        target_x = monitor_left + local_x
                        target_y = monitor_top + local_y
                
                        attack_x = target_x
                        attack_y = target_y - 48

                        random_sleep(0.05, 0.1)

                        pyautogui.moveTo(
                            attack_x,
                            attack_y,
                            duration=random.uniform(0.1, 0.25)
                        )
                        random_click_in_radius(attack_x, attack_y,
                                               random.uniform(0, 2))

                        time.sleep(random.uniform(0.02, 0.05))
                        pyautogui.press('P')
                        print(f"Target acquired!")

                        random_sleep(0.05, 0.1)

                        random_click_in_radius(center_x, center_y,
                                               random.uniform(40, 60))

                        random_sleep(1, 3.5)

                        random_click_in_radius(center_x, center_y,
                                               random.uniform(100, 300))

                        current_state = "ATTACKING"
                        attack_lock_until = time.time() + random.uniform(1.8, 2.5)
                        continue

                    else:
                        success = random_click_on_color(
                            frame,
                            center_x,
                            center_y,
                            min_radius=150,
                            max_radius=300,
                            lower_hsv=LOWER_BG,
                            upper_hsv=UPPER_BG,
                            max_attempts=30
                        )

                        if not success:
                            print("Nie znaleziono koloru po 30 próbach. Zatrzymuję program.")
                            break

                        random_sleep(3, 4)
                        continue





                time.sleep(0.2)

        except KeyboardInterrupt:
            print("Zatrzymano program (Ctrl+C).")

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()