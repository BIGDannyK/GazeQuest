# GazeQuest: Webcam-Based Eye-Tracking Adventure Game

## 🇰🇷 국문 요약 (Korean)
[cite_start]**GazeQuest**는 고가의 전용 장비 없이 일반 웹캠만을 사용하여 사용자의 시선으로 조작하는 PC 어드벤처 게임입니다[cite: 2, 4]. [cite_start]마우스나 키보드 대신 시선 추적 기술을 활용하여 게임의 접근성을 높이고 새로운 몰입 경험을 제공하는 것을 목표로 합니다[cite: 4, 6].

### 🎯 프로젝트 핵심
* [cite_start]**목적**: 물리적 입력 장치 의존도를 낮춰 신체적 제약이 있는 사용자의 접근성을 개선합니다[cite: 4, 6].
* [cite_start]**해결 과제**: 일반 웹캠의 낮은 해상도와 조명 문제를 소프트웨어 최적화로 극복하여 경제적인 시선 추적 솔루션을 구현합니다[cite: 6, 8].
* [cite_start]**최종 결과**: Python 기반 시선 추적 애플리케이션과 Unity 기반 3D 탈출 게임 클라이언트를 제작합니다[cite: 4].

### 🛠 주요 기술 및 기능
* [cite_start]**실시간 추적**: MediaPipe 및 OpenCV를 활용한 안면 랜드마크 및 홍채 좌표 추출[cite: 10, 12].
* [cite_start]**좌표 보정**: 사용자 맞춤형 화면 매핑 및 칼만 필터(Kalman filters)를 통한 시선 안정화[cite: 10, 12].
* [cite_start]**저지연 통신**: Python과 Unity 간 UDP 소켓을 통한 실시간 데이터 전송[cite: 10, 12].
* [cite_start]**응시 상호작용**: 특정 지점을 일정 시간 응시(Dwell-time)하여 퍼즐을 풀거나 이벤트를 실행하는 메커니즘[cite: 10, 12].

---

## 🇺🇸 English Summary (English)
[cite_start]**GazeQuest** is a PC adventure game controlled entirely by the user's gaze using a standard webcam instead of expensive dedicated hardware[cite: 2, 4]. [cite_start]It aims to enhance accessibility and provide a novel interactive experience by replacing traditional physical input devices[cite: 4, 6].

### 🎯 Key Objectives
* [cite_start]**Goal**: Improve accessibility for users with mobility constraints by reducing reliance on physical input devices[cite: 4, 6].
* [cite_start]**Problem Solving**: Delivering an economical software-driven alternative to expensive infrared eye trackers by optimizing open-source models[cite: 6, 8].
* [cite_start]**Final Results**: A background gaze-tracking application (Python) and a playable Unity 3D escape room game client[cite: 4].

### 🛠 Key Features
* [cite_start]**Real-time Tracking**: Facial landmark and iris center extraction using MediaPipe and OpenCV[cite: 10, 12].
* [cite_start]**Calibration & Smoothing**: Personalized screen mapping and jitter reduction via Kalman filters to stabilize the virtual cursor[cite: 10, 12].
* [cite_start]**Low-Latency Communication**: High-speed UDP socket communication converting and sending 2D gaze data to the game engine[cite: 10, 12].
* [cite_start]**Dwell-Time Interaction**: In-game mechanics that trigger actions (e.g., unlocking doors) when the gaze is fixed on an object for a set duration[cite: 10, 12].