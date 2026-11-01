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
  ['af', "Afrikaans"],
  ['sq', "Albanian"],
  ['am', "Amharic"],
  ['ar', "Arabic"],
  ['hy', "Armenian"],
  ['as', "Assamese"],
  ['az', "Azerbaijani"],
  ['ba', "Bashkir"],
  ['eu', "Basque"],
  ['be', "Belarusian"],
  ['bn', "Bengali"],
  ['bs', "Bosnian"],
  ['br', "Breton"],
  ['bg', "Bulgarian"],
  ['yue', "Cantonese"],
  ['ca', "Catalan"],
  ['zh', "Chinese"],
  ['hr', "Croatian"],
  ['cs', "Czech"],
  ['da', "Danish"],
  ['nl', "Dutch"],
  ['en', "English"],
  ['et', "Estonian"],
  ['fo', "Faroese"],
  ['fi', "Finnish"],
  ['fr', "French"],
  ['gl', "Galician"],
  ['ka', "Georgian"],
  ['de', "German"],
  ['el', "Greek"],
  ['gu', "Gujarati"],
  ['ht', "Haitian Creole"],
  ['ha', "Hausa"],
  ['haw', "Hawaiian"],
  ['he', "Hebrew"],
  ['hi', "Hindi"],
  ['hu', "Hungarian"],
  ['is', "Icelandic"],
  ['id', "Indonesian"],
  ['it', "Italian"],
  ['ja', "Japanese"],
  ['jw', "Javanese"],
  ['kn', "Kannada"],
  ['kk', "Kazakh"],
  ['km', "Khmer"],
  ['ko', "Korean"],
  ['lo', "Lao"],
  ['la', "Latin"],
  ['lv', "Latvian"],
  ['ln', "Lingala"],
  ['lt', "Lithuanian"],
  ['lb', "Luxembourgish"],
  ['mk', "Macedonian"],
  ['mg', "Malagasy"],
  ['ms', "Malay"],
  ['ml', "Malayalam"],
  ['mt', "Maltese"],
  ['mi', "Maori"],
  ['mr', "Marathi"],
  ['mn', "Mongolian"],
  ['my', "Myanmar"],
  ['ne', "Nepali"],
  ['no', "Norwegian"],
  ['nn', "Nynorsk"],
  ['oc', "Occitan"],
  ['ps', "Pashto"],
  ['fa', "Persian"],
  ['pl', "Polish"],
  ['pt', "Portuguese"],
  ['pa', "Punjabi"],
  ['ro', "Romanian"],
  ['ru', "Russian"],
  ['sa', "Sanskrit"],
  ['sr', "Serbian"],
  ['sn', "Shona"],
  ['sd', "Sindhi"],
  ['si', "Sinhala"],
  ['sk', "Slovak"],
  ['sl', "Slovenian"],
  ['so', "Somali"],
  ['es', "Spanish"],
  ['su', "Sundanese"],
  ['sw', "Swahili"],
  ['sv', "Swedish"],
  ['tl', "Tagalog"],
  ['tg', "Tajik"],
  ['ta', "Tamil"],
  ['tt', "Tatar"],
  ['te', "Telugu"],
  ['th', "Thai"],
  ['bo', "Tibetan"],
  ['tr', "Turkish"],
  ['tk', "Turkmen"],
  ['uk', "Ukrainian"],
  ['ur', "Urdu"],
  ['uz', "Uzbek"],
  ['vi', "Vietnamese"],
  ['cy', "Welsh"],
  ['yi', "Yiddish"],
  ['yo', "Yoruba"],
];

const menus = {
  'language-menu': $('language-menu'),
  'input-menu': $('input-menu')
};
let openMenuId = null;

function buildLanguageMenu() {
  menus['language-menu'].replaceChildren();
  for (const [value, label] of LANGUAGES) {
    const item = document.createElement('li');
    item.dataset.value = value;
    item.textContent = label;
    item.setAttribute('role', 'option');
    item.addEventListener('click', () => {
      window.silisten.post('/config', { language: value });
      closeMenu();
    });
    menus['language-menu'].append(item);
  }
}

const inputLabels = { default: 'Default mic' };

async function refreshInputLabel(id, label) {
  const list = await window.silisten.get('/sources');
  for (const source of Array.isArray(list) ? list : []) inputLabels[source.id] = source.label;
  if (inputLabels[id]) label.textContent = inputLabels[id];
}

async function buildInputMenu() {
  const list = await window.silisten.get('/sources');
  const menu = menus['input-menu'];
  menu.replaceChildren();
  const current = state ? state.config.input_device || 'default' : 'default';
  const options = [{ id: 'default', label: 'Default mic' }, ...(Array.isArray(list) ? list : [])];
  for (const option of options) inputLabels[option.id] = option.label;
  for (const source of options) {
    const item = document.createElement('li');
    item.dataset.value = source.id;
    item.textContent = source.label;
    item.setAttribute('role', 'option');
    item.classList.toggle('selected', source.id === current);
    item.addEventListener('click', () => {
      window.silisten.post('/config', { input_device: source.id });
      closeMenu();
    });
    menu.append(item);
  }
}

function closeMenu() {
  for (const menu of Object.values(menus)) {
    menu.hidden = true;
  }
  document.querySelectorAll('.lang-button').forEach((b) => b.setAttribute('aria-expanded', 'false'));
  openMenuId = null;
}

async function toggleMenu(button) {
  const id = button.dataset.menu;
  if (openMenuId === id) {
    closeMenu();
    return;
  }
  closeMenu();
  if (id === 'input-menu') await buildInputMenu();
  const menu = menus[id];
  button.parentElement.prepend(menu);
  menu.hidden = false;
  button.setAttribute('aria-expanded', 'true');
  openMenuId = id;
  const selected = menu.querySelector('.selected');
  if (selected) selected.scrollIntoView({ block: 'center' });
}

function closeMenu() {
  for (const menu of Object.values(menus)) {
    menu.hidden = true;
  }
  document.querySelectorAll('.lang-button').forEach((b) => b.setAttribute('aria-expanded', 'false'));
  openMenuId = null;
}

async function toggleMenu(button) {
  const id = button.dataset.menu;
  if (openMenuId === id) {
    closeMenu();
    return;
  }
  closeMenu();
  if (id === 'input-menu') await buildInputMenu();
  const menu = menus[id];
  button.parentElement.prepend(menu);
  menu.hidden = false;
  button.setAttribute('aria-expanded', 'true');
  openMenuId = id;
  const selected = menu.querySelector('.selected');
  if (selected) selected.scrollIntoView({ block: 'center' });
}

for (const button of document.querySelectorAll('.lang-button')) {
  button.addEventListener('click', (event) => {
    event.stopPropagation();
    toggleMenu(button);
  });
}

document.addEventListener('click', (event) => {
  if (!openMenuId) return;
  if (!event.target.closest('.lang-button') && !event.target.closest('.language-menu')) closeMenu();
});

function syncLanguage() {
  if (!state) return;
  const inputs = document.querySelectorAll('.lang-button');
  for (const button of inputs) {
    if (button.dataset.menu !== 'input-menu') continue;
    const current = state.config.input_device || 'default';
    const label = button.querySelector('span');
    if (inputLabels[current]) {
      label.textContent = inputLabels[current];
    } else if (current === 'default') {
      label.textContent = 'Default mic';
    } else {
      label.textContent = 'Microphone';
      refreshInputLabel(current, label);
    }
  }
  const current = state.config.language || '';
  const entry = LANGUAGES.find(([value]) => value === current);
  const text = entry ? entry[1] : current.toUpperCase();
  document.querySelectorAll('.lang-button[data-menu="language-menu"] span').forEach((span) => (span.textContent = text));
  for (const item of menus['language-menu'].children) {
    item.classList.toggle('selected', item.dataset.value === current);
  }
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

$('stop').addEventListener('click', () => {
  window.silisten.post('/record/stop', {});
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
  if (openMenuId) {
    closeMenu();
    return;
  }
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
const MENU_HEADROOM = 300;


new ResizeObserver(() => {
  const height = Math.ceil(notch.getBoundingClientRect().height) + MENU_HEADROOM;
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
  buildLanguageMenu();
requestAnimationFrame(drawEqualizer);
}

buildLanguageMenu();
requestAnimationFrame(drawEqualizer);
