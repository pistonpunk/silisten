const { app, BrowserWindow, ipcMain, screen, dialog, clipboard, shell } = require('electron');
const path = require('node:path');

const BASE = process.env.SILISTEN_URL || 'http://127.0.0.1:8756';
const TOKEN = process.env.SILISTEN_TOKEN || '';
const WIDTH = 728;

let win = null;
let desiredHeight = 220;
let lastReveal = null;

app.commandLine.appendSwitch('ozone-platform', 'x11');

const single = app.requestSingleInstanceLock();
if (!single) {
  app.quit();
}

app.on('second-instance', () => {
  if (win) {
    win.show();
    win.focus();
  }
});

function bounds(height) {
  const display = screen.getDisplayNearestPoint(screen.getCursorScreenPoint());
  const wa = display.workArea;
  return {
    x: Math.round(wa.x + (wa.width - WIDTH) / 2),
    y: Math.round(wa.y + wa.height - height - 24),
    width: WIDTH,
    height
  };
}

function createWindow() {
  win = new BrowserWindow({
    ...bounds(desiredHeight),
    show: false,
    frame: false,
    transparent: true,
    resizable: false,
    movable: false,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    hasShadow: false,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false
    }
  });
  win.setAlwaysOnTop(true, 'screen-saver');
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  win.loadFile(path.join(__dirname, 'index.html'));
  win.on('show', () => win && win.webContents.send('show'));
  win.on('closed', () => { win = null; });
}

async function poll() {
  if (!win) return;
  try {
    const res = await fetch(`${BASE}/state`, {
      headers: { 'X-Silisten-Token': TOKEN },
      signal: AbortSignal.timeout(1500)
    });
    const state = await res.json();
    if (lastReveal === null) {
      lastReveal = state.reveal;
    } else if (state.reveal !== lastReveal) {
      lastReveal = state.reveal;
      win.setBounds(bounds(desiredHeight));
      win.show();
      win.focus();
    }
    win.webContents.send('state', state);
  } catch {
    win.webContents.send('offline');
  }
}

ipcMain.on('layout', (_e, { height }) => {
  desiredHeight = Math.max(120, Math.min(760, Math.round(height)));
  if (win) win.setBounds(bounds(desiredHeight));
});

ipcMain.handle('api', async (_e, { path: route, body }) => {
  try {
    const res = await fetch(`${BASE}${route}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { 'X-Silisten-Token': TOKEN, 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(20000)
    });
    return await res.json();
  } catch (error) {
    return { error: String(error) };
  }
});

ipcMain.on('hide', () => { if (win) win.hide(); });
ipcMain.handle('copy', (_e, text) => { clipboard.writeText(String(text || '')); return true; });

ipcMain.handle('pick-file', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openFile'],
    filters: [{
      name: 'Audio or video',
      extensions: ['mp3', 'wav', 'm4a', 'flac', 'ogg', 'opus', 'aac', 'wma', 'mp4', 'mkv', 'webm', 'mov', 'avi', 'm4v', 'ts', '3gp']
    }]
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.on('open-external', (_e, url) => {
  if (/^https?:\/\//.test(String(url))) shell.openExternal(url);
});

app.whenReady().then(() => {
  createWindow();
  setInterval(poll, 120);
});

app.on('window-all-closed', () => app.quit());
