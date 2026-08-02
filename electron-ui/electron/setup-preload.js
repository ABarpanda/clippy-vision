const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('setup', {

    // ── Listeners (main → renderer) ──────────────────────────────────────

    // { key: 'python', state: 'pending'|'running'|'done'|'error', sub: '...' }
    onStepUpdate: (callback) => {
        ipcRenderer.on('step-update', (_event, data) => callback(data))
    },

    // { key: 'packages', percent: 0-100 }  or  percent: -1 for indeterminate
    onStepProgress: (callback) => {
        ipcRenderer.on('step-progress', (_event, data) => callback(data))
    },

    // { line: '...', level: 'info'|'ok'|'err'|'dim' }
    onLog: (callback) => {
        ipcRenderer.on('setup-log', (_event, data) => callback(data))
    },

    // { done: 3, text: '3 / 6 steps' }
    onOverall: (callback) => {
        ipcRenderer.on('setup-overall', (_event, data) => callback(data))
    },

    // called with no args when all steps finish
    onComplete: (callback) => {
        ipcRenderer.on('setup-complete', () => callback())
    },

    // ── Invocations (renderer → main) ────────────────────────────────────

    getHardwareCheck: () => ipcRenderer.invoke('get-hardware-check'),

    // After user accepts the hardware gate — starts install steps
    confirmHardwareAndStart: (opts) => ipcRenderer.invoke('confirm-hardware-and-start', opts || {}),

    // retry a step that errored: key = 'python' | 'ollama' | 'ollama-service' | 'packages' | 'models' | 'warmup'
    retryStep: (key) => ipcRenderer.invoke('retry-step', key),

    // user clicked Launch — close setup window, open main chat window
    launch: () => ipcRenderer.invoke('launch-app'),

})
