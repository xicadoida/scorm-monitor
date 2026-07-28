import { useState } from 'react'
import {
  pageWrapper,
  card,
  logo,
  input,
  linkText,
  buttonRow,
  buttonPrimary,
  buttonOutline,
  errorMessage
} from '../styles/theme'

function LoginPage({ API_URL, onLogin, onGoToRegister }) {
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
      body: JSON.stringify({ email, password })
    })

    const data = await response.json()

    if (!data.success) {
      setError("Aluno não encontrado.")
      return
    }

    localStorage.setItem(
      "loggedStudent",
      JSON.stringify(data.student)
    )

    onLogin(data.student)
  }

  return (
    <div style={pageWrapper}>
      <form onSubmit={handleLogin} style={card}>
        <img
          src="/logo-iaclube.png"
          alt="iaclube.help - IA para todos"
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

        <button type="button" style={linkText}>
          Esqueci a senha
        </button>

        {error && <p style={errorMessage}>{error}</p>}

        <div style={buttonRow}>
          <button
            type="button"
            onClick={onGoToRegister}
            style={buttonOutline}
          >
            Criar conta
          </button>

          <button type="submit" style={buttonPrimary}>
            Entrar
          </button>
        </div>
      </form>
    </div>
  )
}

export default LoginPage