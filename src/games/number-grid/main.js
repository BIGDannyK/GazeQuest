const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

// 2-minute demo tuning.
const DWELL_TIME = 650;
const COOLDOWN = 280;

// More "game-like" 1~16 mission. The number order forces the player
// to scan around the grid instead of simply moving in a straight line.
const grid = [
  [5, 1, 13, 9],
  [3, 15, 11, 7],
  [8, 16, 2, 12],
  [10, 6, 14, 4],
];
const SIZE = 4;
const CELL = 98;
const boardX = 305;
const boardY = 110;
const maxTarget = 16;

let current = { row: 1, col: 1 }; // starts near center
let target = 1;
let running = false;
let finished = false;
let startTime = 0;
let endTime = 0;
let moves = 0;
let selects = 0;
let wrong = 0;
let lastCommand = 'IDLE';
let commandStart = 0;
let cooldownUntil = 0;
let message = '';
let messageUntil = 0;
let inputCooldownUntil = 0;
let messageGood = true;
let lastCorrectCell = null;

function resetGame() {
  current = { row: 1, col: 1 };
  target = 1;
  running = true;
  finished = false;
  startTime = performance.now();
  endTime = 0;
  moves = 0;
  selects = 0;
  wrong = 0;
  lastCommand = 'IDLE';
  commandStart = 0;
  cooldownUntil = 0;
  message = '';
  lastCorrectCell = null;
  if (window.Tracker) Tracker.startSession('number-grid');
}

function finishGame() {
  finished = true;
  running = false;
  endTime = performance.now();
  const completeTime = (endTime - startTime) / 1000;
  if (window.Tracker) {
    Tracker.logEvent('complete', { completeTime, moves, selects, wrong, maxTarget });
    Tracker.endSession({ metrics: { completeTime, moves, selects, wrong, maxTarget } });
  }
}

function showMessage(text, good = true) {
  message = text;
  messageGood = good;
  messageUntil = performance.now() + 650;
}

function move(cmd) {
  if (!running || finished) return;
  let nr = current.row;
  let nc = current.col;
  if (cmd === 'UP') nr--;
  if (cmd === 'DOWN') nr++;
  if (cmd === 'LEFT') nc--;
  if (cmd === 'RIGHT') nc++;
  if (nr < 0 || nr >= SIZE || nc < 0 || nc >= SIZE) {
    wrong++;
    showMessage('EDGE', false);
    if (window.Tracker) Tracker.logEvent('edge_hit', { cmd });
    return;
  }
  current.row = nr;
  current.col = nc;
  moves++;
  showMessage(cmd, true);
  if (window.Tracker) Tracker.logEvent('move', { cmd, row: nr, col: nc });
}

function selectCurrent() {
  const now = performance.now();
  if (now < inputCooldownUntil) return;
  inputCooldownUntil = now + 220;

  if (!running || finished) {
    resetGame();
    return;
  }

  selects++;
  const value = grid[current.row][current.col];
  if (value === target) {
    lastCorrectCell = { row: current.row, col: current.col, value };
    showMessage(`OK ${target}`, true);
    if (window.Tracker) Tracker.logEvent('select_correct', { value, row: current.row, col: current.col });
    target++;
    if (target > maxTarget) finishGame();
  } else {
    wrong++;
    showMessage(`WRONG ${value}`, false);
    if (window.Tracker) Tracker.logEvent('select_wrong', { value, target, row: current.row, col: current.col });
  }
}

function updateCommand() {
  const now = performance.now();
  const cmd = window.Pointer ? Pointer.getCommand() : 'IDLE';
  if (!running || finished || now < cooldownUntil) return cmd;

  if (cmd !== lastCommand) {
    lastCommand = cmd;
    commandStart = now;
  } else if (cmd !== 'IDLE' && now - commandStart >= DWELL_TIME) {
    move(cmd);
    cooldownUntil = now + COOLDOWN;
    commandStart = now;
  }
  return cmd;
}

function elapsed() {
  if (!startTime) return 0;
  return ((finished ? endTime : performance.now()) - startTime) / 1000;
}

function drawZones(cmd) {
  ctx.save();
  ctx.globalAlpha = 0.12;
  ctx.fillStyle = '#38bdf8';
  if (cmd === 'UP') ctx.fillRect(0, 0, canvas.width, 90);
  if (cmd === 'DOWN') ctx.fillRect(0, canvas.height - 90, canvas.width, 90);
  if (cmd === 'LEFT') ctx.fillRect(0, 0, 130, canvas.height);
  if (cmd === 'RIGHT') ctx.fillRect(canvas.width - 130, 0, 130, canvas.height);
  ctx.restore();
}

function drawProgressBar() {
  const x = 36;
  const y = 342;
  const w = 210;
  const h = 16;
  const progress = Math.max(0, Math.min((target - 1) / maxTarget, 1));
  ctx.fillStyle = '#334155';
  ctx.fillRect(x, y, w, h);
  ctx.fillStyle = '#38bdf8';
  ctx.fillRect(x, y, w * progress, h);
  ctx.strokeStyle = '#64748b';
  ctx.strokeRect(x, y, w, h);
  ctx.fillStyle = '#94a3b8';
  ctx.font = '14px Arial';
  ctx.fillText(`Progress: ${target - 1}/${maxTarget}`, x, y + 38);
}

function drawGrid() {
  for (let r = 0; r < SIZE; r++) {
    for (let c = 0; c < SIZE; c++) {
      const x = boardX + c * CELL;
      const y = boardY + r * CELL;
      const value = grid[r][c];
      const done = value < target;
      const isCurrent = r === current.row && c === current.col;
      const isNext = value === target;
      const wasLastCorrect = lastCorrectCell && lastCorrectCell.row === r && lastCorrectCell.col === c;

      ctx.fillStyle = done ? '#14532d' : '#e2e8f0';
      if (isNext && running && !finished) ctx.fillStyle = '#dbeafe';
      ctx.fillRect(x, y, CELL - 8, CELL - 8);

      if (isNext && running && !finished) {
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 4;
        ctx.strokeRect(x + 5, y + 5, CELL - 18, CELL - 18);
      }

      ctx.strokeStyle = isCurrent ? '#facc15' : '#334155';
      ctx.lineWidth = isCurrent ? 7 : 2;
      ctx.strokeRect(x, y, CELL - 8, CELL - 8);

      if (wasLastCorrect && performance.now() < messageUntil) {
        ctx.strokeStyle = '#22c55e';
        ctx.lineWidth = 7;
        ctx.strokeRect(x + 9, y + 9, CELL - 26, CELL - 26);
      }

      ctx.fillStyle = done ? '#86efac' : '#0f172a';
      ctx.font = 'bold 38px Arial';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(value, x + (CELL - 8) / 2, y + (CELL - 8) / 2);
    }
  }
  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';
}

function drawText(cmd) {
  ctx.fillStyle = '#e5e7eb';
  ctx.font = 'bold 34px Arial';
  ctx.fillText('Number Grid 1-16', 36, 58);
  ctx.font = '18px Arial';
  ctx.fillStyle = '#94a3b8';
  ctx.fillText('Move highlight with gaze. Press SPACE to select the current cell.', 36, 88);

  ctx.fillStyle = '#e5e7eb';
  ctx.font = 'bold 20px Arial';
  ctx.fillText(`Target: ${Math.min(target, maxTarget)} / ${maxTarget}`, 36, 145);
  ctx.fillText(`Time: ${elapsed().toFixed(1)}s`, 36, 178);
  ctx.fillText(`Moves: ${moves}`, 36, 211);
  ctx.fillText(`Selects: ${selects}`, 36, 244);
  ctx.fillText(`Wrong: ${wrong}`, 36, 277);
  ctx.fillText(`Command: ${cmd}`, 36, 310);
  drawProgressBar();

  if (!running && !finished) {
    ctx.fillStyle = '#38bdf8';
    ctx.font = 'bold 30px Arial';
    ctx.fillText('Press SPACE to start', 365, 560);
  }

  if (performance.now() < messageUntil) {
    ctx.fillStyle = messageGood ? '#a7f3d0' : '#fb7185';
    ctx.font = 'bold 42px Arial';
    ctx.fillText(message, 420, 62);
  }

  if (finished) {
    ctx.fillStyle = 'rgba(15,23,42,0.88)';
    ctx.fillRect(250, 150, 500, 300);
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 3;
    ctx.strokeRect(250, 150, 500, 300);
    ctx.fillStyle = '#a7f3d0';
    ctx.font = 'bold 44px Arial';
    ctx.fillText('COMPLETE!', 365, 212);
    ctx.fillStyle = '#e5e7eb';
    ctx.font = '24px Arial';
    ctx.fillText(`Time: ${elapsed().toFixed(1)}s`, 380, 268);
    ctx.fillText(`Moves: ${moves}`, 380, 306);
    ctx.fillText(`Selects: ${selects}`, 380, 344);
    ctx.fillText(`Wrong: ${wrong}`, 380, 382);
    ctx.fillStyle = '#94a3b8';
    ctx.font = '18px Arial';
    ctx.fillText('Press SPACE to restart', 400, 424);
  }
}

function draw() {
  const cmd = updateCommand();
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawZones(cmd);
  drawGrid();
  drawText(cmd);
  requestAnimationFrame(draw);
}

window.addEventListener('click', selectCurrent);
window.addEventListener('keydown', (e) => {
  if (e.code === 'Space') { e.preventDefault(); selectCurrent(); }
  const keyMap = { ArrowUp: 'UP', ArrowDown: 'DOWN', ArrowLeft: 'LEFT', ArrowRight: 'RIGHT' };
  if (keyMap[e.code]) { e.preventDefault(); move(keyMap[e.code]); }
});

draw();
