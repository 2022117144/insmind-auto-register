const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  getDataPath: () => ipcRenderer.invoke('get-data-path'),
  openDataPath: () => ipcRenderer.invoke('open-data-path'),
})