# GazeQuest: A Hands-Free Interaction Platform using Real-Time Webcam Eye Tracking

## 🇰🇷 국문 요약 (Korean)

**GazeQuest**는 고가의 전용 장비 없이 일반 웹캠만으로 사용자의 시선을 추적하여, 마우스 없이 PC 전체와 웹 기반 미니게임을 조작할 수 있는 핸즈프리 플랫폼입니다. 시선으로 OS 커서를 직접 제어하고, 한곳을 일정 시간 응시하면 클릭이 실행되는 **Dwell-Click** 방식을 통해 별도의 네트워크 통신 없이도 모든 웹 브라우저 및 프로그램에서 즉시 사용할 수 있습니다.

### 🎯 프로젝트 핵심

- **목적**: 신체적 제약이 있는 사용자나 손을 쓰기 어려운 상황에서도, 웹캠만으로 PC를 완전히 핸즈프리로 제어할 수 있는 접근성 솔루션을 제공합니다.
- **해결 과제**: 초기에는 Flask-SocketIO 기반 WebSocket으로 시선 좌표를 웹 클라이언트에 전송하는 방식을 시도했으나, 서버 수동 실행과 복잡한 프론트엔드 파싱 로직이 필요했고 동기화 문제로 범용성이 떨어졌습니다. 이를 해결하기 위해 **OS 레벨 커서 주입(`pyautogui`)** 방식으로 전환하여, 별도 설정 없이 모든 브라우저·프로그램에서 동작하도록 구조를 재설계했습니다.
- **최종 결과**: 단일 Python 실행 파일로 즉시 구동되는 시선 추적 시스템과, 이를 활용해 플레이할 수 있는 2종의 웹 기반 미니게임(Eye Maze, Number Grid)을 제작했습니다.

### 🛠 주요 기술 및 기능

- **실시간 추적**: MediaPipe Face Landmarker를 활용한 안면 랜드마크 및 홍채 좌표(#468, #473) 추출.
- **좌표 보정**: 5포인트 아핀 변환(Affine Transformation, `np.linalg.lstsq`) 기반 캘리브레이션과 코 랜드마크를 이용한 머리 움직임 보정(Head Pose Compensation).
- **떨림 보정**: One Euro Filter를 적용해 정지 시 떨림을 줄이고 빠른 시선 이동 시 응답성을 유지.
- **OS 레벨 제어**: `pyautogui`를 통해 시선 좌표를 실제 마우스 커서 위치로 직접 매핑 — 별도 통신 프로토콜 없이 모든 애플리케이션과 호환.
- **Dwell-Click**: 반경 30px 이내에서 1.2초간 시선을 고정하면 자동으로 좌클릭이 실행되며, PyQt5 기반의 투명 클릭-통과(click-through) 오버레이가 진행률을 원형 게이지로 시각화.
- **멀티스레딩**: `QThread`로 무거운 OpenCV/MediaPipe 추적 루프를 UI 렌더링과 분리하여 끊김 없는 오버레이 경험을 보장.
- **입 제스처 안전장치**: 입을 벌리는 동작으로 커서 이동을 Lock/Unlock 토글하여 안정성을 높임.
- **웹 미니게임**: 브라우저의 표준 `mousemove`/`click` 이벤트만으로 동작하는 5종 게임으로 시선 조작 능력을 테스트.

---

## 🇺🇸 English Summary

**GazeQuest** is a hands-free platform that uses real-time webcam-based eye tracking to control an entire PC and play web-based mini-games — no specialized hardware and no mouse required. The user's gaze directly drives the OS-level cursor, and a **Dwell-Click** mechanism triggers mouse clicks by fixation alone, making the system instantly usable across any browser or application with zero network setup.

### 🎯 Key Objectives

- **Goal**: Provide a fully automated, hands-free interaction environment using only a standard webcam, for users with physical disabilities or situations where manual input is restricted.
- **Problem Solving**: Early prototypes relied on a Flask-SocketIO WebSocket pipeline to transmit gaze coordinates to the web client. This required manual server execution, complex frontend parsing, and suffered from synchronization issues with no universal compatibility. We pivoted to **OS-level cursor injection (`pyautogui`)**, eliminating the network layer entirely and making the tracker work system-wide, out-of-the-box.
- **Final Results**: A single-script Python application that instantly activates hands-free PC control, paired with two browser-based mini-games (Eye Maze, Number Grid) that demonstrate gaze-driven interaction.

### 🛠 Key Features

- **Real-Time Tracking**: Facial landmark and iris-center extraction (#468, #473) via MediaPipe Face Landmarker.
- **5-Point Calibration**: Affine transformation (`np.linalg.lstsq`) mapping iris coordinates to normalized screen space, with nose-landmark-based head pose compensation to reduce drift.
- **Cursor Stabilization**: One Euro Filter for adaptive smoothing — minimizes jitter when the gaze is steady while preserving responsiveness during fast movement.
- **OS-Level Integration**: `pyautogui` moves the hardware cursor directly, decoupling the vision module from any specific web client and enabling universal compatibility.
- **Dwell-Click & Visual Feedback**: Fixating within a 30-pixel radius for 1.2 seconds triggers a left-click, visualized through a transparent, click-through PyQt5 overlay rendering a circular progress gauge.
- **Multithreaded Architecture**: A dedicated `QThread` (`GazeThread`) isolates the OpenCV/MediaPipe processing loop from the PyQt5 UI thread, ensuring zero-latency tracking and smooth overlay rendering.
- **Mouth-Gesture Safety Toggle**: Opening the mouth locks/unlocks cursor movement for added stability.
- **Web Mini-Games**: two browser games (Eye Maze, Number Grid) driven entirely by native `mousemove`/`click` events — no custom socket logic required.

---

## 📁 Project Structure

```
GazeQuest/
├── vision_module/
│   └── main.py              # Calibration (OpenCV) → Gaze tracking + Dwell-Click (PyQt5 + QThread)
├── minigame/
│   ├── core/
│   │   ├── pointer.js        # Native mousemove listener (OS cursor-compatible)
│   │   ├── tracker.js        # Session/event recorder
│   │   └── session.js        # localStorage persistence
│   ├── games/
│   │   ├── eye-maze/
│   │   ├── number-grid/
│   │   ├── fruit/            # demo (not implement)
│   │   ├── sniper/           # demo (not implement)
│   │   └── rhythm/           # demo (not implement)
│   ├── report/               # Demo result dashboard
│   └── index.html            # Game selection menu
├── face_landmarker.task       # MediaPipe model file
└── README.md
```

## ▶️ How to Run

```bash
# 1. Install dependencies
pip install opencv-python mediapipe numpy pyautogui PyQt5 keyboard

# 2. Launch the vision module
python vision_module/main.py
#   → Complete the 5-point on-screen calibration (press SPACE at each target)
#   → The webcam window closes automatically; hands-free control begins

# 3. Open any browser and play
#   minigame/index.html  (or open it directly as a local file)
#   Your gaze now drives the OS cursor — click using Dwell-Click (1.2s fixation)

# To exit: press F8, or Ctrl+C in the terminal
```

## 🛠 Technical Stack

- **Vision & Backend**: Python, MediaPipe, OpenCV, NumPy
- **OS Control & UI Overlay**: `pyautogui`, PyQt5 (`QThread`, transparent click-through `QWidget`)
- **Frontend (Mini-Games)**: HTML5, CSS3, Vanilla JavaScript
- **Algorithms**: One Euro Filter, Affine Transformation (`np.linalg.lstsq`), Head Pose Compensation

## 👥 Team #7

| Name | Role |
|---|---|
| 김진성 | Core Vision Module & Calibration |
| 김도영 | Cursor Stabilization & OS-level Control Integration |
| 권승호 | Web Client Architecture & Data Pipeline |
| 정희윤 | Interaction UX Design & System Architecture |
