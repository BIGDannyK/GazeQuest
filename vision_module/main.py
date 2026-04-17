import cv2
import numpy as np
import urllib.request
import os
import mediapipe as mp
import time
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# --- 1. 모델 설정 및 다운로드 ---
model_path = 'face_landmarker.task'
if not os.path.exists(model_path):
    print("모델 다운로드 중...")
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

# --- 2. 설정 변수 및 상태 ---
is_calibrated = False
calib_tl, calib_br = None, None
warning_msg, warning_timer = "", 0

# 벡터 이동 관련
dot_x, dot_y = 0.5, 0.5
MOVE_SPEED = 0.012      
DEADZONE = 0.30         

# 제스처(입 벌리기) 관련
is_locked = False           # 현재 커서가 고정되었는지 여부
mouth_cooldown = 0          # 입 벌림 중복 인식 방지 타이머
MOUTH_THRESHOLD = 0.04      # 입 벌림 감지 임계값

# 시선 값 부드럽게 (떨림 방지)
raw_smoothed_x, raw_smoothed_y = 0.5, 0.5
ALPHA = 0.2             

last_print_time = 0
PRINT_INTERVAL = 0.5 

# --- 3. 윈도우 설정 (창 크기 조절 가능하게) ---
window_name = "GazeQuest - Mouth Gesture Lock"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL) 

cap = cv2.VideoCapture(0)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break

    frame = cv2.flip(frame, 1) 
    h, w, _ = frame.shape
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    detection_result = detector.detect(mp_image)
    
    current_iris_x, current_iris_y = 0, 0

    if detection_result.face_landmarks:
        face_landmarks = detection_result.face_landmarks[0]
        
        # [랜드마크 추출] 눈동자 위치 (468: 왼쪽 눈동자 중심)
        left_iris = face_landmarks[468]
        current_iris_x = int(left_iris.x * w)
        current_iris_y = int(left_iris.y * h)
        cv2.circle(frame, (current_iris_x, current_iris_y), 3, (0, 255, 0), -1)

        # [제스처 감지] 입 벌리기 (13: 상순, 14: 하순)
        upper_lip = face_landmarks[13]
        lower_lip = face_landmarks[14]
        mouth_dist = abs(upper_lip.y - lower_lip.y)

        if mouth_dist > MOUTH_THRESHOLD and mouth_cooldown == 0:
            is_locked = not is_locked
            mouth_cooldown = 20
            warning_msg = "CURSOR LOCKED" if is_locked else "CURSOR UNLOCKED"
            warning_timer = 60

        if mouth_cooldown > 0:
            mouth_cooldown -= 1

    # --- Step 1: Calibration (캘리브레이션 시각화) ---
    if not is_calibrated:
        if calib_tl is None:
            cv2.putText(frame, "1. Look TOP-LEFT and press '1'", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        elif calib_br is None:
            cv2.putText(frame, "2. Look BOTTOM-RIGHT and press '2'", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.rectangle(frame, (calib_tl[0]-5, calib_tl[1]-5), (calib_tl[0]+5, calib_tl[1]+5), (255, 0, 0), 2)
            
    # --- Step 2: Vector Tracking ---
    else:
        if current_iris_x != 0 and current_iris_y != 0:
            # 시선 좌표 정규화 및 필터링
            target_raw_x = np.interp(current_iris_x, [calib_tl[0], calib_br[0]], [0.0, 1.0])
            target_raw_y = np.interp(current_iris_y, [calib_tl[1], calib_br[1]], [0.0, 1.0])
            raw_smoothed_x = ALPHA * target_raw_x + (1 - ALPHA) * raw_smoothed_x
            raw_smoothed_y = ALPHA * target_raw_y + (1 - ALPHA) * raw_smoothed_y

            # 벡터 결정
            vx, vy = 0, 0
            if raw_smoothed_x < (0.5 - DEADZONE):   vx = -1
            elif raw_smoothed_x > (0.5 + DEADZONE): vx = 1
            if raw_smoothed_y < (0.5 - DEADZONE):   vy = -1
            elif raw_smoothed_y > (0.5 + DEADZONE): vy = 1

            # 고정 상태가 아닐 때만 점 이동
            if not is_locked:
                dot_x = np.clip(dot_x + vx * MOVE_SPEED, 0.0, 1.0)
                dot_y = np.clip(dot_y + vy * MOVE_SPEED, 0.0, 1.0)

            # --- 시각적 피드백 ---
            # 데드존 가이드
            dz_x1, dz_y1 = int(w*(0.5-DEADZONE)), int(h*(0.5-DEADZONE))
            dz_x2, dz_y2 = int(w*(0.5+DEADZONE)), int(h*(0.5+DEADZONE))
            cv2.rectangle(frame, (dz_x1, dz_y1), (dz_x2, dz_y2), (255, 255, 255), 1)
            
            # 현재 시선 표시 (청록색)
            cv2.circle(frame, (int(raw_smoothed_x * w), int(raw_smoothed_y * h)), 5, (255, 255, 0), -1)

            # 최종 빨간 점 (고정 시 주황색)
            dot_color = (0 ,165, 255) if is_locked else (0, 0, 255)
            cv2.circle(frame, (int(dot_x * w), int(dot_y * h)), 15, dot_color, -1)
            
            # 상태 정보 텍스트
            state_text = "LOCKED (Open mouth to unlock)" if is_locked else f"MOVING ({vx}, {vy})"
            status_color = (0, 0, 255) if is_locked else (0, 255, 0)
            cv2.putText(frame, f"STATUS: {state_text}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)

            # 터미널 로그
            current_time = time.time()
            if current_time - last_print_time >= PRINT_INTERVAL:
                lock_status = "LOCKED" if is_locked else "ACTIVE"
                print(f"[{lock_status}] Dot:({dot_x:.2f}, {dot_y:.2f}) | MouthDist: {mouth_dist:.3f}")
                last_print_time = current_time

    # UI 상단 경고 메시지
    if warning_timer > 0:
        msg_color = (0, 0, 255) if is_locked else (0, 255, 0)
        cv2.putText(frame, warning_msg, (w//2 - 100, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, msg_color, 2)
        warning_timer -= 1

    # --- [핵심] 창 크기에 맞춰 영상 리사이징 ---
    # 현재 활성화된 창의 크기를 가져옵니다.
    rect = cv2.getWindowImageRect(window_name)
    if rect is not None and rect[2] > 0 and rect[3] > 0:
        win_w, win_h = rect[2], rect[3]
        # 창 크기에 맞게 프레임을 리사이즈하여 출력 (전체 화면 대응)
        display_frame = cv2.resize(frame, (win_w, win_h), interpolation=cv2.INTER_LINEAR)
        cv2.imshow(window_name, display_frame)
    else:
        cv2.imshow(window_name, frame)

    # --- 키 입력 처리 ---
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