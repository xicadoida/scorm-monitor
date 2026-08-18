import { useState } from 'react'
import {
  pageWrapper,
  card,
  logo,
  input,
  buttonRow,
  buttonPrimary,
  buttonOutline,
  errorMessage
} from '../styles/theme'

function LoginPage({ API_URL, onLogin, onGoToRegister, event }) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")

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

    localStorage.setItem(
      "loggedStudent",
      JSON.stringify(data.student)
    )

    onLogin(data.student)
  }

  const theme = event ? {
    "--lms-login-primary": event.color_primary || "#152A47",
    "--lms-login-secondary": event.color_secondary || "#EF4923"
  } : {}

  return (
    <div style={{ ...pageWrapper, ...theme }}>
      <form onSubmit={handleLogin} style={{ ...card, background: "var(--lms-login-primary, #152A47)" }}>
        <img
          src={event?.logo_url || "/logo-iaclube.png"}
          alt={event ? event.name : "iaclube.help - IA para todos"}
          style={logo}
        />

        <input
          value={email}
          onChange={e => setEmail(e.target.value)}
          placeholder="Email"
          style={input}
        />

        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          placeholder="Senha"
          style={input}
        />

        {error && <p style={errorMessage}>{error}</p>}

        <div style={buttonRow}>
          <button
            type="button"
            onClick={onGoToRegister}
            style={buttonOutline}
          >
            Criar conta
          </button>

          <button type="submit" style={{ ...buttonPrimary, background: "var(--lms-login-secondary, #EF4923)" }}>
            Entrar
          </button>
        </div>
      </form>
    </div>
  )
}

export default LoginPage
