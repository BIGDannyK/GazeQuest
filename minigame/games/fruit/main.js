// =============================================
// 🔊 AUDIO ENGINE (Web Audio API)
// =============================================
const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;
function getAudio() { if (!audioCtx) audioCtx = new AudioCtx(); return audioCtx; }

function playSlice(combo = 1) {
    const ac = getAudio();
    const freq = 380 + Math.min(combo, 10) * 70;
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.connect(gain); gain.connect(ac.destination);
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(freq, ac.currentTime);
    osc.frequency.exponentialRampToValueAtTime(freq * 0.4, ac.currentTime + 0.12);
    gain.gain.setValueAtTime(0.35, ac.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.15);
    osc.start(); osc.stop(ac.currentTime + 0.15);
}

function playBombHit() {
    const ac = getAudio();
    [80, 100, 130].forEach((f, i) => {
        const osc = ac.createOscillator();
        const gain = ac.createGain();
        osc.connect(gain); gain.connect(ac.destination);
        osc.type = 'square'; osc.frequency.value = f;
        gain.gain.setValueAtTime(0.3, ac.currentTime + i * 0.05);
        gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + i * 0.05 + 0.3);
        osc.start(ac.currentTime + i * 0.05);
        osc.stop(ac.currentTime + i * 0.05 + 0.3);
    });
}

function playMiss() {
    const ac = getAudio();
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.connect(gain); gain.connect(ac.destination);
    osc.type = 'sine'; osc.frequency.value = 160;
    gain.gain.setValueAtTime(0.2, ac.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.25);
    osc.start(); osc.stop(ac.currentTime + 0.25);
}

function playComboSound(combo) {
    if (combo < 3) return;
    const ac = getAudio();
    const notes = [523, 659, 784, 1047];
    const note = notes[Math.min(Math.floor(combo / 3), 3)];
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.connect(gain); gain.connect(ac.destination);
    osc.type = 'triangle'; osc.frequency.value = note;
    gain.gain.setValueAtTime(0.2, ac.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.2);
    osc.start(); osc.stop(ac.currentTime + 0.2);
}

// =============================================
// 🎮 GAME STATE
// =============================================
const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

let fruits = [], particles = [], scorePopups = [], trail = [];
let score = 0, combo = 0, maxCombo = 0, comboTimer = 0;
let timeLeft = 30, isGameOver = false, missCount = 0;
const gravity = 0.15;
const emojis = ['🍎', '🍊', '🍉', '🍍', '🥝', '🍇', '🫐', '🍑'];
let spawnInterval = 1500;

// =============================================
// ✨ PARTICLES & POPUPS
// =============================================
function spawnParticles(x, y) {
    const colors = ['#ff6b6b', '#ffd93d', '#6bcb77', '#4d96ff', '#c77dff', '#ff9a3c'];
    for (let i = 0; i < 14; i++) {
        const angle = (Math.PI * 2 / 14) * i + (Math.random() - 0.5) * 0.6;
        const speed = 3 + Math.random() * 6;
        particles.push({
            x, y,
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed - 1.5,
            life: 1.0,
            decay: 0.025 + Math.random() * 0.025,
            size: 5 + Math.random() * 7,
            color: colors[Math.floor(Math.random() * colors.length)]
        });
    }
}

function spawnBombParticles(x, y) {
    for (let i = 0; i < 20; i++) {
        const angle = Math.random() * Math.PI * 2;
        const speed = 4 + Math.random() * 8;
        particles.push({
            x, y,
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed - 2,
            life: 1.0,
            decay: 0.02 + Math.random() * 0.03,
            size: 6 + Math.random() * 10,
            color: Math.random() > 0.5 ? '#ff4500' : '#ffa500'
        });
    }
}

function spawnScorePopup(x, y, text, color = '#ffffff') {
    scorePopups.push({ x, y, text, color, life: 1.0, vy: -1.8, scale: 1.0 });
}

// =============================================
// 🍎 FRUIT SPAWNING
// =============================================
function spawnFruit() {
    if (isGameOver) return;

    // Bomb chance increases as difficulty rises
    const bombChance = spawnInterval < 1000 ? 0.18 : 0.08;
    if (Math.random() < bombChance) {
        const peakY = canvas.height * (0.25 + Math.random() * 0.3);
        const initialVy = -Math.sqrt(2 * gravity * (canvas.height - peakY));
        fruits.push({
            x: Math.random() * (canvas.width - 200) + 100,
            y: canvas.height,
            vx: (Math.random() - 0.5) * 2.5,
            vy: initialVy,
            radius: 40,
            emoji: '💣',
            isBomb: true,
            sliced: false,
            angle: 0,
            rotationSpeed: (Math.random() - 0.5) * 0.03
        });
    }

    const count = Math.floor(Math.random() * 2) + 1;
    for (let i = 0; i < count; i++) {
        const isSmall = Math.random() > 0.6;
        const radius = isSmall ? 28 : 52;
        const peakY = canvas.height * (0.12 + Math.random() * 0.38);
        const initialVy = -Math.sqrt(2 * gravity * (canvas.height - peakY));
        fruits.push({
            x: Math.random() * (canvas.width - 200) + 100,
            y: canvas.height,
            vx: (Math.random() - 0.5) * 4,
            vy: initialVy,
            radius,
            emoji: emojis[Math.floor(Math.random() * emojis.length)],
            isBomb: false,
            sliced: false,
            angle: 0,
            rotationSpeed: (Math.random() - 0.5) * 0.07
        });
    }

    spawnInterval = Math.max(320, spawnInterval * 0.94);
    setTimeout(spawnFruit, spawnInterval);
}

// =============================================
// 🖱️ CURSOR TRAIL
// =============================================
canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    trail.push({ x: e.clientX - rect.left, y: e.clientY - rect.top, life: 1.0 });
    if (trail.length > 12) trail.shift();
});

// =============================================
// 🔄 GAME LOOP
// =============================================
function update() {
    if (isGameOver) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const coords = Pointer.getRelativeCoords(canvas);

    // Combo timeout
    comboTimer = Math.max(0, comboTimer - 16.6);
    if (comboTimer <= 0 && combo > 0) combo = 0;

    // --- CURSOR TRAIL ---
    for (let i = 1; i < trail.length; i++) {
        const t = trail[i];
        const prev = trail[i - 1];
        t.life -= 0.14;
        ctx.beginPath();
        ctx.moveTo(prev.x, prev.y);
        ctx.lineTo(t.x, t.y);
        ctx.strokeStyle = `rgba(255, 220, 80, ${t.life * 0.7})`;
        ctx.lineWidth = 10 * t.life;
        ctx.lineCap = 'round';
        ctx.stroke();
    }
    trail = trail.filter(t => t.life > 0);

    // --- FRUITS ---
    const toRemove = [];
    fruits.forEach((f, i) => {
        f.x += f.vx;
        f.y += f.vy;
        f.vy += gravity;
        f.angle += f.rotationSpeed;

        const dist = Math.hypot(coords.x - f.x, coords.y - f.y);

        if (!f.sliced && dist < f.radius) {
            f.sliced = true;
            if (f.isBomb) {
                playBombHit();
                spawnBombParticles(f.x, f.y);
                timeLeft = Math.max(0, timeLeft - 5);
                combo = 0;
                spawnScorePopup(f.x, f.y - 40, '💥 -5초!', '#f43f5e');
                Tracker.logEvent('bomb_hit', {});
            } else {
                combo++;
                maxCombo = Math.max(maxCombo, combo);
                comboTimer = 2200;
                const basePoints = f.radius < 38 ? 30 : 10;
                const multiplier = 1 + Math.floor(combo / 3) * 0.5;
                const points = Math.round(basePoints * multiplier);
                score += points;
                playSlice(combo);
                if (combo % 3 === 0) playComboSound(combo);
                spawnParticles(f.x, f.y);
                const popText = combo >= 3 ? `+${points}  x${combo}🔥` : `+${points}`;
                spawnScorePopup(f.x, f.y - 30, popText, combo >= 5 ? '#ffd93d' : combo >= 3 ? '#a8ff78' : '#ffffff');
                Tracker.logEvent('fruit_sliced', { size: f.radius, combo, points });
            }
        }

        // --- DRAW FRUIT ---
        ctx.save();
        ctx.translate(f.x, f.y);
        ctx.rotate(f.angle);
        ctx.font = `${f.radius * 2}px serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        if (f.sliced && !f.isBomb) {
            // Split into two halves
            ctx.globalAlpha = 0.5;
            ctx.save(); ctx.translate(-6, -4); ctx.rotate(-0.3); ctx.fillText(f.emoji, 0, 0); ctx.restore();
            ctx.save(); ctx.translate(6, 4); ctx.rotate(0.3); ctx.fillText(f.emoji, 0, 0); ctx.restore();
        } else {
            ctx.globalAlpha = f.sliced ? 0.15 : 1.0;
            ctx.fillText(f.emoji, 0, 0);
        }
        ctx.restore();
        ctx.globalAlpha = 1;

        if (f.y > canvas.height + 120) {
            if (!f.sliced && !f.isBomb) {
                missCount++;
                combo = 0;
                playMiss();
            }
            toRemove.push(i);
        }
    });
    for (let i = toRemove.length - 1; i >= 0; i--) fruits.splice(toRemove[i], 1);

    // --- PARTICLES ---
    particles.forEach(p => {
        p.x += p.vx; p.y += p.vy;
        p.vy += 0.18;
        p.vx *= 0.98;
        p.life -= p.decay;
        ctx.beginPath();
        ctx.arc(p.x, p.y, Math.max(0, p.size * p.life), 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = p.life;
        ctx.fill();
        ctx.globalAlpha = 1;
    });
    particles = particles.filter(p => p.life > 0);

    // --- SCORE POPUPS ---
    scorePopups.forEach(sp => {
        sp.y += sp.vy;
        sp.life -= 0.022;
        const size = 18 + (1 - sp.life) * 8;
        ctx.font = `bold ${size}px Arial`;
        ctx.fillStyle = sp.color;
        ctx.globalAlpha = sp.life;
        ctx.textAlign = 'center';
        ctx.fillText(sp.text, sp.x, sp.y);
        ctx.globalAlpha = 1;
    });
    scorePopups = scorePopups.filter(sp => sp.life > 0);

    drawUI();
    requestAnimationFrame(update);
}

// =============================================
// 🖼️ UI
// =============================================
function drawUI() {
    // Score
    ctx.textAlign = 'left';
    ctx.fillStyle = 'white';
    ctx.font = 'bold 28px Arial';
    ctx.fillText(`Score: ${score}`, 30, 48);

    // Miss
    ctx.font = '18px Arial';
    ctx.fillStyle = missCount > 0 ? '#f43f5e' : 'rgba(255,255,255,0.5)';
    ctx.fillText(`❌ Miss: ${missCount}`, 30, 74);

    // Combo display
    if (combo >= 2) {
        const size = Math.min(28 + combo * 1.5, 50);
        ctx.font = `bold ${size}px Arial`;
        ctx.fillStyle = combo >= 8 ? '#ff6b35' : combo >= 5 ? '#ffd93d' : '#a8ff78';
        ctx.textAlign = 'center';
        // Glow effect
        ctx.shadowColor = ctx.fillStyle;
        ctx.shadowBlur = 15;
        ctx.fillText(`${combo} COMBO!`, canvas.width / 2, 52);
        ctx.shadowBlur = 0;
    }

    // Timer
    ctx.textAlign = 'right';
    ctx.fillStyle = timeLeft <= 10 ? '#f43f5e' : 'white';
    ctx.font = 'bold 28px Arial';
    ctx.fillText(`⏱ ${Math.ceil(timeLeft)}s`, canvas.width - 30, 48);

    ctx.textAlign = 'left';
}

// =============================================
// 💀 GAME OVER SCREEN
// =============================================
function showGameOver() {
    ctx.fillStyle = 'rgba(0, 0, 0, 0.82)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.textAlign = 'center';

    ctx.fillStyle = '#38bdf8';
    ctx.font = 'bold 52px Arial';
    ctx.shadowColor = '#38bdf8';
    ctx.shadowBlur = 20;
    ctx.fillText('GAME OVER', canvas.width / 2, 195);
    ctx.shadowBlur = 0;

    ctx.fillStyle = 'white';
    ctx.font = 'bold 34px Arial';
    ctx.fillText(`최종 점수: ${score}`, canvas.width / 2, 262);

    ctx.fillStyle = '#ffd93d';
    ctx.font = '24px Arial';
    ctx.fillText(`🔥 최대 콤보: ${maxCombo}회`, canvas.width / 2, 308);

    ctx.fillStyle = '#f43f5e';
    ctx.fillText(`❌ 미스: ${missCount}회`, canvas.width / 2, 348);

    // Grade
    let grade = '⭐';
    if (missCount === 0 && maxCombo >= 10) grade = '🏆 PERFECT';
    else if (score >= 500) grade = '🥇 EXCELLENT';
    else if (score >= 200) grade = '🥈 GREAT';
    else grade = '🥉 GOOD';
    ctx.fillStyle = '#a8ff78';
    ctx.font = 'bold 26px Arial';
    ctx.fillText(grade, canvas.width / 2, 390);

    // Button
    ctx.fillStyle = '#38bdf8';
    roundRect(ctx, canvas.width / 2 - 115, 415, 230, 52, 14);
    ctx.fill();
    ctx.fillStyle = '#0f172a';
    ctx.font = 'bold 20px Arial';
    ctx.fillText('◀ 메인으로 돌아가기', canvas.width / 2, 447);

    canvas.addEventListener('click', () => { location.href = '../../index.html'; }, { once: true });
}

function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
}

// =============================================
// 🚀 START
// =============================================
Tracker.startSession('fruit');
spawnFruit();
update();

const timer = setInterval(() => {
    timeLeft = Math.max(0, timeLeft - 1);
    if (timeLeft <= 0) {
        isGameOver = true;
        clearInterval(timer);
        Tracker.endSession();
        setTimeout(showGameOver, 200);
    }
}, 1000);
