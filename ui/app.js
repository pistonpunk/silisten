const $ = (id) => document.getElementById(id);
const notch = $('notch');
const eq = $('equalizer');
const eqCtx = eq.getContext('2d');

const BARS = 5;
const history = new Float32Array(BARS * 2);

let state = null;
let settingsOpen = false;
let copiedTimer = null;
let resultSignature = '';

window.silisten.onState(render);

window.silisten.onShow(() => {
  notch.classList.remove('enter');
  void notch.offsetWidth;
  notch.classList.add('enter');
});

window.silisten.onOffline(() => {
  state = null;
  notch.dataset.state = 'error';
  $('title').textContent = 'Silisten';
  $('timer').textContent = '';
  $('errormsg').textContent = 'The Silisten backend is not running. Start it with: silisten start';
});

function render(s) {
  state = s;
  syncLanguage();
  document.documentElement.style.setProperty(
    '--level',
    (s.status === 'listening' ? Math.min(1, s.level || 0) : 0).toFixed(3)
  );

  if (settingsOpen) {
    renderHealth(s);
    return;
  }

  notch.dataset.state = s.status === 'idle' ? 'done' : s.status;

  $('title').textContent = {
    listening: 'Listening',
    thinking: s.phase === 'identifying speakers' ? 'Naming speakers' : s.phase === 'decoding' ? 'Reading the file' : 'Transcribing',
    done: 'Transcription',
    error: 'Something went wrong'
  }[s.status] || 'Silisten';

  $('timer').textContent = s.status === 'listening' ? formatTime(s.duration || 0) : '';

  if (s.status === 'listening') {
    const text = (s.partial || '').trim();
    const partial = $('partial');
    partial.textContent = text || 'Speak whenever you\'re ready';
    partial.classList.toggle('empty', !text);
  }

  if (s.status === 'thinking') {
    $('phase').textContent = s.phase === 'identifying speakers' ? 'Naming speakers'
      : s.phase === 'decoding' ? 'Reading the file' : 'Transcribing';
    const fill = $('fill');
    if (typeof s.progress === 'number') {
      fill.classList.remove('indeterminate');
      fill.style.width = Math.round(s.progress * 100) + '%';
    } else {
      fill.classList.add('indeterminate');
      fill.style.width = '24%';
    }
  }

  if (s.status === 'error') {
    $('errormsg').textContent = s.error || 'Transcription failed.';
  }

  if (s.status === 'done' || s.status === 'idle') {
    const signature = s.text + '|' + (s.segments || []).map((seg) => seg.speaker).join(',');
    if (signature !== resultSignature) {
      resultSignature = signature;
      renderTranscript(s);
    }
    $('stats').textContent = s.duration >= 0.5 ? formatTime(s.duration) : '';
    const copy = $('copy');
    copy.textContent = 'Copy all';
    copy.classList.remove('copied');
    copy.disabled = !s.text;
  }
}

function renderTranscript(s) {
  const el = $('transcript');
  el.replaceChildren();
  const segments = (s.segments || []).filter((seg) => seg.text && seg.text.trim());
  const speakers = new Set(segments.map((seg) => seg.speaker).filter(Boolean));

  if (!s.text) {
    const p = document.createElement('p');
    p.className = 'empty';
    p.textContent = 'Nothing heard.';
    el.append(p);
    return;
  }

  if (speakers.size <= 1) {
    const p = document.createElement('p');
    p.textContent = s.text;
    el.append(p);
    return;
  }

  for (const seg of segments) {
    const row = document.createElement('div');
    row.className = 'seg';
    if (seg.speaker) {
      const chip = document.createElement('span');
      chip.className = 'speaker';
      chip.textContent = 'Speaker ' + seg.speaker;
      row.append(chip);
    }
    const p = document.createElement('p');
    p.textContent = seg.text.trim();
    row.append(p);
    el.append(row);
  }
}

function renderHealth(s) {
  const model = s.engine.state === 'ready'
    ? `ready on ${escapeHtml(s.engine.device)}`
    : s.engine.state === 'loading'
      ? 'loading…'
      : `<span class="bad">failed — ${escapeHtml(s.engine.error || '')}</span>`;
  const speakers = s.diarizer.state === 'ready'
    ? 'ready'
    : s.diarizer.state === 'unavailable'
      ? '<span class="bad">needs a Hugging Face token</span>'
      : s.diarizer.state === 'idle'
        ? 'off'
        : `<span class="bad">${escapeHtml(s.diarizer.error || 'failed')}</span>`;
  $('health').innerHTML = [
    `<b>Model</b> ${model}`,
    `<b>Speakers</b> ${speakers}`,
    `<b>Shortcut</b> ${escapeHtml(s.shortcut)} (set it in GNOME Settings › Keyboard)`
  ].join('<br>');
}

function openSettings() {
  settingsOpen = true;
  $('pane-settings').hidden = false;
  notch.dataset.state = 'settings';
  $('title').textContent = 'Settings';
  $('timer').textContent = '';
  $('settings-note').textContent = '';
  if (state) {
    $('diarize').checked = Boolean(state.config.diarize);
    renderHealth(state);
  }
}

function closeSettings() {
  settingsOpen = false;
  $('pane-settings').hidden = true;
  $('settings-note').textContent = '';
  resultSignature = '';
  if (state) render(state);
}

function formatTime(seconds) {
  const total = Math.max(0, Math.round(seconds || 0));
  return Math.floor(total / 60) + ':' + String(total % 60).padStart(2, '0');
}

function escapeHtml(value) {
  const div = document.createElement('div');
  div.textContent = String(value == null ? '' : value);
  return div.innerHTML;
}

const LANGUAGES = [
  ['', 'Auto'],
  ['en', 'English'],
  ['de', 'German'],
  ['fr', 'French'],
  ['es', 'Spanish'],
  ['it', 'Italian'],
  ['pt', 'Portuguese'],
  ['nl', 'Dutch'],
  ['pl', 'Polish'],
  ['ru', 'Russian'],
  ['uk', 'Ukrainian'],
  ['tr', 'Turkish'],
  ['ar', 'Arabic'],
  ['hi', 'Hindi'],
  ['ja', 'Japanese'],
  ['ko', 'Korean'],
  ['zh', 'Chinese']
];

const quickLanguage = $('quick-language');
for (const [value, label] of LANGUAGES) {
  const option = document.createElement('option');
  option.value = value;
  option.textContent = label;
  quickLanguage.append(option);
}

quickLanguage.addEventListener('change', () => {
  window.silisten.post('/config', { language: quickLanguage.value });
  quickLanguage.blur();
});

function syncLanguage() {
  if (!state) return;
  const current = state.config.language || '';
  if (quickLanguage.value !== current) quickLanguage.value = current;
}

$('gear').addEventListener('click', () => (settingsOpen ? closeSettings() : openSettings()));
$('close').addEventListener('click', () => window.silisten.hide());
$('cancel').addEventListener('click', closeSettings);

$('save').addEventListener('click', async () => {
  const response = await window.silisten.post('/config', {
    diarize: $('diarize').checked
  });
  if (response && response.error) {
    $('settings-note').textContent = response.error;
    return;
  }
  closeSettings();
});

$('copy').addEventListener('click', async () => {
  if (!state || !state.text) return;
  await window.silisten.copy(state.text);
  const button = $('copy');
  button.textContent = 'Copied';
  button.classList.add('copied');
  clearTimeout(copiedTimer);
  copiedTimer = setTimeout(() => {
    button.textContent = 'Copy all';
    button.classList.remove('copied');
    window.silisten.hide();
  }, 800);
});

$('more').addEventListener('click', () => {
  window.silisten.post('/record/start', { append: true });
});

$('file').addEventListener('click', async () => {
  const file = await window.silisten.pickFile();
  if (!file) return;
  window.silisten.post('/upload', { path: file, append: Boolean(state && state.text) });
});

window.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  if (settingsOpen) closeSettings();
  else window.silisten.hide();
});

window.addEventListener('dragover', (event) => {
  event.preventDefault();
  document.body.classList.add('dragging');
});

window.addEventListener('dragleave', (event) => {
  if (!event.relatedTarget) document.body.classList.remove('dragging');
});

window.addEventListener('drop', (event) => {
  event.preventDefault();
  document.body.classList.remove('dragging');
  const file = event.dataTransfer.files && event.dataTransfer.files[0];
  if (!file) return;
  const path = window.silisten.pathFor(file);
  if (path) window.silisten.post('/upload', { path, append: Boolean(state && state.text) });
});

let reportedHeight = 0;
new ResizeObserver(() => {
  const height = Math.ceil(notch.getBoundingClientRect().height) + 30;
  if (Math.abs(height - reportedHeight) < 2) return;
  reportedHeight = height;
  window.silisten.layout(height);
}).observe(notch);

const EQ_CSS_WIDTH = 64;
const EQ_CSS_HEIGHT = 26;
eq.width = Math.round(EQ_CSS_WIDTH * (window.devicePixelRatio || 1));
eq.height = Math.round(EQ_CSS_HEIGHT * (window.devicePixelRatio || 1));

function drawEqualizer() {
  const listening = state && state.status === 'listening';
  const dpr = window.devicePixelRatio || 1;

  for (let i = 0; i < history.length - 1; i++) history[i] = history[i + 1];
  const live = listening ? Math.min(1, (state.level || 0) * 1.8) : 0;
  history[history.length - 1] = Math.min(1, live * (0.55 + Math.random() * 0.85));

  eqCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
  eqCtx.clearRect(0, 0, EQ_CSS_WIDTH, EQ_CSS_HEIGHT);
  eqCtx.fillStyle = '#f5f5f7';

  const gap = 4;
  const barWidth = 3;
  const middle = EQ_CSS_HEIGHT / 2;
  const baseline = listening ? 4 : 3;

  for (let i = 0; i < BARS; i++) {
    const value = listening
      ? Math.max(0.15, history[history.length - 1 - (BARS - 1 - i) * 2])
      : 0.12;
    const barHeight = Math.max(3, value * EQ_CSS_HEIGHT);
    const x = i * (barWidth + gap);
    eqCtx.beginPath();
    eqCtx.roundRect(x, middle - barHeight / 2, barWidth, barHeight, barWidth / 2);
    eqCtx.fill();
  }
  requestAnimationFrame(drawEqualizer);
}

requestAnimationFrame(drawEqualizer);
