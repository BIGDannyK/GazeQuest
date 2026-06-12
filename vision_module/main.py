import sys
import cv2
import numpy as np
import urllib.request
import os
import mediapipe as mp
import time
import pyautogui
import signal
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor

# ─────────────────────────────────────────────
#  PYAUTOGUI & SETTINGS (마우스 및 설정)
# ─────────────────────────────────────────────
pyautogui.FAILSAFE = False
SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()

MOUTH_THRESHOLD  = 0.04
MOUTH_CD_MAX     = 20
MIN_SMOOTHING    = 0.01
MAX_SMOOTHING    = 0.15
MIN_DISTANCE     = 150.0
MAX_DISTANCE     = 400.0

# [체류 클릭 설정]
DWELL_RADIUS        = 30.0   # 머물러야 하는 픽셀 반경
DWELL_TIME_SEC      = 1.2    # 클릭까지 필요한 시간 (초)
CLICK_CD_MAX        = 15     # 쿨다운
DWELL_VISUAL_RADIUS = 25     # 그려질 원의 크기

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
#  ONE EURO FILTER & CALIBRATION (기존과 동일)
# ─────────────────────────────────────────────
class OneEuroFilter:
    def __init__(self, freq=30.0, min_cutoff=0.8, beta=0.06, d_cutoff=1.0):
        self.freq, self.min_cutoff, self.beta, self.d_cutoff = freq, min_cutoff, beta, d_cutoff
        self.x_prev, self.t_prev = None, None
        self.dx_prev = 0.0

    def _alpha(self, cutoff):
        tau = 1.0 / (2 * np.pi * cutoff)
        te  = 1.0 / self.freq
        return 1.0 / (1.0 + tau / te)

    def filter(self, x, timestamp=None):
        if self.x_prev is None:
            self.x_prev, self.t_prev = x, timestamp
            return x
        if timestamp is not None and self.t_prev is not None:
            dt = timestamp - self.t_prev
            if dt > 0: self.freq = 1.0 / dt
            self.t_prev = timestamp
        dx      = (x - self.x_prev) * self.freq
        a_d     = self._alpha(self.d_cutoff)
        dx_hat  = a_d * dx + (1 - a_d) * self.dx_prev
        cutoff  = self.min_cutoff + self.beta * abs(dx_hat)
        a       = self._alpha(cutoff)
        x_hat   = a * x + (1 - a) * self.x_prev
        self.x_prev, self.dx_prev = x_hat, dx_hat
        return x_hat

MARGIN = 0.08
CALIB_TARGETS = [(MARGIN, MARGIN), (1 - MARGIN, MARGIN), (0.5, 0.5), (MARGIN, 1 - MARGIN), (1 - MARGIN, 1 - MARGIN)]
CALIB_LABELS = ["TOP-LEFT", "TOP-RIGHT", "CENTER", "BOTTOM-LEFT", "BOTTOM-RIGHT"]
CALIB_SAMPLES = 20

class Calibration:
    def __init__(self): self.reset()
    def reset(self):
        self.step = 0; self.iris_pts = []; self.sample_buf = []; self.M = None; self.ready = False
        self.neutral_nose_x = None; self.neutral_nose_y = None
    @property
    def done(self): return self.ready
    def current_target_px(self, frame_w, frame_h):
        if self.step >= len(CALIB_TARGETS): return None
        return int(CALIB_TARGETS[self.step][0] * frame_w), int(CALIB_TARGETS[self.step][1] * frame_h)
    def add_sample(self, ix, iy): self.sample_buf.append((ix, iy))
    def confirm_point(self, lms=None):
        if not self.sample_buf: return False
        self.iris_pts.append((float(np.mean([s[0] for s in self.sample_buf])), float(np.mean([s[1] for s in self.sample_buf]))))
        if self.step == 0 and lms is not None:
            self.neutral_nose_x, self.neutral_nose_y = lms[1].x - lms[6].x, lms[1].y - lms[6].y
        self.sample_buf = []
        self.step += 1
        if self.step >= len(CALIB_TARGETS): self._fit()
        return True
    def _fit(self):
        src = np.array([[ix, iy, 1.0] for ix, iy in self.iris_pts], dtype=np.float64)
        dst = np.array(list(CALIB_TARGETS), dtype=np.float64)
        M_T, _, _, _ = np.linalg.lstsq(src, dst, rcond=None)
        self.M, self.ready = M_T.T, True
    def map(self, ix, iy):
        if self.M is None: return ix, iy
        r = self.M @ np.array([ix, iy, 1.0])
        return float(r[0]), float(r[1])

def get_head_offset(lms, calib):
    if calib.neutral_nose_x is None: return 0.0, 0.0
    return (lms[1].x - lms[6].x - calib.neutral_nose_x) * 0.55, (lms[1].y - lms[6].y - calib.neutral_nose_y) * 0.55

def draw_calib_screen(frame, calib, sampling_active, w, h):
    tgt = calib.current_target_px(w, h)
    if not tgt: return
    tx, ty = tgt
    label = CALIB_LABELS[calib.step]
    progress = len(calib.sample_buf) / CALIB_SAMPLES if sampling_active else 0.0
    guide, g_col = (f"Step {calib.step+1}/5: Sampling {label} ...", (0, 220, 100)) if sampling_active else (f"Step {calib.step+1}/5: Look at {label}  ->  press SPACE", (0, 200, 255))
    cv2.putText(frame, guide, (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.62, g_col, 2)
    cv2.circle(frame, (tx, ty), 24, (255, 255, 255), 2)
    cv2.circle(frame, (tx, ty), 7, (0, 60, 255) if int(time.time() * 3) % 2 == 0 else (0, 120, 255), -1)
    if progress > 0: cv2.ellipse(frame, (tx, ty), (24, 24), -90, 0, int(360 * progress), (0, 220, 100), 3)
    cv2.putText(frame, label, (tx - 40, ty + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

# ─────────────────────────────────────────────
#  [NEW] 백그라운드 스레드 (웹캠 및 마우스 제어 담당)
# ─────────────────────────────────────────────
class GazeThread(QThread):
    # GUI로 마우스 좌표와 진행률(0.0 ~ 1.0)을 보내기 위한 신호
    update_overlay_signal = pyqtSignal(int, int, float)

    def __init__(self, cap, calib):
        super().__init__()
        self.cap = cap
        self.calib = calib
        self.running = True

    def run(self):
        filter_x, filter_y = OneEuroFilter(), OneEuroFilter()
        current_mouse_x, current_mouse_y = SCREEN_WIDTH / 2.0, SCREEN_HEIGHT / 2.0
        is_locked, mouth_cooldown = False, 0
        
        dwell_start_time = 0.0
        last_dwell_x, last_dwell_y = current_mouse_x, current_mouse_y
        click_cooldown = 0

        while self.running and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret: break

            now = time.time()
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            detection_result = detector.detect(mp_image)

            if detection_result.face_landmarks:
                lms = detection_result.face_landmarks[0]
                li, ri = lms[468], lms[473]
                iris_norm_x, iris_norm_y = (li.x + ri.x) / 2.0, (li.y + ri.y) / 2.0

                mouth_dist = abs(lms[13].y - lms[14].y)
                if mouth_dist > MOUTH_THRESHOLD and mouth_cooldown == 0:
                    is_locked = not is_locked
                    mouth_cooldown = MOUTH_CD_MAX
                    print("LOCKED" if is_locked else "UNLOCKED")
                if mouth_cooldown > 0: mouth_cooldown -= 1

                if not is_locked:
                    off_x, off_y = get_head_offset(lms, self.calib)
                    mapped_x, mapped_y = self.calib.map(iris_norm_x - off_x, iris_norm_y - off_y)
                    sx = np.clip(filter_x.filter(mapped_x, timestamp=now), 0.0, 1.0)
                    sy = np.clip(filter_y.filter(mapped_y, timestamp=now), 0.0, 1.0)

                    target_x, target_y = sx * SCREEN_WIDTH, sy * SCREEN_HEIGHT
                    dist = np.sqrt((target_x - current_mouse_x)**2 + (target_y - current_mouse_y)**2)
                    
                    if dist <= MIN_DISTANCE: dyn_smooth = MIN_SMOOTHING
                    elif dist >= MAX_DISTANCE: dyn_smooth = MAX_SMOOTHING
                    else: dyn_smooth = MIN_SMOOTHING + (MAX_SMOOTHING - MIN_SMOOTHING) * ((dist - MIN_DISTANCE) / (MAX_DISTANCE - MIN_DISTANCE))

                    current_mouse_x += (target_x - current_mouse_x) * dyn_smooth
                    current_mouse_y += (target_y - current_mouse_y) * dyn_smooth
                    pyautogui.moveTo(int(current_mouse_x), int(current_mouse_y), _pause=False)

                    # Dwell-Click 로직
                    if click_cooldown > 0: click_cooldown -= 1
                    dist_from_last = np.sqrt((current_mouse_x - last_dwell_x)**2 + (current_mouse_y - last_dwell_y)**2)
                    
                    progress_ratio = 0.0
                    if dist_from_last <= DWELL_RADIUS:
                        if dwell_start_time == 0.0: dwell_start_time = now
                        progress_ratio = min((now - dwell_start_time) / DWELL_TIME_SEC, 1.0)

                        if progress_ratio >= 1.0 and click_cooldown == 0:
                            pyautogui.leftClick(_pause=False)
                            click_cooldown = CLICK_CD_MAX
                            dwell_start_time = 0.0
                    else:
                        last_dwell_x, last_dwell_y = current_mouse_x, current_mouse_y
                        dwell_start_time = 0.0

                    # GUI 스레드로 투명 원을 그릴 위치와 진행률 전송
                    self.update_overlay_signal.emit(int(current_mouse_x), int(current_mouse_y), progress_ratio)

            time.sleep(0.005) # 스레드 부하 방지

    def stop(self):
        self.running = False
        self.wait()

# ─────────────────────────────────────────────
#  [NEW] 투명 오버레이 UI (PyQt5)
# ─────────────────────────────────────────────
class TransparentOverlay(QWidget):
    def __init__(self):
        super().__init__()
        # 창 프레임 제거, 항상 위 설정, 작업표시줄 숨김
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        # 배경을 완전히 투명하게 설정
        self.setAttribute(Qt.WA_TranslucentBackground)
        # ★ 핵심: 마우스 클릭 이벤트가 창을 통과하도록 설정 (Click-through)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        
        self.setGeometry(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
        self.cursor_x = 0
        self.cursor_y = 0
        self.progress = 0.0

    def update_overlay(self, x, y, progress):
        self.cursor_x = x
        self.cursor_y = y
        self.progress = progress
        self.update()  # paintEvent 호출 (화면 갱신)

    def paintEvent(self, event):
        if self.progress > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing) # 계단현상 방지

            # 1. 반투명한 회색 배경 원 (틀)
            pen_bg = QPen(QColor(150, 150, 150, 100), 4)
            painter.setPen(pen_bg)
            painter.drawEllipse(self.cursor_x - DWELL_VISUAL_RADIUS, self.cursor_y - DWELL_VISUAL_RADIUS, 
                                DWELL_VISUAL_RADIUS * 2, DWELL_VISUAL_RADIUS * 2)

            # 2. 파란색 진행 원 (시간이 지날수록 차오름)
            pen_fg = QPen(QColor(50, 150, 255, 220), 5)
            painter.setPen(pen_fg)
            
            # PyQt5에서 drawArc의 각도는 1/16도 단위. 90도는 12시 방향.
            # 마이너스 값은 시계방향으로 그려짐.
            start_angle = 90 * 16 
            span_angle = int(-360 * self.progress * 16)
            painter.drawArc(self.cursor_x - DWELL_VISUAL_RADIUS, self.cursor_y - DWELL_VISUAL_RADIUS, 
                            DWELL_VISUAL_RADIUS * 2, DWELL_VISUAL_RADIUS * 2, 
                            start_angle, span_angle)

# ─────────────────────────────────────────────
#  MAIN EXECUTION (1단계 OpenCV -> 2단계 PyQt5)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    cap = cv2.VideoCapture(0)
    calib = Calibration()
    sampling_active = False

    print("==================================================")
    print(" [1단계] OpenCV 기반 캘리브레이션 시작")
    print(" 화면 안내에 따라 스페이스바를 눌러 초점을 학습하세요.")
    print("==================================================")

    window_name = "Calibration Phase"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    # --- 1단계: 캘리브레이션 루프 (OpenCV UI) ---
    while cap.isOpened() and not calib.done:
        ret, frame = cap.read()
        if not ret: break

        frame = cv2.flip(frame, 1)
        h_cam, w_cam = frame.shape[:2]
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        res = detector.detect(mp_image)
        face_ok = bool(res.face_landmarks)

        if face_ok:
            lms = res.face_landmarks[0]
            if sampling_active:
                calib.add_sample((lms[468].x + lms[473].x)/2.0, (lms[468].y + lms[473].y)/2.0)
                if len(calib.sample_buf) >= CALIB_SAMPLES:
                    calib.confirm_point(lms=lms)
                    sampling_active = False

            draw_calib_screen(frame, calib, sampling_active, w_cam, h_cam)

        cv2.imshow(window_name, frame)
        key = cv2.waitKey(1) & 0xFF
        if key == 27: # ESC
            cap.release()
            cv2.destroyAllWindows()
            sys.exit()
        elif key == ord(' ') and face_ok and not sampling_active:
            sampling_active = True

    cv2.destroyAllWindows() # 캘리브레이션 완료 시 창 닫기

    print("\n==================================================")
    print(" [2단계] 투명 오버레이 실시간 추적 모드 진입")
    print(" 웹캠 창이 숨겨지고 바탕화면 모드로 작동합니다.")
    print(" 마우스를 특정 위치에 1.2초간 고정하면 파란 원이 차오르며 클릭됩니다.")
    print(" 종료하려면 터미널에서 Ctrl+C 를 누르세요.")
    print("==================================================")

    # --- 2단계: 백그라운드 추적 및 투명 오버레이 렌더링 (PyQt5) ---
    app = QApplication(sys.argv)
    
    overlay = TransparentOverlay()
    overlay.show()

    gaze_thread = GazeThread(cap, calib)
    gaze_thread.update_overlay_signal.connect(overlay.update_overlay) # 스레드와 UI 연결
    gaze_thread.start()

    def sigint_handler(signum, frame):
        print("\n[시스템 알림] 터미널에서 Ctrl+C 입력 감지. 프로그램을 안전하게 종료합니다.")
        app.quit()  # PyQt 메인 이벤트 루프를 강제 탈출시킴

    # 터미널 인터럽트 신호를 sigint_handler 함수로 연결
    signal.signal(signal.SIGINT, sigint_handler)

    # 파이썬 인터프리터가 C++ 루프 속에서도 0.5초마다 주기적으로 깨어나서
    # Ctrl+C 신호가 들어왔는지 확인하도록 빈 타이머(Dummy Timer) 설정
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)
    
    # PyQt5 메인 루프 실행 (app.quit()이 호출될 때까지 여기서 대기)
    app.exec_() 
    
    # ─────────────────────────────────────────────
    # 프로그램 종료 시 자원 안전 해제
    # ─────────────────────────────────────────────
    print("[시스템 알림] 백그라운드 스레드 및 웹캠 자원을 해제합니다...")
    gaze_thread.stop()
    if cap.isOpened():
        cap.release()
    sys.exit(0)