// =============================================
// 🔊 AUDIO ENGINE - Continuous tracking tone
// =============================================
const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;
function getAudio() { if (!audioCtx) audioCtx = new AudioCtx(); return audioCtx; }

let trackingOsc = null, trackingGainNode = null;
let wasTracking = false;

function startTrackingTone(progress) {
    if (trackingOsc) {
        trackingOsc.frequency.value = 280 + progress * 380;
        return;
    }
    const ac = getAudio();
    trackingOsc = ac.createOscillator();
    trackingGainNode = ac.createGain();
    trackingOsc.connect(trackingGainNode);
    trackingGainNode.connect(ac.destination);
    trackingOsc.type = 'sine';
    trackingOsc.frequency.value = 280 + progress * 380;
    trackingGainNode.gain.setValueAtTime(0, ac.currentTime);
    trackingGainNode.gain.linearRampToValueAtTime(0.08, ac.currentTime + 0.05);
    trackingOsc.start();
}

function stopTrackingTone() {
    if (!trackingOsc) return;
    const ac = getAudio();
    trackingGainNode.gain.linearRampToValueAtTime(0, ac.currentTime + 0.08);
    const osc = trackingOsc;
    trackingOsc = null;
    trackingGainNode = null;
    setTimeout(() => { try { osc.stop(); } catch(e) {} }, 100);
}

function playSliderComplete(rate) {
    const ac = getAudio();
    const freq = rate >= 90 ? 784 : rate >= 60 ? 523 : 294;
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.connect(gain); gain.connect(ac.destination);
    osc.type = 'sine'; osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.25, ac.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.35);
    osc.start(); osc.stop(ac.currentTime + 0.35);
}

// =============================================
// 🎮 GAME STATE
// =============================================
const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

let sliders = [], particles = [], gradePopups = [], cursorTrail = [];
let score = 0, combo = 0, maxCombo = 0;
let totalTicks = 0, hitTicks = 0;
let timeLeft = 30, isGameOver = false;
let isCurrentlyTracking = false;

// =============================================
// ✨ EFFECTS
// =============================================
function spawnParticles(x, y, isHit) {
    if (Math.random() > 0.25) return; // throttle
    const color = isHit ? '#4ade80' : '#f87171';
    for (let i = 0; i < 4; i++) {
        const angle = Math.random() * Math.PI * 2;
        const speed = 1 + Math.random() * 3;
        particles.push({
            x, y,
            vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
            life: 1.0, decay: 0.055 + Math.random() * 0.03,
            size: 3 + Math.random() * 3, color
        });
    }
}

function spawnGradePopup(x, y, text, color) {
    gradePopups.push({ x, y, text, color, life: 1.0, vy: -1.6 });
}

// =============================================
// 🎵 SLIDER MANAGEMENT
// =============================================
const randPt = () => ({
    x: Math.random() * (canvas.width - 200) + 100,
    y: Math.random() * (canvas.height - 200) + 100
});

function spawnSlider() {
    if (isGameOver) return;
    const types = ['line', 'curve', 'zigzag'];
    const type = types[Math.floor(Math.random() * types.length)];
    let s = {
        type, radius: 35,
        spawnTime: performance.now(),
        approachDuration: 900,
        state: 'approach',
        completionHits: 0,
        completionTotal: 0
    };
    let totalLength = 0;

    if (type === 'line') {
        s.points = [randPt(), randPt()];
        totalLength = Math.hypot(s.points[1].x - s.points[0].x, s.points[1].y - s.points[0].y);
        s.startX = s.points[0].x; s.startY = s.points[0].y;
    } else if (type === 'zigzag') {
        s.points = [randPt(), randPt(), randPt()];
        totalLength = Math.hypot(s.points[1].x - s.points[0].x, s.points[1].y - s.points[0].y) +
                      Math.hypot(s.points[2].x - s.points[1].x, s.points[2].y - s.points[1].y);
        s.startX = s.points[0].x; s.startY = s.points[0].y;
    } else if (type === 'curve') {
        s.cx = randPt().x; s.cy = randPt().y;
        s.r = Math.random() * 100 + 80;
        s.startAngle = Math.random() * Math.PI * 2;
        const sweep = (Math.PI + Math.random() * Math.PI * 0.5) * (Math.random() > 0.5 ? 1 : -1);
        s.endAngle = s.startAngle + sweep;
        s.ccw = sweep < 0;
        totalLength = Math.abs(sweep) * s.r;
        s.startX = s.cx + Math.cos(s.startAngle) * s.r;
        s.startY = s.cy + Math.sin(s.startAngle) * s.r;
    }

    s.travelDuration = Math.max(1000, Math.min((totalLength / 240) * 1000, 4000));
    sliders.push(s);
}

function getPos(s, progress) {
    if (s.type === 'line' || s.type === 'zigzag') {
        const segs = s.points.length - 1;
        const scaled = progress * segs;
        const idx = Math.min(Math.floor(scaled), segs - 1);
        const t = scaled - idx;
        const p1 = s.points[idx], p2 = s.points[idx + 1];
        return { x: p1.x + (p2.x - p1.x) * t, y: p1.y + (p2.y - p1.y) * t };
    } else {
        const angle = s.startAngle + (s.endAngle - s.startAngle) * progress;
        return { x: s.cx + Math.cos(angle) * s.r, y: s.cy + Math.sin(angle) * s.r };
    }
}

// =============================================
// 🖱️ CURSOR TRAIL
// =============================================
canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    cursorTrail.push({ x: e.clientX - rect.left, y: e.clientY - rect.top, life: 1.0 });
    if (cursorTrail.length > 35) cursorTrail.shift();
});

// =============================================
// 🔄 GAME LOOP
// =============================================
function update(now) {
    if (isGameOver) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const coords = Pointer.getRelativeCoords(canvas);
    isCurrentlyTracking = false;

    // --- CURSOR TRAIL ---
    for (let i = 1; i < cursorTrail.length; i++) {
        const t = cursorTrail[i];
        const prev = cursorTrail[i - 1];
        t.life -= 0.055;
        const w = 16 * t.life * (i / cursorTrail.length);
        ctx.beginPath();
        ctx.moveTo(prev.x, prev.y);
        ctx.lineTo(t.x, t.y);
        ctx.strokeStyle = `rgba(56, 189, 248, ${t.life * 0.45})`;
        ctx.lineWidth = w;
        ctx.lineCap = 'round';
        ctx.stroke();
    }
    cursorTrail = cursorTrail.filter(t => t.life > 0);

    // --- SLIDERS ---
    const toRemove = [];
    sliders.forEach((s, si) => {
        const elapsed = now - s.spawnTime;

        // === Draw Track Path ===
        ctx.save();
        ctx.beginPath();
        if (s.type === 'line' || s.type === 'zigzag') {
            ctx.moveTo(s.points[0].x, s.points[0].y);
            s.points.forEach(p => ctx.lineTo(p.x, p.y));
        } else if (s.type === 'curve') {
            ctx.arc(s.cx, s.cy, s.r, s.startAngle, s.endAngle, s.ccw);
        }
        // Outer glow
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.08)';
        ctx.lineWidth = s.radius * 3.5;
        ctx.lineCap = 'round'; ctx.lineJoin = 'round';
        ctx.stroke();
        // Inner track
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
        ctx.lineWidth = s.radius * 2;
        ctx.stroke();
        // Track border lines
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.3)';
        ctx.lineWidth = 1.5;
        ctx.stroke();
        ctx.restore();

        // === APPROACH STATE ===
        if (s.state === 'approach') {
            const progress = Math.min(elapsed / s.approachDuration, 1);

            // Start circle glow
            const grd = ctx.createRadialGradient(s.startX, s.startY, 0, s.startX, s.startY, s.radius * 1.8);
            grd.addColorStop(0, 'rgba(56, 189, 248, 0.4)');
            grd.addColorStop(1, 'rgba(56, 189, 248, 0)');
            ctx.beginPath(); ctx.arc(s.startX, s.startY, s.radius * 1.8, 0, Math.PI * 2);
            ctx.fillStyle = grd; ctx.fill();

            // Start circle
            ctx.beginPath(); ctx.arc(s.startX, s.startY, s.radius, 0, Math.PI * 2);
            const ballGrd = ctx.createRadialGradient(s.startX - 8, s.startY - 8, 0, s.startX, s.startY, s.radius);
            ballGrd.addColorStop(0, '#7dd3fc');
            ballGrd.addColorStop(1, '#0ea5e9');
            ctx.fillStyle = ballGrd; ctx.fill();

            // Shrinking approach ring
            const ringR = s.radius * (2.4 - progress * 1.4);
            ctx.beginPath(); ctx.arc(s.startX, s.startY, ringR, 0, Math.PI * 2);
            ctx.strokeStyle = `rgba(255, 255, 255, ${(1 - progress) * 0.9})`;
            ctx.lineWidth = 2; ctx.stroke();

            if (elapsed >= s.approachDuration) s.state = 'moving';

        // === MOVING STATE ===
        } else if (s.state === 'moving') {
            const progress = Math.min((elapsed - s.approachDuration) / s.travelDuration, 1);
            const pos = getPos(s, progress);

            const dist = Math.hypot(coords.x - pos.x, coords.y - pos.y);
            const isTracking = dist < s.radius * 1.5;

            s.completionTotal++;
            totalTicks++;

            if (isTracking) {
                s.completionHits++;
                hitTicks++;
                combo++;
                maxCombo = Math.max(maxCombo, combo);
                const mult = getMultiplier(combo);
                score += Math.round(2 * mult);
                isCurrentlyTracking = true;
                startTrackingTone(progress);
                spawnParticles(pos.x, pos.y, true);
            } else {
                if (combo > 0) combo = 0;
                spawnParticles(pos.x, pos.y, false);
            }

            Tracker.logEvent('tracking_tick', { type: s.type, isHit: isTracking, errorDist: dist });

            // Ball glow
            if (isTracking) {
                const grd = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, s.radius * 2.5);
                grd.addColorStop(0, 'rgba(74, 222, 128, 0.55)');
                grd.addColorStop(1, 'rgba(74, 222, 128, 0)');
                ctx.beginPath(); ctx.arc(pos.x, pos.y, s.radius * 2.5, 0, Math.PI * 2);
                ctx.fillStyle = grd; ctx.fill();
            }

            // Ball body with gradient
            ctx.beginPath(); ctx.arc(pos.x, pos.y, s.radius, 0, Math.PI * 2);
            const ballGrd = ctx.createRadialGradient(pos.x - s.radius * 0.35, pos.y - s.radius * 0.35, 0, pos.x, pos.y, s.radius);
            ballGrd.addColorStop(0, '#ffffff');
            ballGrd.addColorStop(0.5, isTracking ? '#4ade80' : '#f87171');
            ballGrd.addColorStop(1, isTracking ? '#16a34a' : '#dc2626');
            ctx.fillStyle = ballGrd; ctx.fill();

            // Progress arc on ball
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, s.radius + 5, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * progress);
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
            ctx.lineWidth = 2; ctx.stroke();

            if (progress >= 1) {
                const rate = s.completionTotal > 0
                    ? Math.round((s.completionHits / s.completionTotal) * 100) : 0;
                let grade, color;
                if (rate >= 90) { grade = '✨ PERFECT'; color = '#ffd93d'; }
                else if (rate >= 70) { grade = '👍 GOOD'; color = '#4ade80'; }
                else if (rate >= 40) { grade = '😬 OK'; color = '#94a3b8'; }
                else { grade = '💔 MISS'; color = '#f87171'; }
                spawnGradePopup(pos.x, pos.y - 20, `${grade}  ${rate}%`, color);
                playSliderComplete(rate);
                Tracker.logEvent('slider_end', { completionRate: rate, type: s.type });
                s.state = 'done';
            }
        }

        if (s.state === 'done') {
            toRemove.push(si);
            if (!isGameOver) setTimeout(spawnSlider, 280);
        }
    });

    for (let i = toRemove.length - 1; i >= 0; i--) sliders.splice(toRemove[i], 1);

    // Tracking sound management
    if (!isCurrentlyTracking && wasTracking) {
        stopTrackingTone();
    }
    wasTracking = isCurrentlyTracking;

    // --- PARTICLES ---
    particles.forEach(p => {
        p.x += p.vx; p.y += p.vy;
        p.vx *= 0.97; p.vy *= 0.97;
        p.life -= p.decay;
        ctx.beginPath();
        ctx.arc(p.x, p.y, Math.max(0, p.size * p.life), 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = p.life;
        ctx.fill();
        ctx.globalAlpha = 1;
    });
    particles = particles.filter(p => p.life > 0);

    // --- GRADE POPUPS ---
    gradePopups.forEach(gp => {
        gp.y += gp.vy; gp.life -= 0.018;
        ctx.font = `bold 22px Arial`;
        ctx.fillStyle = gp.color;
        ctx.globalAlpha = gp.life;
        ctx.textAlign = 'center';
        ctx.shadowColor = gp.color;
        ctx.shadowBlur = 10;
        ctx.fillText(gp.text, gp.x, gp.y);
        ctx.shadowBlur = 0;
        ctx.globalAlpha = 1;
    });
    gradePopups = gradePopups.filter(gp => gp.life > 0);

    drawUI();
    requestAnimationFrame(update);
}

function getMultiplier(combo) {
    if (combo >= 30) return 3.0;
    if (combo >= 20) return 2.5;
    if (combo >= 10) return 2.0;
    if (combo >= 5)  return 1.5;
    return 1.0;
}

// =============================================
// 🖼️ UI
// =============================================
function drawUI() {
    const accuracy = totalTicks > 0 ? Math.round((hitTicks / totalTicks) * 100) : 100;

    ctx.textAlign = 'left';
    ctx.fillStyle = 'white';
    ctx.font = 'bold 28px Arial';
    ctx.fillText(`Score: ${score}`, 30, 48);

    ctx.font = '18px Arial';
    ctx.fillStyle = accuracy >= 80 ? '#4ade80' : accuracy >= 50 ? '#ffd93d' : '#f87171';
    ctx.fillText(`Accuracy: ${accuracy}%`, 30, 74);

    if (combo >= 5) {
        const mult = getMultiplier(combo);
        ctx.font = 'bold 20px Arial';
        ctx.fillStyle = '#ffd93d';
        ctx.shadowColor = '#ffd93d';
        ctx.shadowBlur = 10;
        ctx.fillText(`🔥 ${combo} COMBO  ×${mult.toFixed(1)}`, 30, 100);
        ctx.shadowBlur = 0;
    }

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
    const accuracy = totalTicks > 0 ? Math.round((hitTicks / totalTicks) * 100) : 0;

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

    ctx.fillStyle = accuracy >= 80 ? '#4ade80' : '#ffd93d';
    ctx.font = '24px Arial';
    ctx.fillText(`🎯 추적 정확도: ${accuracy}%`, canvas.width / 2, 308);

    ctx.fillStyle = '#ffd93d';
    ctx.fillText(`🔥 최대 콤보: ${maxCombo}`, canvas.width / 2, 350);

    let grade;
    if (accuracy >= 90 && maxCombo >= 20) grade = '🏆 MAESTRO';
    else if (accuracy >= 75) grade = '🥇 TRACKER';
    else if (accuracy >= 50) grade = '🥈 FOLLOWER';
    else grade = '🥉 TRAINEE';
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
Tracker.startSession('rhythm');
spawnSlider();
requestAnimationFrame(update);

const timer = setInterval(() => {
    timeLeft = Math.max(0, timeLeft - 1);
    if (timeLeft <= 0) {
        isGameOver = true;
        clearInterval(timer);
        stopTrackingTone();
        Tracker.endSession();
        setTimeout(showGameOver, 200);
    }
}, 1000);
