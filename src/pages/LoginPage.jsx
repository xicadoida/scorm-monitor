import { useState } from 'react'

function LoginPage({ API_URL, onLogin }) {
  const [email, setEmail] = useState("")
  const [error, setError] = useState("")

  async function handleLogin(e) {
    e.preventDefault()
    setError("")

    const response = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ email })
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
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "#f4f6fb",
      fontFamily: "Arial"
    }}>
      <form
        onSubmit={handleLogin}
        style={{
          background: "white",
          padding: "32px",
          borderRadius: "16px",
          width: "360px",
          boxShadow: "0 4px 16px rgba(0,0,0,0.08)"
        }}
      >
        <h1>Entrar</h1>

        <p style={{ color: "#555" }}>
          Acesse seus cursos usando seu email cadastrado.
        </p>

        <label>Email:</label>

        <input
          value={email}
          onChange={e => setEmail(e.target.value)}
          placeholder="seu@email.com"
          style={{
            width: "100%",
            padding: "10px",
            marginTop: "8px",
            marginBottom: "16px"
          }}
        />

        {error && (
          <p style={{ color: "red" }}>
            {error}
          </p>
        )}

        <button
          type="submit"
          style={{
            width: "100%",
            padding: "12px",
            border: "none",
            borderRadius: "10px",
            background: "#2563eb",
            color: "white",
            fontWeight: "bold",
            cursor: "pointer"
          }}
        >
          Entrar
        </button>
      </form>
    </div>
  )
}

export default LoginPage