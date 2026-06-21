# GazeQuest: Webcam-Based Eye-Tracking Adventure Game

## 🇰🇷 국문 요약 (Korean)
**GazeQuest**는 고가의 전용 장비 없이 일반 웹캠만을 사용하여 사용자의 시선으로 조작하는 PC 어드벤처 게임입니다. 마우스나 키보드 대신 시선 추적 기술을 활용하여 게임의 접근성을 높이고 새로운 몰입 경험을 제공합니다.

### 🎯 프로젝트 핵심
* **목적**: 물리적 입력 장치 의존도를 낮춰 신체적 제약이 있는 사용자의 접근성을 개선합니다.
* **해결 과제**: 일반 웹캠의 낮은 해상도와 조명 문제를 소프트웨어 최적화로 극복하여 경제적인 시선 추적 솔루션을 구현합니다.
* **최종 결과**: Python 기반 시선 추적 애플리케이션과 Unity 기반 3D 탈출 게임 클라이언트를 제작합니다.

### 🛠 주요 기술 및 기능
* **실시간 추적**: MediaPipe 및 OpenCV를 활용한 안면 랜드마크 및 홍채 좌표 추출.
* **좌표 보정**: 사용자 맞춤형 화면 매핑 및 칼만 필터(Kalman filters)를 통한 시선 안정화.
* **저지연 통신**: Python과 Unity 간 UDP 소켓을 통한 실시간 데이터 전송.
* **응시 상호작용**: 특정 지점을 일정 시간 응시(Dwell-time)하여 퍼즐을 풀거나 이벤트를 실행하는 메커니즘.

## ⚠️ Limitations / 제한 사항

- GazeQuest는 실시간 시선 추적을 위해 웹캠에 지속적으로 접근해야 합니다.
- Zoom, Google Meet, Microsoft Teams, Discord, OBS Studio 등 카메라를 사용하는 다른 프로그램이 실행 중인 경우 시선 추적 모듈이 정상적으로 초기화되지 않거나 동작하지 않을 수 있습니다.
- 운영체제 및 웹캠 드라이버 환경에 따라 카메라 공유가 지원되지 않을 수 있으며, 이 경우 영상 스트림에 접근할 수 없습니다.
- 최적의 성능을 위해 게임 실행 전 다른 카메라 사용 프로그램을 종료하는 것을 권장합니다.

## 🚀 Usage / 사용 방법

1. 프로그램을 실행합니다.
2. 화면의 안내에 따라 시선을 다음 위치로 이동한 후 각 위치에서 스페이스바를 눌러 보정을 진행합니다.
   - 왼쪽 위
   - 오른쪽 위
   - 중앙
   - 왼쪽 아래
   - 오른쪽 아래
3. 보정이 완료되면 원하는 위치로 시선을 이동하여 마우스 커서를 조작할 수 있습니다.
4. 일정 시간 동안 같은 위치를 응시하면 자동으로 클릭이 수행됩니다.
5. 입을 크게 벌리면 시선 추적 기반 마우스 제어가 일시 중지됩니다.
6. f8을 누르거나 터미널에서 crtl+C를 누르면 프로그램이 종료됩니다.

---

## 🇺🇸 English Summary (English)
**GazeQuest** is a PC adventure game controlled entirely by the user's gaze using a standard webcam instead of expensive dedicated hardware. It aims to enhance accessibility and provide a novel interactive experience by replacing traditional physical input devices.

### 🎯 Key Objectives
* **Goal**: Improve accessibility for users with mobility constraints by reducing reliance on physical input devices.
* **Problem Solving**: Delivering an economical software-driven alternative to expensive infrared eye trackers by optimizing open-source models.
* **Final Results**: A background gaze-tracking application (Python) and a playable Unity 3D escape room game client.

### 🛠 Key Features
* **Real-time Tracking**: Facial landmark and iris center extraction using MediaPipe and OpenCV.
* **Calibration & Smoothing**: Personalized screen mapping and jitter reduction via Kalman filters to stabilize the virtual cursor.
* **Low-Latency Communication**: High-speed UDP socket communication converting and sending 2D gaze data to the game engine.
* **Dwell-Time Interaction**: In-game mechanics that trigger actions (e.g., unlocking doors) when the gaze is fixed on an object for a set duration.

## ⚠️ Limitations

- GazeQuest requires continuous access to a webcam for real-time gaze tracking.
- If another application such as Zoom, Google Meet, Microsoft Teams, Discord, or OBS Studio is already using the camera, the gaze-tracking module may fail to initialize or operate correctly.
- Depending on the operating system and webcam driver, camera sharing may not be supported, causing the application to lose access to the video stream.
- For best performance, close other applications that use the webcam before launching GazeQuest.

1. Launch the program.
2. Follow the on-screen instructions and look at the following positions. Press the **Spacebar** at each position to complete the calibration process.
   - Top-left
   - Top-right
   - Center
   - Bottom-left
   - Bottom-right
3. After calibration, move your gaze to control the mouse cursor.
4. Keeping your gaze fixed on the same position for a certain period will automatically trigger a mouse click.
5. Opening your mouth widely will temporarily pause gaze-based mouse control.
6. Press f8 button or press crtl+C in terminal then program terminate.