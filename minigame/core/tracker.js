window.Tracker = {
    samples: [],
    events: [],
    startTime: null,
    isTracking: false,
    currentGame: '',

    startSession(gameName) {
        this.currentGame = gameName;
        this.samples = [];
        this.events = [];
        this.startTime = performance.now();
        this.isTracking = true;
        console.log(`🚀 [${gameName}] 기록 시작`);
    },

    onSample(x, y) {
        this.samples.push({ x, y, t: performance.now() });
    },

    logEvent(name, data = {}) {
        this.events.push({ name, ...data, t: performance.now() });
    },

    endSession() {
        this.isTracking = false;
        const result = {
            game: this.currentGame,
            duration: (performance.now() - this.startTime) / 1000,
            samples: this.samples,
            events: this.events
        };
        console.log("🏁 세션 종료", result);
        if (window.Session) window.Session.save(result);
        return result;
    }
};
