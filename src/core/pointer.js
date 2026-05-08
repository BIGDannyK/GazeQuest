window.Pointer = {
    x: 0,
    y: 0,
    isValid: false,
    socket: null,

    init() {
        // 1. Python Flask-SocketIO 서버에 연결 (main.py에서 설정한 5000 포트)
        this.socket = io("http://localhost:5000");

        this.socket.on("connect", () => {
            console.log("✅ Gaze Server connected!");
        });

        // 2. 'gaze_data' 이벤트 수신
        this.socket.on("gaze_data", (data) => {
            // 정규화된 좌표(0~1)를 브라우저 픽셀 좌표로 변환
            this.updatePosition(data.x * window.innerWidth, data.y * window.innerHeight);
        });

        // (옵션) 마우스 이동도 병행하고 싶다면 유지, 시선만 쓰고 싶다면 삭제하세요.
        window.addEventListener('mousemove', (e) => {
            this.updatePosition(e.clientX, e.clientY);
        });

        console.log("🖱️ Pointer calibrated & Socket connected.");
    },

    // 좌표 갱신 및 외부 모듈(Tracker 등) 알림 통합 함수
    updatePosition(nx, ny) {
        this.x = nx;
        this.y = ny;
        this.isValid = true;

        if (window.Tracker && window.Tracker.isTracking) {
            window.Tracker.onSample(this.x, this.y);
        }
    },

    getRelativeCoords(canvas) {
        const rect = canvas.getBoundingClientRect();
        return {
            x: this.x - rect.left,
            y: this.y - rect.top
        };
    }
};

window.addEventListener('DOMContentLoaded', () => window.Pointer.init());