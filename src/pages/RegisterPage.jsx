import { useState } from 'react'

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
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "#f4f6fb",
      fontFamily: "Arial"
    }}>
      <form
        onSubmit={handleRegister}
        style={{
          background: "white",
          padding: "32px",
          borderRadius: "16px",
          width: "380px",
          boxShadow: "0 4px 16px rgba(0,0,0,0.08)"
        }}
      >
        <h1>Criar conta</h1>

        <input
          placeholder="Nome"
          value={form.name}
          onChange={e => setForm({ ...form, name: e.target.value })}
          style={inputStyle}
        />

        <input
          placeholder="Email"
          value={form.email}
          onChange={e => setForm({ ...form, email: e.target.value })}
          style={inputStyle}
        />

        <input
          type="password"
          placeholder="Senha"
          value={form.password}
          onChange={e => setForm({ ...form, password: e.target.value })}
          style={inputStyle}
        />

        <input
          type="password"
          placeholder="Confirmar senha"
          value={form.confirmPassword}
          onChange={e => setForm({ ...form, confirmPassword: e.target.value })}
          style={inputStyle}
        />

        {error && <p style={{ color: "red" }}>{error}</p>}
        {success && <p style={{ color: "green" }}>{success}</p>}

        <button type="submit" style={buttonStyle}>
          Criar conta
        </button>

        <button
          type="button"
          onClick={onBackToLogin}
          style={{
            ...buttonStyle,
            background: "#6b7280",
            marginTop: "10px"
          }}
        >
          Voltar para login
        </button>
      </form>
    </div>
  )
}

const inputStyle = {
  width: "100%",
  padding: "10px",
  marginBottom: "12px"
}

const buttonStyle = {
  width: "100%",
  padding: "12px",
  border: "none",
  borderRadius: "10px",
  background: "#2563eb",
  color: "white",
  fontWeight: "bold",
  cursor: "pointer"
}

export default RegisterPage