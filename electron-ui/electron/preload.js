const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('clippy', {

    chat: async (message, conversationId) => {
        const response = await fetch('http://localhost:8000/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message,
                conversation_id: conversationId,
            })
        })
        
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
    },

    chatStream: async (message, conversationId, onEvent) => {
        const response = await fetch('http://localhost:8000/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message,
                conversation_id: conversationId,
            }),
        })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        if (!response.body) throw new Error('No response body')

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
            const { done, value } = await reader.read()
            if (done) break
            buffer += decoder.decode(value, { stream: true })
            const parts = buffer.split('\n\n')
            buffer = parts.pop() || ''
            for (const part of parts) {
                const line = part.split('\n').find(l => l.startsWith('data: '))
                if (!line) continue
                try {
                    const event = JSON.parse(line.slice(6))
                    onEvent(event)
                } catch (_) { /* ignore malformed chunk */ }
            }
        }
    },

    getName: async () => {
        const response = await fetch('http://localhost:8000/user/name')
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
    },

    setName: async (name) => {
        const response = await fetch('http://localhost:8000/user/name', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
        })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
    },

    getProfile: async () => {
        const response = await fetch('http://localhost:8000/user/profile')
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
    },

    updateProfile: async (payload) => {
        const response = await fetch('http://localhost:8000/user/profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
    },

    getPrivacySettings: async () => {
        const response = await fetch('http://localhost:8000/settings/privacy')
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
    },

    updatePrivacySettings: async (enabled) => {
        const response = await fetch('http://localhost:8000/settings/privacy', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled }),
        })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
    },

    listConversations: async () => {
        const response = await fetch('http://localhost:8000/conversations')
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
    },

    searchConversations: async (query, limit = 20) => {
        const params = new URLSearchParams({ q: query || '', limit: String(limit) })
        const response = await fetch(`http://localhost:8000/conversations/search?${params}`)
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
    },

    getConversation: async (conversationId) => {
        const response = await fetch(
            `http://localhost:8000/conversations/${encodeURIComponent(conversationId)}`
        )
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
    },

    checkHealth: async () => {
        const response = await fetch('http://localhost:8000/health')
        return response.ok
    },

    toggleCapture: () => ipcRenderer.invoke('toggle-capture'),

    getCaptureStatus: () => ipcRenderer.invoke('get-capture-status'),

    onCaptureStatusChanged: (callback) => {
        ipcRenderer.on('capture-status-changed', (_event, active) => callback(active))
    },

    onApiReady: (callback) => {
        ipcRenderer.on('api-ready', () => callback())
    },

    onLoadingStatus: (callback) => {
        ipcRenderer.on('loading-status', (_event, data) => callback(data))
    },

})
