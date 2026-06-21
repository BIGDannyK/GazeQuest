const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

// 2-minute demo tuning: each gaze direction must be held briefly.
const DWELL_TIME = 650;
const COOLDOWN = 280;

// 11x11 mixed-turn maze: short segments only, so the demo does not repeat
// the same gaze direction for too long. 1 = wall, 0 = path
const maze = [
  [1,1,1,1,1,1,1,1,1,1,1],
  [1,1,1,1,1,1,1,1,1,0,1],
  [1,1,1,1,1,1,1,0,0,0,1],
  [1,1,1,1,1,1,1,0,1,1,1],
  [1,1,1,1,1,1,0,0,1,1,1],
  [1,1,1,1,0,0,0,1,1,1,1],
  [1,1,1,1,0,0,1,1,1,1,1],
  [1,1,1,1,1,0,1,1,1,1,1],
  [1,1,1,0,0,0,1,1,1,1,1],
  [1,0,0,0,1,1,1,1,1,1,1],
  [1,1,1,1,1,1,1,1,1,1,1],
];

const ROWS = maze.length;
const COLS = maze[0].length;
const CELL = 42;
const boardX = 345;
const boardY = 78;
const start = { row: 9, col: 1 };
const goal = { row: 1, col: 9 };

let player = { ...start };
let running = false;
let finished = false;
let startTime = 0;
let endTime = 0;
let moves = 0;
let wallHits = 0;
let lastCommand = 'IDLE';
let commandStart = 0;
let cooldownUntil = 0;
let flashMessage = '';
let flashUntil = 0;
let routeHint = 'Mixed route: short LEFT/RIGHT/UP turns, no long repeated direction.';

function resetGame() {
  player = { ...start };
  running = true;
  finished = false;
  startTime = performance.now();
  endTime = 0;
  moves = 0;
  wallHits = 0;
  lastCommand = 'IDLE';
  commandStart = 0;
  cooldownUntil = 0;
  flashMessage = '';
  if (window.Tracker) Tracker.startSession('eye-maze');
}

function finishGame() {
  finished = true;
  running = false;
  endTime = performance.now();
  const clearTime = (endTime - startTime) / 1000;
  if (window.Tracker) {
    Tracker.logEvent('clear', { clearTime, moves, wallHits, maze: '11x11-mixed-turn' });
    Tracker.endSession({ metrics: { clearTime, moves, wallHits, maze: '11x11-mixed-turn' } });
  }
}

function showFlash(msg) {
  flashMessage = msg;
  flashUntil = performance.now() + 450;
}

function executeCommand(cmd) {
  if (!running || finished || cmd === 'IDLE') return;
  let nr = player.row;
  let nc = player.col;
  if (cmd === 'UP') nr--;
  if (cmd === 'DOWN') nr++;
  if (cmd === 'LEFT') nc--;
  if (cmd === 'RIGHT') nc++;

  if (maze[nr]?.[nc] === 0) {
    player.row = nr;
    player.col = nc;
    moves++;
    showFlash(cmd);
    if (window.Tracker) Tracker.logEvent('move', { cmd, row: nr, col: nc });
  } else {
    wallHits++;
    showFlash('WALL');
    if (window.Tracker) Tracker.logEvent('wall_hit', { cmd, row: nr, col: nc });
  }

  if (player.row === goal.row && player.col === goal.col) finishGame();
}

function updateCommand() {
  const now = performance.now();
  const cmd = window.Pointer ? Pointer.getCommand() : 'IDLE';
  if (!running || finished || now < cooldownUntil) return cmd;

  if (cmd !== lastCommand) {
    lastCommand = cmd;
    commandStart = now;
  } else if (cmd !== 'IDLE' && now - commandStart >= DWELL_TIME) {
    executeCommand(cmd);
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

function drawBoard() {
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const x = boardX + c * CELL;
      const y = boardY + r * CELL;
      const isPath = maze[r][c] === 0;
      ctx.fillStyle = isPath ? '#e2e8f0' : '#334155';
      ctx.fillRect(x, y, CELL - 3, CELL - 3);

      if (isPath) {
        ctx.strokeStyle = 'rgba(15,23,42,0.14)';
        ctx.lineWidth = 1;
        ctx.strokeRect(x, y, CELL - 3, CELL - 3);
      }

      if (r === start.row && c === start.col) {
        ctx.fillStyle = '#38bdf8';
        ctx.font = '22px Arial';
        ctx.fillText('S', x + 12, y + 28);
      }

      if (r === goal.row && c === goal.col) {
        ctx.fillStyle = '#22c55e';
        ctx.font = '26px Arial';
        ctx.fillText('🏁', x + 6, y + 30);
      }
    }
  }

  const px = boardX + player.col * CELL;
  const py = boardY + player.row * CELL;
  ctx.fillStyle = '#facc15';
  ctx.beginPath();
  ctx.arc(px + CELL / 2 - 2, py + CELL / 2 - 2, 16, 0, Math.PI * 2);
  ctx.fill();
  ctx.font = '22px Arial';
  ctx.fillText('🙂', px + 8, py + 30);
}

function drawMiniRoute() {
  ctx.fillStyle = '#94a3b8';
  ctx.font = '15px Arial';
  ctx.fillText('Demo goal: show varied gaze directions', 36, 328);
  ctx.fillText('with short turns and wall-hit logging.', 36, 350);
}

function drawText(cmd) {
  ctx.fillStyle = '#e5e7eb';
  ctx.font = 'bold 34px Arial';
  ctx.fillText('Eye Maze+', 36, 58);
  ctx.font = '18px Arial';
  ctx.fillStyle = '#94a3b8';
  ctx.fillText('Look at screen edges to move. Spacebar click starts/restarts.', 36, 88);

  ctx.fillStyle = '#e5e7eb';
  ctx.font = 'bold 20px Arial';
  ctx.fillText(`Time: ${elapsed().toFixed(1)}s`, 36, 145);
  ctx.fillText(`Moves: ${moves}`, 36, 178);
  ctx.fillText(`Wall Hits: ${wallHits}`, 36, 211);
  ctx.fillText(`Command: ${cmd}`, 36, 244);

  ctx.fillStyle = '#a7f3d0';
  ctx.font = '16px Arial';
  ctx.fillText(routeHint, 36, 286);
  drawMiniRoute();

  if (!running && !finished) {
    ctx.fillStyle = '#38bdf8';
    ctx.font = 'bold 30px Arial';
    ctx.fillText('Press SPACE to start', 365, 560);
  }

  if (performance.now() < flashUntil) {
    ctx.fillStyle = flashMessage === 'WALL' ? '#fb7185' : '#a7f3d0';
    ctx.font = 'bold 42px Arial';
    ctx.fillText(flashMessage, 450, 52);
  }

  if (finished) {
    ctx.fillStyle = 'rgba(15,23,42,0.88)';
    ctx.fillRect(250, 165, 500, 255);
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 3;
    ctx.strokeRect(250, 165, 500, 255);
    ctx.fillStyle = '#a7f3d0';
    ctx.font = 'bold 44px Arial';
    ctx.fillText('CLEAR!', 410, 225);
    ctx.fillStyle = '#e5e7eb';
    ctx.font = '24px Arial';
    ctx.fillText(`Time: ${elapsed().toFixed(1)}s`, 380, 280);
    ctx.fillText(`Moves: ${moves}`, 380, 318);
    ctx.fillText(`Wall Hits: ${wallHits}`, 380, 356);
    ctx.fillStyle = '#94a3b8';
    ctx.font = '18px Arial';
    ctx.fillText('Press SPACE to restart', 400, 395);
  }
}

function draw() {
  const cmd = updateCommand();
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawZones(cmd);
  drawBoard();
  drawText(cmd);
  requestAnimationFrame(draw);
}

function startFromInput(e) {
  if (e) e.preventDefault?.();
  if (!running || finished) resetGame();
}

window.addEventListener('click', startFromInput);
window.addEventListener('keydown', (e) => {
  if (e.code === 'Space') startFromInput(e);
  if (!running || finished) return;
  const keyMap = { ArrowUp: 'UP', ArrowDown: 'DOWN', ArrowLeft: 'LEFT', ArrowRight: 'RIGHT' };
  if (keyMap[e.code]) { e.preventDefault(); executeCommand(keyMap[e.code]); }
});

draw();
