window.Session = {
    save(data) {
        const history = JSON.parse(localStorage.getItem('game_history') || '[]');
        history.push({ ...data, date: new Date().toISOString() });
        localStorage.setItem('game_history', JSON.stringify(history));
        console.log("💾 데이터가 LocalStorage에 저장되었습니다.");
    },
    getHistory() {
        return JSON.parse(localStorage.getItem('game_history') || '[]');
    },
    clear() {
        localStorage.removeItem('game_history');
    }
};
