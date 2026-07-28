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
  successMessage
} from '../styles/theme'

function RegisterPage({ API_URL, onBackToLogin }) {
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    confirmPassword: ""
  })

  const [error, setError] = useState("")
  const [success, setSuccess] = useState("")

  async function handleRegister(e) {
    e.preventDefault()
    setError("")
    setSuccess("")

    if (form.password !== form.confirmPassword) {
      setError("As senhas não coincidem.")
      return
    }

    const response = await fetch(`${API_URL}/auth/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        name: form.name,
        email: form.email,
        password: form.password
      })
    })

    const data = await response.json()

    if (!data.success) {
      setError(data.message || "Erro ao cadastrar.")
      return
    }

    setSuccess("Conta criada com sucesso. Volte para o login.")
  }

  return (
    <div style={pageWrapper}>
      <form onSubmit={handleRegister} style={{ ...card, width: "380px" }}>
        <img
          src="/logo-iaclube.png"
          alt="iaclube.help - IA para todos"
          style={logo}
        />

        <input
          placeholder="Nome completo"
          value={form.name}
          onChange={e => setForm({ ...form, name: e.target.value })}
          style={input}
        />

        <input
          placeholder="Email"
          value={form.email}
          onChange={e => setForm({ ...form, email: e.target.value })}
          style={input}
        />

        <input
          type="password"
          placeholder="Senha"
          value={form.password}
          onChange={e => setForm({ ...form, password: e.target.value })}
          style={input}
        />

        <input
          type="password"
          placeholder="Confirmar senha"
          value={form.confirmPassword}
          onChange={e => setForm({ ...form, confirmPassword: e.target.value })}
          style={{ ...input, marginBottom: "20px" }}
        />

        {error && <p style={errorMessage}>{error}</p>}
        {success && <p style={successMessage}>{success}</p>}

        <div style={buttonRow}>
          <button type="button" onClick={onBackToLogin} style={buttonOutline}>
            Cancelar
          </button>

          <button type="submit" style={buttonPrimary}>
            Criar conta
          </button>
        </div>
      </form>
    </div>
  )
}

export default RegisterPage