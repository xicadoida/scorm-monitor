import { useState } from 'react'

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
        <h1
          style={{
            fontSize: "32px",
            marginBottom: "8px",
            color: "#111827"
          }}
        >
          Entrar
        </h1>

        <p
          style={{
            color: "#6b7280",
            marginBottom: "24px",
            lineHeight: 1.5
          }}
        >
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
        <label>Senha:</label>

        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          placeholder="Sua senha"
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
        <button
          type="button"
          onClick={onGoToRegister}
          style={{
            width: "100%",
            padding: "12px",
            border: "none",
            borderRadius: "10px",
            background: "#6b7280",
            color: "white",
            fontWeight: "bold",
            cursor: "pointer",
            marginTop: "10px"
          }}
        >
          Criar conta
        </button>
      </form>
    </div>
  )
}

export default LoginPage