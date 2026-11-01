const { contextBridge, ipcRenderer, webUtils } = require('electron');

contextBridge.exposeInMainWorld('silisten', {
  onState: (cb) => ipcRenderer.on('state', (_e, state) => cb(state)),
  onShow: (cb) => ipcRenderer.on('show', () => cb()),
  onOffline: (cb) => ipcRenderer.on('offline', () => cb()),
  post: (route, body) => ipcRenderer.invoke('api', { path: route, body }),
  get: (route) => ipcRenderer.invoke('api', { path: route }),
  hide: () => ipcRenderer.send('hide'),
  copy: (text) => ipcRenderer.invoke('copy', text),
  pickFile: () => ipcRenderer.invoke('pick-file'),
  pathFor: (file) => webUtils.getPathForFile(file),
  layout: (height) => ipcRenderer.send('layout', { height }),
  open: (url) => ipcRenderer.send('open-external', url)
});
