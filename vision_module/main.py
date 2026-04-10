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
MOVE_SPEED = 0.012      # 점이 흐르는 속도
DEADZONE = 0.20         # 멈춤 범위 확장 (0.15 -> 0.20)

# 시선 값 부드럽게 (떨림 방지)
raw_smoothed_x, raw_smoothed_y = 0.5, 0.5
ALPHA = 0.2             # 시선 필터링 계수

last_print_time = 0
PRINT_INTERVAL = 0.5 

cap = cv2.VideoCapture(0)
window_name = "GazeQuest - Vector Control (Large Deadzone)"

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
        left_iris = face_landmarks[468]
        current_iris_x = int(left_iris.x * w)
        current_iris_y = int(left_iris.y * h)
        cv2.circle(frame, (current_iris_x, current_iris_y), 3, (0, 255, 0), -1)

    # UI 알림 표시
    if warning_timer > 0:
        cv2.putText(frame, warning_msg, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
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
            # 1. 시선 좌표 정규화 (0.0 ~ 1.0)
            target_raw_x = np.interp(current_iris_x, [calib_tl[0], calib_br[0]], [0.0, 1.0])
            target_raw_y = np.interp(current_iris_y, [calib_tl[1], calib_br[1]], [0.0, 1.0])
            
            # 2. 노이즈 필터링
            raw_smoothed_x = ALPHA * target_raw_x + (1 - ALPHA) * raw_smoothed_x
            raw_smoothed_y = ALPHA * target_raw_y + (1 - ALPHA) * raw_smoothed_y

            # 3. 벡터 결정 (0.5 - DEADZONE ~ 0.5 + DEADZONE 사이면 0)
            vx, vy = 0, 0
            if raw_smoothed_x < (0.5 - DEADZONE):   vx = -1
            elif raw_smoothed_x > (0.5 + DEADZONE): vx = 1
            
            if raw_smoothed_y < (0.5 - DEADZONE):   vy = -1
            elif raw_smoothed_y > (0.5 + DEADZONE): vy = 1

            # 4. 빨간 점 위치 업데이트 및 경계 제한
            dot_x = np.clip(dot_x + vx * MOVE_SPEED, 0.0, 1.0)
            dot_y = np.clip(dot_y + vy * MOVE_SPEED, 0.0, 1.0)

            # --- 시각적 피드백 ---
            # 하얀 사각형: 멈춤 구간 (DEADZONE) 시각화
            dz_x1, dz_y1 = int(w*(0.5-DEADZONE)), int(h*(0.5-DEADZONE))
            dz_x2, dz_y2 = int(w*(0.5+DEADZONE)), int(h*(0.5+DEADZONE))
            cv2.rectangle(frame, (dz_x1, dz_y1), (dz_x2, dz_y2), (255, 255, 255), 1)
            
            # 청록색 점: 현재 내 시선 위치
            cv2.circle(frame, (int(raw_smoothed_x * w), int(raw_smoothed_y * h)), 5, (255, 255, 0), -1)

            # 빨간 큰 점: 조종되는 결과물
            cv2.circle(frame, (int(dot_x * w), int(dot_y * h)), 15, (0, 0, 255), -1)
            
            # 상태 정보 표시
            is_stopped = (vx == 0 and vy == 0)
            state_text = "STOPPED" if is_stopped else f"MOVING ({vx}, {vy})"
            color = (0, 255, 0) if is_stopped else (0, 165, 255)
            cv2.putText(frame, f"STATUS: {state_text}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            # 터미널 로그 출력
            current_time = time.time()
            if current_time - last_print_time >= PRINT_INTERVAL:
                print(f"[{state_text}] Dot:({dot_x:.2f}, {dot_y:.2f}) | Gaze:({raw_smoothed_x:.2f}, {raw_smoothed_y:.2f})")
                last_print_time = current_time

    cv2.imshow(window_name, frame)

    key = cv2.waitKey(1) & 0xFF
    if key == 27 or cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
        break
    elif key == ord('r') or key == ord('R'):
        is_calibrated = False
        calib_tl, calib_br = None, None
        dot_x, dot_y = 0.5, 0.5
        warning_msg, warning_timer = "RESET ALL!", 60
    elif key == ord('1') and detection_result.face_landmarks:
        calib_tl = (current_iris_x, current_iris_y)
        warning_msg, warning_timer = "Point 1 Saved!", 60
    elif key == ord('2') and calib_tl is not None and detection_result.face_landmarks:
        calib_br = (current_iris_x, current_iris_y)
        is_calibrated = True
        print("Calibration Complete!")

cap.release()
cv2.destroyAllWindows()