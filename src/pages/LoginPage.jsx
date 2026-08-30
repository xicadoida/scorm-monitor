import { useState } from 'react'
import {
  pageWrapper,
  card,
  logo,
  input,
  buttonRow,
  buttonPrimary,
  buttonOutline,
  errorMessage,
  linkText,
  successMessage
} from '../styles/theme'

function LoginPage({ API_URL, onLogin, onGoToRegister, event, resetToken, onResetFinished }) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [showRecovery, setShowRecovery] = useState(false)
  const [newPassword, setNewPassword] = useState("")
  const [loading, setLoading] = useState(false)

  async function handleLogin(e) {
    e.preventDefault()
    setError("")

    const response = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ email, password, event_slug: event?.slug || null })
    })

    const data = await response.json()

    if (!data.success) {
      setError(data.message || "Não foi possível entrar.")
      return
    }

    if (!data.access_token) {
      setError("Não foi possível iniciar uma sessão segura. Tente novamente.")
      return
    }

    localStorage.setItem(
      "loggedStudent",
      JSON.stringify(data.student)
    )
    localStorage.setItem("accessToken", data.access_token)

    onLogin(data.student)
  }

  async function requestRecovery(e) {
    e.preventDefault()
    setError("")
    setNotice("")
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, event_slug: event?.slug || null })
      })
      const data = await response.json()
      setNotice(data.message || "Se o e-mail estiver cadastrado, enviaremos as instruções.")
    } catch {
      setError("Não foi possível solicitar a recuperação. Tente novamente.")
    } finally {
      setLoading(false)
    }
  }

  async function resetPassword(e) {
    e.preventDefault()
    setError("")
    setNotice("")
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: resetToken, new_password: newPassword })
      })
      const data = await response.json()
      if (!data.success) {
        setError(data.message || "Não foi possível redefinir a senha.")
        return
      }
      setNotice(data.message || "Senha redefinida.")
    } catch {
      setError("Não foi possível redefinir a senha.")
    } finally {
      setLoading(false)
    }
  }

  const theme = event ? {
    "--lms-login-primary": event.color_primary || "#152A47",
    "--lms-login-secondary": event.color_secondary || "#EF4923"
  } : {}

  return (
    <div style={{ ...pageWrapper, ...theme }}>
      <form onSubmit={resetToken ? resetPassword : (showRecovery ? requestRecovery : handleLogin)} style={{ ...card, background: "var(--lms-login-primary, #152A47)" }}>
        <img
          src={event?.logo_url || "/logo-iaclube.png"}
          alt={event ? event.name : "iaclube.help - IA para todos"}
          style={logo}
        />

        {resetToken ? (
          <>
            <p style={{ color: "white", textAlign: "center", margin: "0 0 18px" }}>Crie uma nova senha</p>
            <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} placeholder="Nova senha (mínimo 6 caracteres)" style={input} required />
          </>
        ) : (
          <>
            <input value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" type="email" style={input} required />
            {!showRecovery && <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Senha" style={input} required />}
          </>
        )}

        {error && <p style={errorMessage}>{error}</p>}
        {notice && <p style={successMessage}>{notice}</p>}

        {!resetToken && !showRecovery && (
          <button type="button" onClick={() => { setShowRecovery(true); setError(""); setNotice("") }} style={linkText}>
            Esqueci a senha
          </button>
        )}

        <div style={buttonRow}>
          {resetToken ? (
            <button type="button" onClick={onResetFinished} style={buttonOutline}>Voltar</button>
          ) : showRecovery ? (
            <button type="button" onClick={() => { setShowRecovery(false); setError(""); setNotice("") }} style={buttonOutline}>Voltar</button>
          ) : (
            <button type="button" onClick={onGoToRegister} style={buttonOutline}>Criar conta</button>
          )}
          <button type="submit" disabled={loading} style={{ ...buttonPrimary, background: "var(--lms-login-secondary, #EF4923)", opacity: loading ? 0.75 : 1 }}>
            {resetToken ? "Salvar senha" : showRecovery ? "Enviar link" : "Entrar"}
          </button>
        </div>
      </form>
    </div>
  )
}

export default LoginPage
