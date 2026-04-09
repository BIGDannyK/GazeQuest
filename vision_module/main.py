import cv2
import numpy as np
import urllib.request
import os
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# 1. 모델 다운로드 및 설정
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

# 변수 초기화
is_calibrated = False
calib_tl = None
calib_br = None
warning_msg = ""
warning_timer = 0

smoothed_x, smoothed_y = None, None
ALPHA = 0.1 

# 3. 웹캠 실행
cap = cv2.VideoCapture(0)
window_name = "GazeQuest - Advanced Tracking"

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

    # --- [UI: 에러 및 안내 메시지 표시] ---
    if warning_timer > 0:
        cv2.putText(frame, warning_msg, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
        warning_timer -= 1
        
    cv2.putText(frame, "Press 'R' anytime to RESET", (w - 250, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    # --- [Step 1: Calibration] ---
    if not is_calibrated:
        if calib_tl is None:
            cv2.putText(frame, "1. Look TOP-LEFT and press '1'", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        elif calib_br is None:
            cv2.putText(frame, "2. Look BOTTOM-RIGHT and press '2'", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            
            # 1번 점이 찍혀있다면 파란색 네모와 글씨로 시각적 피드백 제공!
            cv2.rectangle(frame, (calib_tl[0]-5, calib_tl[1]-5), (calib_tl[0]+5, calib_tl[1]+5), (255, 0, 0), 2)
            cv2.putText(frame, "TL Anchor", (calib_tl[0]+10, calib_tl[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
            
    # --- [Step 2: Tracking] ---
    else:
        cv2.putText(frame, "Calibration DONE! Look around.", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        if current_iris_x != 0 and current_iris_y != 0:
            raw_x = np.interp(current_iris_x, [calib_tl[0], calib_br[0]], [0.0, 1.0])
            raw_y = np.interp(current_iris_y, [calib_tl[1], calib_br[1]], [0.0, 1.0])

            if smoothed_x is None:
                smoothed_x, smoothed_y = raw_x, raw_y
            else:
                smoothed_x = ALPHA * raw_x + (1 - ALPHA) * smoothed_x
                smoothed_y = ALPHA * raw_y + (1 - ALPHA) * smoothed_y

            screen_cursor_x = int(smoothed_x * w)
            screen_cursor_y = int(smoothed_y * h)
            
            cv2.circle(frame, (screen_cursor_x, screen_cursor_y), 10, (0, 0, 255), -1)
            cv2.putText(frame, f"Unity X:{smoothed_x:.2f}, Y:{smoothed_y:.2f}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

    cv2.imshow(window_name, frame)

    # --- [이벤트 처리] ---
    key = cv2.waitKey(1) & 0xFF
    if key == 27 or cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
        break
    
    # R 키를 누르면 전체 리셋
    elif key == ord('r') or key == ord('R'):
        is_calibrated = False
        calib_tl = None
        calib_br = None
        smoothed_x, smoothed_y = None, None
        warning_msg = "Calibration RESET! Start over."
        warning_timer = 60
        print("초기화되었습니다. 다시 1번부터 세팅하세요.")

    elif key == ord('1') and detection_result.face_landmarks:
        calib_tl = (current_iris_x, current_iris_y)
        print("좌상단 좌표 저장:", calib_tl)
        warning_msg = "Point 1 Saved! (Press 1 again if wrong)"
        warning_timer = 60
        
    elif key == ord('2') and calib_tl is not None and detection_result.face_landmarks:
        dx = current_iris_x - calib_tl[0]
        dy = current_iris_y - calib_tl[1]
        
        if abs(dx) < 3 or abs(dy) < 3:
            warning_msg = "Error: Too little movement! Move eyes more."
            warning_timer = 90
        elif dx < 0 or dy < 0:
            warning_msg = "Error: Wrong direction! Look BOTTOM-RIGHT."
            warning_timer = 90
        else:
            calib_br = (current_iris_x, current_iris_y)
            is_calibrated = True
            print("우하단 좌표 저장 완료! 게임 시작.")

cap.release()
cv2.destroyAllWindows()
