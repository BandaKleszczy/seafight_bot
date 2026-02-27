import numpy as np
import cv2
from mss import mss
import pyautogui
import time

THRESHOLD = 5  # maksymalny dystans Hamming

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

        print(f"Contour: w={w}, h={h}, ratio={ratio:.2f}")
        print("Detected:", w, h)
        print("Width:", w)

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


def main():
    with mss() as sct:
        monitor = sct.monitors[1]  # <-- to MUSI być

        screenshot = sct.grab(monitor)
        frame = np.array(screenshot)
        frame = frame[:, :, :3]  # usuń kanał alfa
        frame = frame.copy()     # wymuś poprawny layout pamięci

        previous_state = None

        # ====== DEATH SCREEN ROI (przykładowe współrzędne) ======
        death_roi = extract_fixed_roi(frame, 750, 500, 820, 530)

        # Zakres koloru (czarny)
        LOWER_BLACK = np.array([0, 0, 0])
        UPPER_BLACK = np.array([0, 0, 0])
        
        is_dead, pixel_count = detect_color_presence(
            death_roi,
            LOWER_BLACK,
            UPPER_BLACK,
            min_pixels=2050
        )

        # ====== ATTACK ICON ROI (inne współrzędne) ======
        attack_roi = extract_fixed_roi(frame, 299, 265, 305, 273)
        
        LOWER_GREEN_ICON = np.array([45, 60, 20])
        UPPER_GREEN_ICON = np.array([85, 255, 200])

        is_attacking, pixel_count = detect_color_presence(
            attack_roi,
            LOWER_GREEN_ICON,
            UPPER_GREEN_ICON,
            min_pixels=40
        )

        roi_frame = apply_elliptical_roi(frame, 0.223, 0.27)
        boxes, mask = detect_green_bars(roi_frame)

        for i, (x, y, w, h) in enumerate(boxes):
            cv2.rectangle(roi_frame, (x, y), (x+w, y+h), (0, 0, 255), 2)

            label_img = extract_label_region(roi_frame, x, y, w, h)

            if label_img.size > 0:
                normalized = normalize_label(label_img)
                hash_value = average_hash(normalized)

                print(f"Label {i} hash:", hash_value)

                matches = find_matches(hash_value)

                if matches:
                    print(f"Label {i}: {len(matches)} match(es)")
                    for name, dist in matches:
                        print(f"   -> {name} (distance={dist})")
                else:
                    print(f"Label {i}: no match")

                cv2.imwrite(f"label_{i}.png", normalized)

        cv2.imwrite("output.png", roi_frame)
        cv2.imwrite("mask.png", mask)

        print(f"Znaleziono {len(boxes)} potencjalnych pasków.")
        print("Zapisano pliki: output.png i mask.png")
        
        if is_dead:
            current_state = "DEAD"
        elif is_attacking:
            current_state = "ATTACKING"
        else:
            current_state = "SEARCHING"

        if current_state != previous_state:
            print(f"STATE = {current_state}")
            previous_state = current_state

if __name__ == "__main__":
    main()