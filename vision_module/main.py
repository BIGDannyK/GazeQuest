import cv2
import numpy as np
import urllib.request
import os
import mediapipe as mp
import time
import pyautogui
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# ─────────────────────────────────────────────
#  PYAUTOGUI SETUP (마우스 제어 설정)
# ─────────────────────────────────────────────
pyautogui.FAILSAFE = False  # 화면 모서리 강제 종료 방지
SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()

# ─────────────────────────────────────────────
#  MODEL SETUP
# ─────────────────────────────────────────────
model_path = 'face_landmarker.task'
if not os.path.exists(model_path):
    print("모델 다운로드 중...")
    url = ("https://storage.googleapis.com/mediapipe-models/"
           "face_landmarker/face_landmarker/float16/1/face_landmarker.task")
    urllib.request.urlretrieve(url, model_path)

base_options = python.BaseOptions(model_asset_path=model_path)
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    output_face_blendshapes=False,
    output_facial_transformation_matrixes=False,
    num_faces=1
)
detector = vision.FaceLandmarker.create_from_options(options)

# ─────────────────────────────────────────────
#  ONE EURO FILTER (시선 떨림 방지)
# ─────────────────────────────────────────────
class OneEuroFilter:
    def __init__(self, freq=30.0, min_cutoff=0.8, beta=0.06, d_cutoff=1.0):
        self.freq       = freq
        self.min_cutoff = min_cutoff
        self.beta       = beta
        self.d_cutoff   = d_cutoff
        self.x_prev     = None
        self.dx_prev     = 0.0
        self.t_prev     = None

    def _alpha(self, cutoff):
        tau = 1.0 / (2 * np.pi * cutoff)
        te  = 1.0 / self.freq
        return 1.0 / (1.0 + tau / te)

    def filter(self, x, timestamp=None):
        if self.x_prev is None:
            self.x_prev = x
            self.t_prev = timestamp
            return x
        if timestamp is not None and self.t_prev is not None:
            dt = timestamp - self.t_prev
            if dt > 0:
                self.freq = 1.0 / dt
            self.t_prev = timestamp
        dx      = (x - self.x_prev) * self.freq
        a_d     = self._alpha(self.d_cutoff)
        dx_hat  = a_d * dx + (1 - a_d) * self.dx_prev
        cutoff  = self.min_cutoff + self.beta * abs(dx_hat)
        a       = self._alpha(cutoff)
        x_hat   = a * x + (1 - a) * self.x_prev
        self.x_prev  = x_hat
        self.dx_prev = dx_hat
        return x_hat

    def reset(self):
        self.x_prev  = None
        self.dx_prev = 0.0
        self.t_prev  = None


# ─────────────────────────────────────────────
#  5-POINT CALIBRATION (기준점 매핑 기능 완전 복원)
# ─────────────────────────────────────────────
MARGIN = 0.08

CALIB_TARGETS = [
    (MARGIN,       MARGIN      ),   # 0 좌상단
    (1 - MARGIN,   MARGIN      ),   # 1 우상단
    (0.5,          0.5         ),   # 2 중앙
    (MARGIN,       1 - MARGIN  ),   # 3 좌하단
    (1 - MARGIN,   1 - MARGIN  ),   # 4 우하단
]

CALIB_LABELS = [
    "TOP-LEFT",
    "TOP-RIGHT",
    "CENTER",
    "BOTTOM-LEFT",
    "BOTTOM-RIGHT",
]

CALIB_SAMPLES = 20   # 포인트당 누적할 카메라 프레임 수


class Calibration:
    def __init__(self):
        self.reset()

    def reset(self):
        self.step           = 0
        self.iris_pts       = []
        self.sample_buf     = []
        self.M              = None
        self.ready          = False  # 초기 구동 시 완료 상태가 아님 (창 오픈 필항)
        self.neutral_nose_x = None
        self.neutral_nose_y = None

    @property
    def done(self):
        return self.ready

    def current_target_px(self, frame_w, frame_h):
        if self.step >= len(CALIB_TARGETS):
            return None
        tx, ty = CALIB_TARGETS[self.step]
        return int(tx * frame_w), int(ty * frame_h)

    def add_sample(self, ix, iy):
        self.sample_buf.append((ix, iy))

    def confirm_point(self, lms=None):
        if not self.sample_buf:
            return False
        avg_x = float(np.mean([s[0] for s in self.sample_buf]))
        avg_y = float(np.mean([s[1] for s in self.sample_buf]))
        self.iris_pts.append((avg_x, avg_y))
        if self.step == 0 and lms is not None:
            self.neutral_nose_x = lms[1].x - lms[6].x
            self.neutral_nose_y = lms[1].y - lms[6].y
        self.sample_buf = []
        self.step += 1
        if self.step >= len(CALIB_TARGETS):
            self._fit()
        return True

    def _fit(self):
        # 5가지 타겟 홍채 입력점들과 실제 정규화 모니터 비율 목적지 간의 아핀 변환 최소자승법 연산
        src = np.array([[ix, iy, 1.0] for ix, iy in self.iris_pts], dtype=np.float64)
        dst = np.array(list(CALIB_TARGETS),                         dtype=np.float64)
        M_T, _, _, _ = np.linalg.lstsq(src, dst, rcond=None)
        self.M     = M_T.T   # 변환 행렬 형태 결정 (shape: 2x3)
        self.ready = True

    def map(self, ix, iy):
        if self.M is None:
            return ix, iy
        v = np.array([ix, iy, 1.0])
        r = self.M @ v
        return float(r[0]), float(r[1])


# ─────────────────────────────────────────────
#  HEAD POSE COMPENSATION (머리 움직임 보정)
# ─────────────────────────────────────────────
HEAD_COMP_SCALE = 0.55

def get_head_offset(lms, calib):
    if calib.neutral_nose_x is None:
        return 0.0, 0.0
    nx = (lms[1].x - lms[6].x) - calib.neutral_nose_x
    ny = (lms[1].y - lms[6].y) - calib.neutral_nose_y
    return nx * HEAD_COMP_SCALE, ny * HEAD_COMP_SCALE


# ─────────────────────────────────────────────
#  SETTINGS
# ─────────────────────────────────────────────
MOUTH_THRESHOLD  = 0.04
MOUTH_CD_MAX     = 20
WIN_W, WIN_H     = 960, 720
MIN_SMOOTHING    = 0.01  # 거리가 가까울 때의 최저 속도 (정밀도 유지)
MAX_SMOOTHING    = 0.15  # 거리가 멀 때의 최고 속도 (빠른 이동 보장)
MIN_DISTANCE     = 150.0
MAX_DISTANCE   = 400.0 # 마우스가 최고 속도에 도달하기 위한 타겟과의 픽셀 거리 (이보다 멀면 최고속도)



# ─────────────────────────────────────────────
#  CALIBRATION DRAWING HELPER
# ─────────────────────────────────────────────
def draw_calib_screen(frame, calib, sampling_active, w, h):
    tgt = calib.current_target_px(w, h)
    if tgt is None:
        return
    tx, ty    = tgt
    label     = CALIB_LABELS[calib.step]
    progress  = len(calib.sample_buf) / CALIB_SAMPLES if sampling_active else 0.0

    if sampling_active:
        guide = f"Step {calib.step+1}/5: Sampling {label} ...  (hold still)"
        g_col = (0, 220, 100)
    else:
        guide = f"Step {calib.step+1}/5: Look at {label}  ->  press SPACE"
        g_col = (0, 200, 255)
    cv2.putText(frame, guide, (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.62, g_col, 2)

    cv2.circle(frame, (tx, ty), 24, (255, 255, 255), 2)
    if int(time.time() * 3) % 2 == 0:
        cv2.circle(frame, (tx, ty), 7, (0, 60, 255), -1)
    else:
        cv2.circle(frame, (tx, ty), 7, (0, 120, 255), -1)
    if progress > 0:
        cv2.ellipse(frame, (tx, ty), (24, 24), -90,
                    0, int(360 * progress), (0, 220, 100), 3)
    cv2.putText(frame, label, (tx - 40, ty + 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

    for i in range(calib.step):
        dtx = int(CALIB_TARGETS[i][0] * w)
        dty = int(CALIB_TARGETS[i][1] * h)
        cv2.circle(frame, (dtx, dty), 10, (0, 200, 80), -1)
        cv2.putText(frame, "v", (dtx - 5, dty + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

    bx, by, bw, bh = 10, h - 28, w - 20, 12
    cv2.rectangle(frame, (bx, by), (bx+bw, by+bh), (45, 45, 45), -1)
    if progress > 0:
        cv2.rectangle(frame, (bx, by), (bx + int(bw*progress), by+bh),
                      (0, 190, 70), -1)
    cv2.rectangle(frame, (bx, by), (bx+bw, by+bh), (130, 130, 130), 1)
    cv2.putText(frame, f"{int(progress*100)}%", (bx+4, by-3),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 160, 160), 1)


# ─────────────────────────────────────────────
#  MAIN HYBRID LOOP
# ─────────────────────────────────────────────
calib            = Calibration()
filter_x         = OneEuroFilter()
filter_y         = OneEuroFilter()

is_locked        = False
mouth_cooldown   = 0
sampling_active  = False
window_destroyed = False

# [추가됨] 마우스의 현재 가상 위치 (초기값은 화면 정중앙으로 설정)
current_mouse_x = SCREEN_WIDTH / 2.0
current_mouse_y = SCREEN_HEIGHT / 2.0

window_name = "GazeQuest - Calibration Mode"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

print("==================================================")
print(f" 모니터 해상도 감지: {SCREEN_WIDTH} x {SCREEN_HEIGHT}")
print(f" 최소 감도: {MIN_SMOOTHING} ~ 최대 감도: {MAX_SMOOTHING} (동적 제어)")
print(" GazeQuest 제어 시스템 모듈 구동을 시작합니다.")
print(" [1단계] GUI 화면 안내에 따라 5가지 포인트의 초점을 학습시켜 주세요.")
print("==================================================")

cap = cv2.VideoCapture(0)

try:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        now = time.time()
        frame = cv2.flip(frame, 1)
        h_cam, w_cam = frame.shape[:2]

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image  = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        detection_result = detector.detect(mp_image)

        face_ok = bool(detection_result.face_landmarks)

        if face_ok:
            lms = detection_result.face_landmarks[0]
            li, ri = lms[468], lms[473]
            iris_norm_x = (li.x + ri.x) / 2.0
            iris_norm_y = (li.y + ri.y) / 2.0

            # ─── [1단계] 캘리브레이션 모드 진행 상태 ───
            if not calib.done:
                if sampling_active:
                    calib.add_sample(iris_norm_x, iris_norm_y)
                    if len(calib.sample_buf) >= CALIB_SAMPLES:
                        calib.confirm_point(lms=lms)
                        sampling_active = False
                        
                        if calib.done:
                            print("\n==================================================")
                            print(" 캘리브레이션 매핑 행렬 피팅 완료!")
                            print(" 안내 창을 종료하고 백그라운드 절대 마우스 제어 모드로 자동 진입합니다.")
                            print(" 종료를 원하시면 터미널 창에서 Ctrl + C를 입력하세요.")
                            print("==================================================")

                # 시각 피드백 그리기 (캘리브레이션 단계에서만 렌더링)
                current_iris_x = int(iris_norm_x * w_cam)
                current_iris_y = int(iris_norm_y * h_cam)
                cv2.circle(frame, (int(li.x*w_cam), int(li.y*h_cam)), 3, (0, 255, 100), -1)
                cv2.circle(frame, (int(ri.x*w_cam), int(ri.y*h_cam)), 3, (0, 255, 100), -1)
                cv2.circle(frame, (current_iris_x, current_iris_y), 4, (0, 200, 255), -1)
                draw_calib_screen(frame, calib, sampling_active, w_cam, h_cam)

            # ─── [2단계] 캘리브레이션 완료 후 실시간 절대 마우스 커서 추적 제어 ───
            else:
                # 캘리브레이션 완료 즉시 안내용 웹캠 GUI 창 소멸 및 백그라운드 스위칭
                if not window_destroyed:
                    cv2.destroyAllWindows()
                    window_destroyed = True
                
                # CPU 과도한 루프 레이스 방지를 위한 미세 자원 할당 양보
                time.sleep(0.001)

                # 입 크기 기반 토글 락 제어 (LOCK / UNLOCK)
                mouth_dist = abs(lms[13].y - lms[14].y)
                if mouth_dist > MOUTH_THRESHOLD and mouth_cooldown == 0:
                    is_locked = not is_locked
                    mouth_cooldown = MOUTH_CD_MAX
                    status_str = "LOCKED (마우스 고정)" if is_locked else "UNLOCKED (추적 활성화)"
                    print(f"[시스템 알림] 커서 상태 변경: {status_str}")
                    
                if mouth_cooldown > 0:
                    mouth_cooldown -= 1

                # 락 상태가 아닐 때만 실제 하드웨어 커서 움직임 명령 전송
                if not is_locked:
                    # 머리 흔들림 오프셋 상쇄 연산
                    off_x, off_y = get_head_offset(lms, calib)
                    comp_x = iris_norm_x - off_x
                    comp_y = iris_norm_y - off_y

                    # 상하좌우 관계가 온전한 모니터 절대 비율 공간(0.0 ~ 1.0)으로 아핀 투영
                    mapped_x, mapped_y = calib.map(comp_x, comp_y)

                    # 부드러운 움직임을 보장하기 위한 원유로 실시간 필터 적용
                    sx = filter_x.filter(mapped_x, timestamp=now)
                    sy = filter_y.filter(mapped_y, timestamp=now)

                    # 시선이 모니터 화면 바깥 경계를 초과할 경우를 위한 경계 제한 조치
                    sx = np.clip(sx, 0.0, 1.0)
                    sy = np.clip(sy, 0.0, 1.0)

                    # 요구사항 반영: 정규화 좌표계를 스크린 픽셀 크기에 그대로 연동시켜 절대 좌표(최종 목표 지점)로 변환
                    target_x = sx * SCREEN_WIDTH
                    target_y = sy * SCREEN_HEIGHT

                    # 선형 보간(Lerf)
                    dist = np.sqrt((target_x - current_mouse_x)**2 + (target_y - current_mouse_y)**2)
                    
                    if dist <= MIN_DISTANCE:
                        # 타겟 반경 150픽셀 이내: 무조건 최소 속도로 정밀 타겟팅
                        dynamic_smoothing = MIN_SMOOTHING
                    elif dist >= MAX_DISTANCE:
                        # 타겟 반경 400픽셀 밖: 무조건 최대 속도로 날아감
                        dynamic_smoothing = MAX_SMOOTHING
                    else:
                        # 150 ~ 400픽셀 사이: 속도가 자연스럽게 가속/감속되는 구간
                        dist_ratio = (dist - MIN_DISTANCE) / (MAX_DISTANCE - MIN_DISTANCE)
                        dynamic_smoothing = MIN_SMOOTHING + (MAX_SMOOTHING - MIN_SMOOTHING) * dist_ratio

                    current_mouse_x += (target_x - current_mouse_x) * dynamic_smoothing
                    current_mouse_y += (target_y - current_mouse_y) * dynamic_smoothing

                    # OS 커서 제어 하드웨어 가로채기 주입 (_pause=False 처리로 실시간 지연 요소 소멸)
                    pyautogui.moveTo(int(current_mouse_x), int(current_mouse_y), _pause=False)

        # 캘리브레이션이 완료되지 않은 상태(1단계)에서만 오픈CV 창 활성화 및 키 매핑 스캔
        if not calib.done:
            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC 키 누르면 도중 탈출
                break
            elif key == ord(' '):  # 스페이스바 누르면 현재 타겟에 대한 데이터 누적 채집 시작
                if face_ok and not sampling_active:
                    sampling_active = True
        else:
            # 2단계 진입 후에는 포커스 창이 없으므로 무거운 cv2.waitKey를 건너뜀
            pass

except KeyboardInterrupt:
    print("\n[시스템 알림] 터미널 인터럽트 요청 감지. 시선 마우스 제어 모듈을 완전히 종료합니다.")

finally:
    cap.release()
    if not window_destroyed:
        cv2.destroyAllWindows()