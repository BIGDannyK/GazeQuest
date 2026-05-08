// =============================================
// 🔊 AUDIO ENGINE
// =============================================
const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;
function getAudio() { if (!audioCtx) audioCtx = new AudioCtx(); return audioCtx; }

function playDwellTick(progress) {
    const ac = getAudio();
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.connect(gain); gain.connect(ac.destination);
    osc.type = 'sine';
    osc.frequency.value = 280 + progress * 600;
    gain.gain.setValueAtTime(0.06, ac.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.06);
    osc.start(); osc.stop(ac.currentTime + 0.06);
}

function playLockOn() {
    const ac = getAudio();
    [440, 554, 659].forEach((freq, i) => {
        const osc = ac.createOscillator();
        const gain = ac.createGain();
        osc.connect(gain); gain.connect(ac.destination);
        osc.type = 'sine'; osc.frequency.value = freq;
        const t = ac.currentTime + i * 0.07;
        gain.gain.setValueAtTime(0.22, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.12);
        osc.start(t); osc.stop(t + 0.12);
    });
}

function playMissSound() {
    const ac = getAudio();
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.connect(gain); gain.connect(ac.destination);
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(180, ac.currentTime);
    osc.frequency.exponentialRampToValueAtTime(80, ac.currentTime + 0.3);
    gain.gain.setValueAtTime(0.25, ac.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.3);
    osc.start(); osc.stop(ac.currentTime + 0.3);
}

// =============================================
// 🎮 GAME STATE
// =============================================
const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

let targets = [], particles = [], scorePopups = [];
let score = 0, missCount = 0, combo = 0, maxCombo = 0;
let timeLeft = 30, isGameOver = false;
let lastTickBucket = -1;

const TARGET_LIFETIME = 4500;  // ms until a target auto-disappears
const MAX_TARGETS = 4;

// =============================================
// ✨ PARTICLES & POPUPS
// =============================================
function spawnExplosion(x, y, radius) {
    for (let i = 0; i < 18; i++) {
        const angle = (Math.PI * 2 / 18) * i + (Math.random() - 0.5) * 0.4;
        const speed = 2 + Math.random() * (radius / 8);
        particles.push({
            x, y,
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed,
            life: 1.0,
            decay: 0.03 + Math.random() * 0.03,
            size: 4 + Math.random() * 5,
            color: `hsl(${190 + Math.random() * 50}, 80%, 65%)`
        });
    }
}

function spawnScorePopup(x, y, text, color = '#ffd93d') {
    scorePopups.push({ x, y, text, color, life: 1.0, vy: -2 });
}

// =============================================
// 🎯 TARGET MANAGEMENT
// =============================================
function spawnTarget() {
    const radius = Math.random() * 32 + 18; // 18~50
    const moveSpeed = 0.0;

    targets.push({
        x: Math.random() * (canvas.width - 200) + 100,
        y: Math.random() * (canvas.height - 160) + 80,
        radius,
        dwell: 0,
        maxDwell: radius < 30 ? 650 : 1200,
        state: 'preview',
        spawnTime: performance.now(),
        previewDuration: 550,
        // Slight drift after appearing
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        lastTickBucket: -1
    });
}

setInterval(() => {
    if (!isGameOver && targets.length < MAX_TARGETS) spawnTarget();
}, 1000);

// =============================================
// 🖱️ CROSSHAIR DRAWING
// =============================================
function drawCrosshair(x, y, isLocked) {
    const size = 22;
    const gap = 6;
    ctx.strokeStyle = isLocked ? 'rgba(56, 189, 248, 0.9)' : 'rgba(244, 63, 94, 0.85)';
    ctx.lineWidth = 1.5;

    // Four lines with center gap
    [[x - gap, y, x - size, y], [x + gap, y, x + size, y],
     [x, y - gap, x, y - size], [x, y + gap, x, y + size]].forEach(([x1, y1, x2, y2]) => {
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    });

    // Center dot
    ctx.beginPath(); ctx.arc(x, y, 2.5, 0, Math.PI * 2);
    ctx.fillStyle = isLocked ? 'rgba(56, 189, 248, 0.9)' : 'rgba(244, 63, 94, 0.9)';
    ctx.fill();

    // Outer ring
    ctx.beginPath(); ctx.arc(x, y, 14, 0, Math.PI * 2);
    ctx.strokeStyle = isLocked ? 'rgba(56, 189, 248, 0.4)' : 'rgba(244, 63, 94, 0.3)';
    ctx.lineWidth = 1;
    ctx.stroke();
}

// =============================================
// 🎯 TARGET DRAWING
// =============================================
function drawTarget(t, coords, now) {
    const elapsed = now - t.spawnTime;

    if (t.state === 'preview') {
        const progress = Math.min(elapsed / t.previewDuration, 1);
        // Shrinking preview ring
        ctx.beginPath();
        ctx.arc(t.x, t.y, t.radius * (2.5 - progress * 1.5), 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(255,255,255,${0.12 + progress * 0.2})`;
        ctx.setLineDash([6, 6]);
        ctx.lineWidth = 1.5;
        ctx.stroke();
        ctx.setLineDash([]);
        if (elapsed > t.previewDuration) t.state = 'active';
        return false;
    }

    // Active state
    const activeElapsed = elapsed - t.previewDuration;
    const expireProgress = Math.min(activeElapsed / TARGET_LIFETIME, 1);

    // Drift
    t.x += t.vx; t.y += t.vy;
    if (t.x < t.radius + 10 || t.x > canvas.width - t.radius - 10) t.vx *= -1;
    if (t.y < t.radius + 10 || t.y > canvas.height - t.radius - 10) t.vy *= -1;

    if (expireProgress >= 1) {
        // Auto-miss
        missCount++;
        combo = 0;
        playMissSound();
        spawnScorePopup(t.x, t.y - 35, 'MISS', '#f43f5e');
        return true; // remove
    }

    const dist = Math.hypot(coords.x - t.x, coords.y - t.y);
    const isHover = dist < t.radius;

    // Dwell
    if (isHover) {
        t.dwell += 16.6;
        const bucket = Math.floor((t.dwell / t.maxDwell) * 8);
        if (bucket !== t.lastTickBucket) {
            playDwellTick(t.dwell / t.maxDwell);
            t.lastTickBucket = bucket;
        }
    } else {
        t.dwell = Math.max(0, t.dwell - 9);
        t.lastTickBucket = Math.floor((t.dwell / t.maxDwell) * 8);
    }

    // --- DRAW ---
    // Expiry warning ring (red, fills in as time runs out)
    ctx.beginPath();
    ctx.arc(t.x, t.y, t.radius + 10, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * expireProgress);
    ctx.strokeStyle = `rgba(244, 63, 94, ${0.3 + expireProgress * 0.6})`;
    ctx.lineWidth = 3;
    ctx.stroke();

    // Outer glow when hovered
    if (isHover) {
        const grd = ctx.createRadialGradient(t.x, t.y, t.radius * 0.5, t.x, t.y, t.radius * 2.2);
        grd.addColorStop(0, 'rgba(56, 189, 248, 0.25)');
        grd.addColorStop(1, 'rgba(56, 189, 248, 0)');
        ctx.beginPath(); ctx.arc(t.x, t.y, t.radius * 2.2, 0, Math.PI * 2);
        ctx.fillStyle = grd; ctx.fill();
    }

    // Dwell fill (arc sector)
    if (t.dwell > 0) {
        ctx.beginPath();
        ctx.moveTo(t.x, t.y);
        ctx.arc(t.x, t.y, t.radius * 0.88, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * (t.dwell / t.maxDwell));
        ctx.fillStyle = `rgba(56, 189, 248, 0.30)`;
        ctx.fill();
    }

    // Concentric target rings (3 rings like real sniper scope)
    const ringData = [
        { r: t.radius, w: 2.5 },
        { r: t.radius * 0.62, w: 1.5 },
        { r: t.radius * 0.28, w: 1.2 },
    ];
    ringData.forEach(({ r, w }) => {
        ctx.beginPath();
        ctx.arc(t.x, t.y, r, 0, Math.PI * 2);
        ctx.strokeStyle = isHover ? '#38bdf8' : '#f43f5e';
        ctx.lineWidth = w;
        ctx.stroke();
    });

    // Center dot
    ctx.beginPath();
    ctx.arc(t.x, t.y, 3, 0, Math.PI * 2);
    ctx.fillStyle = isHover ? '#38bdf8' : '#f43f5e';
    ctx.fill();

    // Cross lines inside target
    ctx.strokeStyle = isHover ? 'rgba(56, 189, 248, 0.5)' : 'rgba(244, 63, 94, 0.4)';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(t.x - t.radius, t.y); ctx.lineTo(t.x + t.radius, t.y); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(t.x, t.y - t.radius); ctx.lineTo(t.x, t.y + t.radius); ctx.stroke();

    // Success!
    if (t.dwell >= t.maxDwell) {
        combo++;
        maxCombo = Math.max(maxCombo, combo);
        const pts = Math.round((100 - t.radius) * (1 + combo * 0.3));
        score += pts;
        playLockOn();
        spawnExplosion(t.x, t.y, t.radius);
        const popText = combo > 1 ? `+${pts}  ${combo}🔥COMBO` : `+${pts}  LOCKED!`;
        spawnScorePopup(t.x, t.y - 30, popText, combo > 2 ? '#ffd93d' : '#4ade80');
        Tracker.logEvent('dwell_success', { radius: t.radius, combo, pts });
        return true; // remove
    }

    return false;
}

// =============================================
// 🔄 GAME LOOP
// =============================================
let anyHovered = false;

function update(now) {
    if (isGameOver) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const coords = Pointer.getRelativeCoords(canvas);

    anyHovered = targets.some(t =>
        t.state === 'active' && Math.hypot(coords.x - t.x, coords.y - t.y) < t.radius
    );

    // Crosshair
    drawCrosshair(coords.x, coords.y, anyHovered);

    // Targets (iterate safely)
    const toRemove = [];
    targets.forEach((t, i) => {
        if (drawTarget(t, coords, now)) toRemove.push(i);
    });
    for (let i = toRemove.length - 1; i >= 0; i--) targets.splice(toRemove[i], 1);

    // Particles
    particles.forEach(p => {
        p.x += p.vx; p.y += p.vy;
        p.vx *= 0.95; p.vy *= 0.95;
        p.life -= p.decay;
        ctx.beginPath();
        ctx.arc(p.x, p.y, Math.max(0, p.size * p.life), 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = p.life;
        ctx.fill();
        ctx.globalAlpha = 1;
    });
    particles = particles.filter(p => p.life > 0);

    // Score popups
    scorePopups.forEach(sp => {
        sp.y += sp.vy; sp.life -= 0.022;
        ctx.font = `bold 20px Arial`;
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
    ctx.textAlign = 'left';
    ctx.fillStyle = 'white';
    ctx.font = 'bold 28px Arial';
    ctx.fillText(`Score: ${score}`, 30, 48);

    if (combo >= 2) {
        ctx.font = 'bold 20px Arial';
        ctx.fillStyle = '#ffd93d';
        ctx.shadowColor = '#ffd93d';
        ctx.shadowBlur = 8;
        ctx.fillText(`🔥 ${combo} COMBO`, 30, 76);
        ctx.shadowBlur = 0;
    }

    ctx.textAlign = 'right';
    ctx.font = '18px Arial';
    ctx.fillStyle = missCount > 0 ? '#f43f5e' : 'rgba(255,255,255,0.4)';
    ctx.fillText(`❌ Miss: ${missCount}`, canvas.width - 30, 76);

    ctx.fillStyle = timeLeft <= 10 ? '#f43f5e' : 'white';
    ctx.font = 'bold 28px Arial';
    ctx.fillText(`⏱ ${Math.ceil(timeLeft)}s`, canvas.width - 30, 48);
    ctx.textAlign = 'left';
}

// =============================================
// 💀 GAME OVER SCREEN
// =============================================
function showGameOver() {
    ctx.fillStyle = 'rgba(0,0,0,0.82)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.textAlign = 'center';

    ctx.fillStyle = '#38bdf8';
    ctx.font = 'bold 52px Arial';
    ctx.shadowColor = '#38bdf8';
    ctx.shadowBlur = 22;
    ctx.fillText('GAME OVER', canvas.width / 2, 195);
    ctx.shadowBlur = 0;

    ctx.fillStyle = 'white';
    ctx.font = 'bold 34px Arial';
    ctx.fillText(`최종 점수: ${score}`, canvas.width / 2, 262);

    ctx.fillStyle = '#ffd93d';
    ctx.font = '24px Arial';
    ctx.fillText(`🔥 최대 콤보: ${maxCombo}회`, canvas.width / 2, 308);

    ctx.fillStyle = '#f43f5e';
    ctx.fillText(`❌ 미스: ${missCount}회`, canvas.width / 2, 350);

    // Grade
    let grade;
    if (missCount === 0 && maxCombo >= 8) grade = '🏆 SHARPSHOOTER';
    else if (score >= 800) grade = '🥇 MARKSMAN';
    else if (score >= 400) grade = '🥈 RIFLEMAN';
    else grade = '🥉 RECRUIT';
    ctx.fillStyle = '#a8ff78';
    ctx.font = 'bold 24px Arial';
    ctx.fillText(grade, canvas.width / 2, 393);

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
Tracker.startSession('sniper');
spawnTarget();
requestAnimationFrame(update);

const timer = setInterval(() => {
    timeLeft = Math.max(0, timeLeft - 1);
    if (timeLeft <= 0) {
        isGameOver = true;
        clearInterval(timer);
        Tracker.endSession();
        setTimeout(showGameOver, 200);
    }
}, 1000);
