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

function LoginPage({
  API_URL,
  onLogin,
  onGoToRegister,
  event,
  resetToken,
  verificationToken,
  onResetFinished,
  onVerificationFinished,
  initialNotice = ""
}) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [noticeOverride, setNoticeOverride] = useState(null)
  const [showRecovery, setShowRecovery] = useState(false)
  const [showVerificationResend, setShowVerificationResend] = useState(false)
  const [newPassword, setNewPassword] = useState("")
  const [verificationPassword, setVerificationPassword] = useState("")
  const [verificationNeedsPassword, setVerificationNeedsPassword] = useState(false)
  const [loading, setLoading] = useState(false)

  // A mensagem vinda da tela anterior não precisa de efeito: um override local
  // só vale enquanto se refere à mesma mensagem de origem. Assim, um retorno
  // posterior (cadastro ou confirmação) aparece sem disparar setState no efeito.
  const notice = noticeOverride?.source === initialNotice
    ? noticeOverride.value
    : initialNotice
  const setNotice = (value) => {
    setNoticeOverride({ source: initialNotice, value })
  }

  async function handleLogin(e) {
    e.preventDefault()
    setError("")

    try {
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
    } catch {
      setError("Não foi possível entrar. Tente novamente.")
    }
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
      if (!response.ok || !data.success) {
        setError(data.message || "Não foi possível solicitar a recuperação. Tente novamente.")
        return
      }
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

  async function requestVerification(e) {
    e.preventDefault()
    setError("")
    setNotice("")
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/auth/resend-email-verification`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, event_slug: event?.slug || null })
      })
      const data = await response.json()
      if (!response.ok || !data.success) {
        setError(data.message || "Não foi possível solicitar a confirmação. Tente novamente.")
        return
      }
      setNotice(data.message || "Se houver uma conta elegível, enviaremos as instruções.")
    } catch {
      setError("Não foi possível solicitar a confirmação. Tente novamente.")
    } finally {
      setLoading(false)
    }
  }

  async function verifyEmail(e) {
    e.preventDefault()
    setError("")
    setNotice("")
    setLoading(true)
    try {
      const payload = { token: verificationToken }
      if (verificationPassword) payload.new_password = verificationPassword

      const response = await fetch(`${API_URL}/auth/verify-email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })
      const data = await response.json()

      // Uma conta pendente não mantém a senha escolhida por quem iniciou o
      // cadastro: somente a pessoa que recebeu o link poderá defini-la.
      if (data.requires_new_password) {
        setVerificationNeedsPassword(true)
        setNotice(data.message || "Defina uma senha para concluir a confirmação.")
        return
      }

      if (!response.ok || !data.success) {
        setError(data.message || "Não foi possível confirmar este e-mail.")
        return
      }

      setVerificationPassword("")
      onVerificationFinished?.(data.message || "E-mail confirmado. Agora você já pode entrar.")
    } catch {
      setError("Não foi possível confirmar este e-mail.")
    } finally {
      setLoading(false)
    }
  }

  function closeSecondaryMode() {
    setShowRecovery(false)
    setShowVerificationResend(false)
    setError("")
    setNotice("")
  }

  const isVerifyingEmail = Boolean(verificationToken)
  const submitHandler = isVerifyingEmail
    ? verifyEmail
    : resetToken
      ? resetPassword
      : showRecovery
        ? requestRecovery
        : showVerificationResend
          ? requestVerification
          : handleLogin

  const theme = event ? {
    "--lms-login-primary": event.color_primary || "#152A47",
    "--lms-login-secondary": event.color_secondary || "#EF4923"
  } : {}

  return (
    <div style={{ ...pageWrapper, ...theme }}>
      <form onSubmit={submitHandler} style={{ ...card, background: "var(--lms-login-primary, #152A47)" }}>
        <img
          src={event?.logo_url || "/logo-iaclube.png"}
          alt={event ? event.name : "iaclube.help - IA para todos"}
          style={logo}
        />

        {isVerifyingEmail ? (
          <>
            <p style={{ color: "white", textAlign: "center", margin: "0 0 18px" }}>
              {verificationNeedsPassword
                ? "Defina uma senha para concluir a confirma\u00e7\u00e3o."
                : "Confirme seu e-mail para ativar o acesso."}
            </p>
            {verificationNeedsPassword && (
              <input
                type="password"
                value={verificationPassword}
                onChange={e => setVerificationPassword(e.target.value)}
                placeholder="Defina uma senha (mínimo 6 caracteres)"
                autoComplete="new-password"
                style={input}
                required
              />
            )}
          </>
        ) : resetToken ? (
          <>
            <p style={{ color: "white", textAlign: "center", margin: "0 0 18px" }}>Crie uma nova senha</p>
            <input
              type="password"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              placeholder="Nova senha (mínimo 6 caracteres)"
              autoComplete="new-password"
              style={input}
              required
            />
          </>
        ) : (
          <>
            <input value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" type="email" style={input} required />
            {!showRecovery && !showVerificationResend && (
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Senha"
                autoComplete="current-password"
                style={input}
                required
              />
            )}
          </>
        )}

        {error && <p style={errorMessage}>{error}</p>}
        {notice && <p style={successMessage}>{notice}</p>}

        {!isVerifyingEmail && !resetToken && !showRecovery && !showVerificationResend && <>
          <button type="button" onClick={() => { setShowRecovery(true); setError(""); setNotice("") }} style={linkText}>
            Esqueci a senha
          </button>
          <button type="button" onClick={() => { setShowVerificationResend(true); setError(""); setNotice("") }} style={{ ...linkText, textAlign: "center", marginTop: "-8px" }}>
            Reenviar confirmação de e-mail
          </button>
        </>}

        <div style={buttonRow}>
          {isVerifyingEmail ? (
            <button type="button" onClick={() => onVerificationFinished?.()} style={buttonOutline}>Voltar</button>
          ) : resetToken ? (
            <button type="button" onClick={onResetFinished} style={buttonOutline}>Voltar</button>
          ) : showRecovery || showVerificationResend ? (
            <button type="button" onClick={closeSecondaryMode} style={buttonOutline}>Voltar</button>
          ) : (
            <button type="button" onClick={onGoToRegister} style={buttonOutline}>Criar conta</button>
          )}
          <button type="submit" disabled={loading} style={{ ...buttonPrimary, background: "var(--lms-login-secondary, #EF4923)", opacity: loading ? 0.75 : 1 }}>
            {isVerifyingEmail
              ? verificationNeedsPassword ? "Definir senha e confirmar" : "Confirmar e-mail"
              : resetToken ? "Salvar senha" : showRecovery ? "Enviar link" : showVerificationResend ? "Reenviar link" : "Entrar"}
          </button>
        </div>
      </form>
    </div>
  )
}

export default LoginPage
