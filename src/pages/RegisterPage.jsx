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

function RegisterPage({ API_URL, onBackToLogin, event }) {
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    confirmPassword: "",
    personType: "",
    acceptedTerms: false
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

    if (!form.personType) {
      setError("Selecione se o cadastro é de pessoa física ou jurídica.")
      return
    }

    if (!form.acceptedTerms) {
      setError("É necessário aceitar os termos de uso para criar a conta.")
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
        password: form.password,
        person_type: form.personType,
        accepted_terms: form.acceptedTerms,
        event_slug: event?.slug || null
      })
    })

    const data = await response.json()

    if (!data.success) {
      setError(data.message || "Erro ao cadastrar.")
      return
    }

    onBackToLogin()
  }

  const theme = event ? {
    "--lms-login-primary": event.color_primary || "#152A47",
    "--lms-login-secondary": event.color_secondary || "#EF4923"
  } : {}

  return (
    <div style={{ ...pageWrapper, ...theme }}>
      <form onSubmit={handleRegister} style={{ ...card, width: "380px", background: "var(--lms-login-primary, #152A47)" }}>
        <img
          src={event?.logo_url || "/logo-iaclube.png"}
          alt={event ? event.name : "iaclube.help - IA para todos"}
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

        <select
          value={form.personType}
          onChange={e => setForm({ ...form, personType: e.target.value })}
          style={input}
        >
          <option value="">Tipo de pessoa</option>
          <option value="pf">Pessoa física</option>
          <option value="pj">Pessoa jurídica</option>
        </select>

        <label style={{ display: "flex", gap: "8px", alignItems: "flex-start", color: "#fff", fontSize: "13px", lineHeight: 1.35, margin: "0 0 20px" }}>
          <input
            type="checkbox"
            checked={form.acceptedTerms}
            onChange={e => setForm({ ...form, acceptedTerms: e.target.checked })}
            style={{ marginTop: "2px" }}
          />
          <span>Li e aceito os <a href="https://iaclube.com/sobre/temos-de-uso-lms" target="_blank" rel="noreferrer" style={{ color: "#fff", textDecoration: "underline" }}>termos de uso da plataforma</a>.</span>
        </label>

        {error && <p style={errorMessage}>{error}</p>}
        {success && <p style={successMessage}>{success}</p>}

        <div style={buttonRow}>
          <button type="button" onClick={onBackToLogin} style={buttonOutline}>
            Cancelar
          </button>

          <button type="submit" style={{ ...buttonPrimary, background: "var(--lms-login-secondary, #EF4923)" }}>
            Criar conta
          </button>
        </div>
      </form>
    </div>
  )
}

export default RegisterPage
