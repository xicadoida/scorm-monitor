import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'

// Todas as chamadas ao backend recebem a sessão atual automaticamente. Assim
// componentes não precisam duplicar o cabeçalho Authorization em cada fetch.
const nativeFetch = window.fetch.bind(window)
const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

window.fetch = (resource, options = {}) => {
  const url = typeof resource === 'string' ? resource : resource?.url
  const token = localStorage.getItem('accessToken')

  if (!token || !url?.startsWith(apiBaseUrl)) {
    return nativeFetch(resource, options)
  }

  const headers = new Headers(options.headers || (resource instanceof Request ? resource.headers : undefined))
  headers.set('Authorization', `Bearer ${token}`)
  return nativeFetch(resource, { ...options, headers })
}

ReactDOM.createRoot(document.getElementById('root')).render(
    <App />
)
