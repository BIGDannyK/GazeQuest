window.Pointer = {
    x: 0,
    y: 0,
    isValid: false,

    init() {
        window.addEventListener('mousemove', (e) => {
            this.x = e.clientX;
            this.y = e.clientY;
            this.isValid = true;

            if (window.Tracker && window.Tracker.isTracking) {
                window.Tracker.onSample(this.x, this.y);
            }
        });
        console.log("🖱️ Pointer calibrated.");
    },

    // 특정 엘리먼트(캔버스) 내부의 상대 좌표를 계산하는 핵심 함수
    getRelativeCoords(canvas) {
        const rect = canvas.getBoundingClientRect();
        return {
            x: this.x - rect.left,
            y: this.y - rect.top
        };
    }
};

window.addEventListener('DOMContentLoaded', () => window.Pointer.init());
