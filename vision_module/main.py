import cv2
import numpy as np
import urllib.request
import os
import mediapipe as mp
import time
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

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
#  ONE EURO FILTER
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
#  5-POINT CALIBRATION
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

CALIB_SAMPLES = 20   # 포인트당 누적 프레임 수


class Calibration:
    def __init__(self):
        self.reset()

    def reset(self):
        self.step           = 0
        self.iris_pts       = []
        self.sample_buf     = []
        self.M              = None
        self.ready          = False
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
        src = np.array([[ix, iy, 1.0] for ix, iy in self.iris_pts], dtype=np.float64)
        dst = np.array(list(CALIB_TARGETS),                         dtype=np.float64)
        M_T, _, _, _ = np.linalg.lstsq(src, dst, rcond=None)
        self.M     = M_T.T   # shape (2, 3)
        self.ready = True

    def map(self, ix, iy):
        if self.M is None:
            return ix, iy
        v = np.array([ix, iy, 1.0])
        r = self.M @ v
        return float(r[0]), float(r[1])


# ─────────────────────────────────────────────
#  HEAD POSE COMPENSATION
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
MOVE_SPEED      = 0.012
DEADZONE        = 0.28
MOUTH_THRESHOLD = 0.04
MOUTH_CD_MAX    = 20
PRINT_INTERVAL  = 0.5
WIN_W, WIN_H    = 960, 720


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
#  MAIN
# ─────────────────────────────────────────────
calib           = Calibration()
filter_x         = OneEuroFilter()
filter_y         = OneEuroFilter()

dot_x, dot_y    = 0.5, 0.5
is_locked       = False
mouth_cooldown  = 0
warning_msg     = ""
warning_timer   = 0
last_print_time = 0
detection_result = None
mouth_dist      = 0.0
sampling_active = False
lms             = None

window_name = "GazeQuest - Vision Module"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.resizeWindow(window_name, WIN_W, WIN_H)

cap = cv2.VideoCapture(0)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    h_cam, w_cam = frame.shape[:2]
    now = time.time()

    rgb_frame        = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image         = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    detection_result = detector.detect(mp_image)

    iris_norm_x, iris_norm_y   = 0.0, 0.0
    current_iris_x, current_iris_y = 0, 0
    face_ok = bool(detection_result.face_landmarks)

    if face_ok:
        lms = detection_result.face_landmarks[0]

        li, ri      = lms[468], lms[473]
        iris_norm_x = (li.x + ri.x) / 2.0
        iris_norm_y = (li.y + ri.y) / 2.0
        current_iris_x = int(iris_norm_x * w_cam)
        current_iris_y = int(iris_norm_y * h_cam)

        cv2.circle(frame, (int(li.x*w_cam), int(li.y*h_cam)), 3, (0, 255, 100), -1)
        cv2.circle(frame, (int(ri.x*w_cam), int(ri.y*h_cam)), 3, (0, 255, 100), -1)
        cv2.circle(frame, (current_iris_x, current_iris_y), 4, (0, 200, 255), -1)

        if calib.done:
            mouth_dist = abs(lms[13].y - lms[14].y)
            if mouth_dist > MOUTH_THRESHOLD and mouth_cooldown == 0:
                is_locked      = not is_locked
                mouth_cooldown = MOUTH_CD_MAX
                warning_msg    = "CURSOR LOCKED" if is_locked else "CURSOR UNLOCKED"
                warning_timer  = 60
            if mouth_cooldown > 0:
                mouth_cooldown -= 1

    if not calib.done:
        if sampling_active and face_ok:
            calib.add_sample(iris_norm_x, iris_norm_y)
            if len(calib.sample_buf) >= CALIB_SAMPLES:
                calib.confirm_point(lms=lms)
                sampling_active = False
                if calib.done:
                    warning_msg   = "Calibration Complete!  Press R to redo"
                    warning_timer = 90

        draw_calib_screen(frame, calib, sampling_active, w_cam, h_cam)

        if not face_ok:
            cv2.putText(frame, "[ Face not detected ]", (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    else:
        if face_ok and iris_norm_x != 0.0:
            off_x, off_y = get_head_offset(lms, calib)
            comp_x = iris_norm_x - off_x
            comp_y = iris_norm_y - off_y

            mapped_x, mapped_y = calib.map(comp_x, comp_y)

            sx = filter_x.filter(mapped_x, timestamp=now)
            sy = filter_y.filter(mapped_y, timestamp=now)

            # 1. 중심(0.5, 0.5)으로부터의 거리와 방향 계산
            dx = sx - 0.5
            dy = sy - 0.5
            dist = np.sqrt(dx**2 + dy**2)

            # 2. 원형 경계(DEADZONE)를 기준으로 한 속도 계산
            if dist > DEADZONE:
                # (현재거리 - 반지름)을 통해 경계 밖으로 벗어난 정도를 구함
                # 이 값이 커질수록 이동 속도가 증가함
                speed_factor = dist - DEADZONE
                
                # 방향 벡터(정규화)에 거리 기반 속도 계수를 곱함
                vx = (dx / dist) * speed_factor
                vy = (dy / dist) * speed_factor
            else:
                # 원 안에 있을 때는 속도 0
                vx, vy = 0.0, 0.0

            if not is_locked:
                dot_x = float(np.clip(dot_x + vx * MOVE_SPEED, 0.0, 1.0))
                dot_y = float(np.clip(dot_y + vy * MOVE_SPEED, 0.0, 1.0))

            # ─── 수정된 부분: 데드존 시각화를 사각형에서 원으로 변경 ───
            center_x, center_y = int(w_cam * 0.5), int(h_cam * 0.5)
            radius = int(DEADZONE * w_cam)
            cv2.circle(frame, (center_x, center_y), radius, (200, 200, 200), 1)
            # ──────────────────────────────────────────────────────────

            cv2.circle(frame, (int(sx*w_cam), int(sy*h_cam)), 6, (0, 220, 255), -1)
            dot_color = (0, 165, 255) if is_locked else (0, 0, 255)
            cv2.circle(frame, (int(dot_x*w_cam), int(dot_y*h_cam)), 15, dot_color, -1)

            state_text   = "LOCKED  (open mouth)" if is_locked else f"MOVING  ({vx}, {vy})"
            status_color = (0, 60, 255) if is_locked else (0, 220, 60)
            cv2.putText(frame, f"STATUS: {state_text}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)

            if now - last_print_time >= PRINT_INTERVAL:
                print(f"[{'LOCKED' if is_locked else 'ACTIVE'}] "
                      f"Dot:({dot_x:.2f},{dot_y:.2f}) | Mouth:{mouth_dist:.3f}")
                last_print_time = now

    if warning_timer > 0:
        msg_col = (0, 60, 255) if is_locked else (0, 220, 60)
        cv2.putText(frame, warning_msg, (w_cam//2 - 140, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, msg_col, 2)
        warning_timer -= 1

    rect = cv2.getWindowImageRect(window_name)
    if rect and rect[2] > 0 and rect[3] > 0:
        cv2.imshow(window_name,
                   cv2.resize(frame, (rect[2], rect[3]),
                               interpolation=cv2.INTER_LINEAR))
    else:
        cv2.imshow(window_name, frame)

    key = cv2.waitKey(1) & 0xFF

    if key == 27 or cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
        break

    elif key == ord(' '):
        if not calib.done and face_ok and not sampling_active:
            sampling_active = True

    elif key == ord('r') or key == ord('R'):
        calib           = Calibration()
        filter_x         = OneEuroFilter()
        filter_y         = OneEuroFilter()
        dot_x, dot_y    = 0.5, 0.5
        is_locked       = False
        sampling_active = False
        warning_msg     = "RESET!"
        warning_timer   = 60
        print("[GazeQuest] Reset.")

cap.release()
cv2.destroyAllWindows()