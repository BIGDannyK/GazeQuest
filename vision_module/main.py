import cv2
import numpy as np
import urllib.request
import os
import mediapipe as mp
import time
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# 1. 모델 설정
model_path = 'face_landmarker.task'
if not os.path.exists(model_path):
    url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
    urllib.request.urlretrieve(url, model_path)

base_options = python.BaseOptions(model_asset_path=model_path)
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    output_face_blendshapes=False,
    output_facial_transformation_matrixes=False,
    num_faces=1
)
detector = vision.FaceLandmarker.create_from_options(options)

# --- 설정 변수 ---
is_calibrated = False
calib_tl, calib_br = None, None
warning_msg, warning_timer = "", 0

# 벡터 이동 관련
dot_x, dot_y = 0.5, 0.5
MOVE_SPEED = 0.012      
DEADZONE = 0.20         

# 제스처(입 벌리기) 관련
is_locked = False           # 현재 커서가 고정되었는지 여부
mouth_cooldown = 0          # 입 벌림 중복 인식 방지 타이머
MOUTH_THRESHOLD = 0.04      # 입 벌림 감지 임계값 (거리가 이보다 크면 인식)

# 시선 값 부드럽게 (떨림 방지)
raw_smoothed_x, raw_smoothed_y = 0.5, 0.5
ALPHA = 0.2             

last_print_time = 0
PRINT_INTERVAL = 0.5 

cap = cv2.VideoCapture(0)
window_name = "GazeQuest - Mouth Gesture Lock"

while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break

    frame = cv2.flip(frame, 1) 
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    detection_result = detector.detect(mp_image)
    h, w, _ = frame.shape
    current_iris_x, current_iris_y = 0, 0

    if detection_result.face_landmarks:
        face_landmarks = detection_result.face_landmarks[0]
        
        # 1. 눈동자 위치 파악
        left_iris = face_landmarks[468]
        current_iris_x = int(left_iris.x * w)
        current_iris_y = int(left_iris.y * h)
        cv2.circle(frame, (current_iris_x, current_iris_y), 3, (0, 255, 0), -1)

        # 2. 입 벌리기 제스처 감지 (랜드마크 13: 윗입술 안쪽, 14: 아랫입술 안쪽)
        upper_lip = face_landmarks[13]
        lower_lip = face_landmarks[14]
        mouth_dist = abs(upper_lip.y - lower_lip.y)

        if mouth_dist > MOUTH_THRESHOLD and mouth_cooldown == 0:
            is_locked = not is_locked  # 상태 반전 (토글)
            mouth_cooldown = 20        # 약 0.6~1초간 쿨타임 (연속 인식 방지)
            warning_msg = "CURSOR LOCKED" if is_locked else "CURSOR UNLOCKED"
            warning_timer = 60

        if mouth_cooldown > 0:
            mouth_cooldown -= 1

    # UI 알림 표시
    if warning_timer > 0:
        msg_color = (0, 0, 255) if is_locked else (0, 255, 0)
        cv2.putText(frame, warning_msg, (w//2 - 100, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, msg_color, 2)
        warning_timer -= 1

    # --- Step 1: Calibration ---
    if not is_calibrated:
        if calib_tl is None:
            cv2.putText(frame, "1. Look TOP-LEFT and press '1'", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        elif calib_br is None:
            cv2.putText(frame, "2. Look BOTTOM-RIGHT and press '2'", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.rectangle(frame, (calib_tl[0]-5, calib_tl[1]-5), (calib_tl[0]+5, calib_tl[1]+5), (255, 0, 0), 2)
            
    # --- Step 2: Vector Tracking ---
    else:
        if current_iris_x != 0 and current_iris_y != 0:
            # 1. 시선 좌표 정규화 및 필터링
            target_raw_x = np.interp(current_iris_x, [calib_tl[0], calib_br[0]], [0.0, 1.0])
            target_raw_y = np.interp(current_iris_y, [calib_tl[1], calib_br[1]], [0.0, 1.0])
            raw_smoothed_x = ALPHA * target_raw_x + (1 - ALPHA) * raw_smoothed_x
            raw_smoothed_y = ALPHA * target_raw_y + (1 - ALPHA) * raw_smoothed_y

            # 2. 벡터 결정
            vx, vy = 0, 0
            if raw_smoothed_x < (0.5 - DEADZONE):   vx = -1
            elif raw_smoothed_x > (0.5 + DEADZONE): vx = 1
            if raw_smoothed_y < (0.5 - DEADZONE):   vy = -1
            elif raw_smoothed_y > (0.5 + DEADZONE): vy = 1

            # 3. [핵심] 고정 상태가 아닐 때만 점 이동
            if not is_locked:
                dot_x = np.clip(dot_x + vx * MOVE_SPEED, 0.0, 1.0)
                dot_y = np.clip(dot_y + vy * MOVE_SPEED, 0.0, 1.0)

            # --- 시각적 피드백 ---
            # 데드존 가이드
            dz_x1, dz_y1 = int(w*(0.5-DEADZONE)), int(h*(0.5-DEADZONE))
            dz_x2, dz_y2 = int(w*(0.5+DEADZONE)), int(h*(0.5+DEADZONE))
            cv2.rectangle(frame, (dz_x1, dz_y1), (dz_x2, dz_y2), (255, 255, 255), 1)
            
            # 현재 시선 표시 (청록색 점)
            cv2.circle(frame, (int(raw_smoothed_x * w), int(raw_smoothed_y * h)), 5, (255, 255, 0), -1)

            # 최종 빨간 점 (고정 시 색상 변경)
            dot_color = (100, 100, 100) if is_locked else (0, 0, 255)
            cv2.circle(frame, (int(dot_x * w), int(dot_y * h)), 15, dot_color, -1)
            
            # 상태 표시
            state_text = "LOCKED (Open mouth to unlock)" if is_locked else f"MOVING ({vx}, {vy})"
            status_color = (0, 0, 255) if is_locked else (0, 255, 0)
            cv2.putText(frame, f"STATUS: {state_text}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)

            # 터미널 로그
            current_time = time.time()
            if current_time - last_print_time >= PRINT_INTERVAL:
                lock_status = "LOCKED" if is_locked else "ACTIVE"
                print(f"[{lock_status}] Dot:({dot_x:.2f}, {dot_y:.2f}) | MouthDist: {mouth_dist:.3f}")
                last_print_time = current_time

    cv2.imshow(window_name, frame)

    key = cv2.waitKey(1) & 0xFF
    if key == 27 or cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
        break
    elif key == ord('r') or key == ord('R'):
        is_calibrated = False
        is_locked = False
        calib_tl, calib_br = None, None
        dot_x, dot_y = 0.5, 0.5
        warning_msg, warning_timer = "RESET ALL!", 60
    elif key == ord('1') and detection_result.face_landmarks:
        calib_tl = (current_iris_x, current_iris_y)
        warning_msg, warning_timer = "Point 1 Saved!", 60
    elif key == ord('2') and calib_tl is not None and detection_result.face_landmarks:
        calib_br = (current_iris_x, current_iris_y)
        is_calibrated = True

cap.release()
cv2.destroyAllWindows()