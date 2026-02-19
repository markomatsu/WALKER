const { contextBridge, ipcRenderer, webUtils } = require('electron');

contextBridge.exposeInMainWorld('walker', {
  runAnalysis: (payload) => ipcRenderer.invoke('run-analysis', payload),
  selectFiles: () => ipcRenderer.invoke('select-files'),
  readSource: (path) => ipcRenderer.invoke('read-source', { path }),
  exportReport: (payload) => ipcRenderer.invoke('export-report', payload),
  getDroppedFilePath: (file) => {
    try {
      if (webUtils && typeof webUtils.getPathForFile === 'function') {
        return webUtils.getPathForFile(file) || '';
      }
    } catch (_err) {
      // Fall back for older Electron versions.
    }

    if (file && typeof file.path === 'string') {
      return file.path;
    }

    return '';
  },
});
