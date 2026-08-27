import { useEffect, useMemo, useState } from 'react'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import {
  pageBackground,
  sectionTitle,
  searchInput,
  courseGrid,
  courseCard,
  courseCardHeader,
  courseCardTitle,
  courseCardSubtitle,
  coursePillButton,
  buttonOutline,
  progressWrapper,
  progressPercentLabel,
  progressTrack,
  progressFill,
  emptyStateText,
  paginationWrapper,
  paginationButton,
  paginationButtonActive,
  paginationArrow,
  accountCard,
  input,
  errorMessage,
  successMessage
} from '../styles/theme'

const COURSES_PER_PAGE = 6

// Ainda não existe carga horária nem % de progresso real vindos do backend.
// Por enquanto aproximamos os dois a partir do que já temos (status e tempo de sessão),
// só pra ter algo visual coerente. Quando o backend tiver esses dados de verdade,
// é só trocar essas duas funções.
function estimateProgress(progress) {
  if (!progress) return 0
  if (progress.completed) return 100
  if (progress.sessions_count > 0) return 50
  return 0
}

function formatHours(totalSessionTime) {
  if (!totalSessionTime) return "0h"

  const [hh] = totalSessionTime.split(":")
  const hours = parseInt(hh, 10)

  return Number.isNaN(hours) ? "0h" : `${hours}h`
}

function Dashboard({
  selectedStudent,
  courses,
  onOpenCourse,
  onOpenReport,
  onLogout,
  onOpenAdmin,
  isAdmin,
  API_URL,
  event,
  reloadCourses
}) {
  const [activeTab, setActiveTab] = useState("todos-cursos")
  const [progressData, setProgressData] = useState({})
  const [attendance, setAttendance] = useState(null)
  const [attendanceError, setAttendanceError] = useState("")
  const [search, setSearch] = useState("")

  const [publicCourses, setPublicCourses] = useState([])
  const [publicSearch, setPublicSearch] = useState("")
  const [publicPage, setPublicPage] = useState(1)
  const [enrollingCode, setEnrollingCode] = useState(null)

  const [passwordForm, setPasswordForm] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: ""
  })
  const [passwordError, setPasswordError] = useState("")
  const [passwordSuccess, setPasswordSuccess] = useState("")

  const [deletePassword, setDeletePassword] = useState("")
  const [deleteError, setDeleteError] = useState("")
  const [deleting, setDeleting] = useState(false)

  // Cada evento pode trocar "Curso" por outra palavra (ex: "Módulo").
  // Tudo abaixo deriva dessa única palavra, pra manter a gramática consistente
  // nos vários lugares que mencionam "curso" na tela.
  const itemSingular = event?.item_name || "Curso"
  const itemPlural = `${itemSingular}s`
  const itemSingularLower =
    itemSingular.charAt(0).toLowerCase() + itemSingular.slice(1)
  const itemPluralLower =
    itemPlural.charAt(0).toLowerCase() + itemPlural.slice(1)
  const showProgress = event?.show_progress !== false

  const tabLabels = {
    "meus-cursos": `Meus ${itemPlural}`,
    "todos-cursos": `Todos os ${itemPlural}`
  }

  useEffect(() => {
    async function loadProgress() {
      if (!selectedStudent) return

      const results = {}

      for (const course of courses) {
        const response = await fetch(
          `${API_URL}/progress/${selectedStudent.student_code}/${course.course_code}`
        )

        const data = await response.json()
        results[course.course_code] = data
      }

      setProgressData(results)
    }

    loadProgress()
  }, [courses, selectedStudent, API_URL])

  useEffect(() => {
    async function loadAttendance() {
      // A carteira de frequência é exclusiva dos ambientes de evento.
      // Contas da plataforma padrão não devem vê-la nem consultar seus dados.
      if (!selectedStudent || !event?.id) {
        setAttendance(null)
        setAttendanceError("")
        return
      }

      setAttendanceError("")
      try {
        const response = await fetch(
          `${API_URL}/attendance/students/${selectedStudent.student_code}`
        )
        const data = await response.json()

        if (!response.ok || !data.success) {
          throw new Error(data.message || "Não foi possível carregar a frequência.")
        }

        setAttendance(data)
      } catch (error) {
        setAttendanceError(error.message)
      }
    }

    loadAttendance()
  }, [selectedStudent, event?.id, API_URL])

  useEffect(() => {
    async function loadPublicCourses() {
      if (!selectedStudent || activeTab !== "todos-cursos") return

      const response = await fetch(
        `${API_URL}/courses/public?email=${encodeURIComponent(selectedStudent.email)}`
      )

      const data = await response.json()
      setPublicCourses(data.courses || [])
    }

    loadPublicCourses()
  }, [activeTab, selectedStudent, API_URL])

  useEffect(() => {
    setPublicPage(1)
  }, [publicSearch, activeTab])

  const enrolledCodes = useMemo(
    () => new Set(courses.map(c => c.course_code)),
    [courses]
  )

  // "Meus cursos" agora mostra tudo, dividido em duas seções:
  // o que ainda está em andamento e o que já foi concluído.
  const filteredCourses = useMemo(() => {
    return courses.filter(course =>
      course.title.toLowerCase().includes(search.toLowerCase())
    )
  }, [courses, search])

  const inProgressCourses = useMemo(
    () => filteredCourses.filter(
      course => !progressData[course.course_code]?.completed
    ),
    [filteredCourses, progressData]
  )

  const completedCourses = useMemo(
    () => filteredCourses.filter(
      course => progressData[course.course_code]?.completed
    ),
    [filteredCourses, progressData]
  )

  // "Todos cursos" agora mostra tudo, mas os já inscritos perdem prioridade
  // na ordenação: primeiro o que ainda não tem acesso, depois o que já está
  // em andamento, e por último o que já foi concluído.
  function getPublicPriority(course) {
    const progress = progressData[course.course_code]

    if (progress?.completed) return 2
    if (enrolledCodes.has(course.course_code)) return 1
    return 0
  }

  const availablePublicCourses = useMemo(() => {
    return publicCourses
      .filter(course =>
        course.title.toLowerCase().includes(publicSearch.toLowerCase())
      )
      .sort((a, b) => getPublicPriority(a) - getPublicPriority(b))
  }, [publicCourses, publicSearch, enrolledCodes, progressData])

  const publicTotalPages = Math.max(
    1,
    Math.ceil(availablePublicCourses.length / COURSES_PER_PAGE)
  )

  const pagePublicCourses = availablePublicCourses.slice(
    (publicPage - 1) * COURSES_PER_PAGE,
    publicPage * COURSES_PER_PAGE
  )

  async function handleEnroll(course) {
    setEnrollingCode(course.course_code)

    const response = await fetch(
      `${API_URL}/students/${selectedStudent.student_code}/enroll/${course.course_code}`,
      { method: "POST" }
    )

    const data = await response.json()

    setEnrollingCode(null)

    if (!data.success) {
      alert(data.message || "Não foi possível se inscrever nesse curso.")
      return
    }

    await reloadCourses()
  }

  async function handleChangePassword(e) {
    e.preventDefault()
    setPasswordError("")
    setPasswordSuccess("")

    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      setPasswordError("A confirmação não bate com a nova senha.")
      return
    }

    if (passwordForm.newPassword.length < 6) {
      setPasswordError("A nova senha precisa ter pelo menos 6 caracteres.")
      return
    }

    const response = await fetch(`${API_URL}/auth/change-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        student_code: selectedStudent.student_code,
        current_password: passwordForm.currentPassword,
        new_password: passwordForm.newPassword
      })
    })

    const data = await response.json()

    if (!data.success) {
      setPasswordError(data.message || "Não foi possível trocar a senha.")
      return
    }

    setPasswordSuccess("Senha alterada com sucesso.")
    setPasswordForm({
      currentPassword: "",
      newPassword: "",
      confirmPassword: ""
    })
  }

  async function handleDeleteAccount(e) {
    e.preventDefault()
    setDeleteError("")

    if (!deletePassword) {
      setDeleteError("Digite sua senha pra confirmar.")
      return
    }

    const confirmed = window.confirm(
      "Tem certeza que quer excluir sua conta? Isso remove seu acesso a todos os cursos e não pode ser desfeito."
    )

    if (!confirmed) return

    setDeleting(true)

    const response = await fetch(
      `${API_URL}/students/${selectedStudent.student_code}/delete-account`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: deletePassword })
      }
    )

    const data = await response.json()

    setDeleting(false)

    if (!data.success) {
      setDeleteError(data.message || "Não foi possível excluir a conta.")
      return
    }

    localStorage.removeItem("loggedStudent")
    onLogout()
  }

  function renderCourseCard(course, { context = "meus" } = {}) {
    const progress = progressData[course.course_code]
    const percent = estimateProgress(progress)
    const isMeus = context === "meus"

    const isEnrolled = enrolledCodes.has(course.course_code)
    const isCompleted = Boolean(progress?.completed)
    const status = isCompleted
      ? "Concluído"
      : progress?.sessions_count > 0
        ? "Em andamento"
        : "Não iniciado"

    let buttonLabel = "Inscrever"
    let buttonAction = () => handleEnroll(course)
    let buttonDisabled = enrollingCode === course.course_code
    let buttonStyle = coursePillButton

    if (!isMeus) {
      if (isEnrolled) {
        buttonLabel = "Acessar"
        buttonAction = () => onOpenCourse(course)
        buttonDisabled = false
      } else if (enrollingCode === course.course_code) {
        buttonLabel = "Inscrevendo..."
      }
    }

    return (
      <div key={course.course_code} style={courseCard}>
        <div style={courseCardHeader}>
          <span style={{ ...courseCardSubtitle, color: "#FFFFFF", fontWeight: "bold" }}>{status}</span>

          {isMeus ? (
            <button
              type="button"
              onClick={() => onOpenCourse(course)}
              style={coursePillButton}
            >
              Acessar
            </button>
          ) : !isMeus ? (
            <button
              type="button"
              onClick={buttonAction}
              disabled={buttonDisabled}
              style={buttonStyle}
            >
              {buttonLabel}
            </button>
          ) : null}
        </div>

        <p style={courseCardTitle}>{course.title}</p>

        {isMeus && showProgress && (
          <p style={courseCardSubtitle}>{formatHours(progress?.total_session_time)}</p>
        )}

        {isMeus && showProgress && (
          <div style={progressWrapper}>
            <p style={progressPercentLabel}>{percent}%</p>
            <div style={progressTrack}>
              <div style={progressFill(percent)} />
            </div>
          </div>
        )}
      </div>
    )
  }

  function renderPagination(currentPage, total, onChange) {
    if (total <= 1) return null

    return (
      <div style={paginationWrapper}>
        <button
          type="button"
          style={paginationArrow}
          onClick={() => onChange(Math.max(1, currentPage - 1))}
          disabled={currentPage === 1}
        >
          ‹
        </button>

        {Array.from({ length: total }, (_, i) => i + 1).map(n => (
          <button
            key={n}
            type="button"
            style={n === currentPage ? paginationButtonActive : paginationButton}
            onClick={() => onChange(n)}
          >
            {n}
          </button>
        ))}

        <button
          type="button"
          style={paginationArrow}
          onClick={() => onChange(Math.min(total, currentPage + 1))}
          disabled={currentPage === total}
        >
          ›
        </button>
      </div>
    )
  }

  function renderMeusCursos() {
    return (
      <>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "12px",
            marginBottom: "16px"
          }}
        >
          <p style={sectionTitle}>Meus {itemPluralLower}</p>

          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder={`Pesquise o ${itemSingularLower}`}
            style={searchInput}
          />
        </div>

        <p style={{ ...sectionTitle, fontSize: "15px" }}>
          {itemPlural} em andamento
        </p>

        <div style={courseGrid}>
          {inProgressCourses.map(c => renderCourseCard(c))}

          {inProgressCourses.length === 0 && (
            <p style={emptyStateText}>
              Nenhum {itemSingularLower} em andamento no momento.
            </p>
          )}
        </div>

        <p style={{ ...sectionTitle, fontSize: "15px" }}>
          {itemPlural} concluídos
        </p>

        <div style={courseGrid}>
          {completedCourses.map(c => renderCourseCard(c))}

          {completedCourses.length === 0 && (
            <p style={emptyStateText}>
              Nenhum {itemSingularLower} concluído ainda.
            </p>
          )}
        </div>
      </>
    )
  }

  function renderTodosCursos() {
    return (
      <>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "12px",
            marginBottom: "16px"
          }}
        >
          <p style={sectionTitle}>
            {event ? `${itemPlural} do ${event.name}` : itemPlural}
          </p>

          <input
            value={publicSearch}
            onChange={e => setPublicSearch(e.target.value)}
            placeholder={`Pesquise o ${itemSingularLower}`}
            style={searchInput}
          />
        </div>

        <div style={courseGrid}>
          {pagePublicCourses.map(c => renderCourseCard(c, { context: "todos" }))}

          {availablePublicCourses.length === 0 && (
            <p style={emptyStateText}>
              Nenhum {itemSingularLower} encontrado.
            </p>
          )}
        </div>

        {renderPagination(publicPage, publicTotalPages, setPublicPage)}
      </>
    )
  }

  function renderConta() {
    const attendanceStatuses = {
      presente: { symbol: "Presença aula", color: "#63bf7f", background: "#EAF7EE" },
      atividade_substitutiva: { symbol: "Atividade", color: "#497c7e", background: "#E8F0F0" },
      justificada: { symbol: "!", color: "#D88400", background: "#FFF5DF" },
      falta: { symbol: "×", color: "#E34B4B", background: "#FDEBEB" },
      a_realizar: { symbol: "Não aferida", color: "#9AA8BA", background: "#FFFFFF" }
    }
    const formatAttendanceDate = value => {
      if (!value) return "—"
      const [year, month, day] = value.split("-")
      return year && month && day ? `${day}/${month}` : value
    }

    return (
      <>
        <p style={sectionTitle}>Conta</p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "32px", alignItems: "start" }}>
        <div>

        <div style={accountCard}>
          <p style={{ margin: 0, fontWeight: "bold", fontSize: "16px" }}>
            {selectedStudent?.name}
          </p>
          <p style={{ margin: "4px 0 0 0", color: "rgba(255,255,255,0.9)", fontSize: "14px" }}>
            {selectedStudent?.email}
          </p>
        </div>

        <p style={sectionTitle}>Alterar senha</p>

        <form
          onSubmit={handleChangePassword}
          style={{ ...accountCard, display: "flex", flexDirection: "column" }}
        >
          <input
            type="password"
            placeholder="Senha atual"
            value={passwordForm.currentPassword}
            onChange={e =>
              setPasswordForm({ ...passwordForm, currentPassword: e.target.value })
            }
            style={input}
          />

          <input
            type="password"
            placeholder="Nova senha"
            value={passwordForm.newPassword}
            onChange={e =>
              setPasswordForm({ ...passwordForm, newPassword: e.target.value })
            }
            style={input}
          />

          <input
            type="password"
            placeholder="Confirmar nova senha"
            value={passwordForm.confirmPassword}
            onChange={e =>
              setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })
            }
            style={{ ...input, marginBottom: "24px" }}
          />

          {(passwordError || passwordSuccess) && (
            <div style={{ marginTop: "-12px", marginBottom: "16px" }}>
              {passwordError && <p style={{ ...errorMessage, margin: 0 }}>{passwordError}</p>}
              {passwordSuccess && <p style={{ ...successMessage, margin: 0 }}>{passwordSuccess}</p>}
            </div>
          )}

          <button type="submit" style={{ ...buttonOutline, alignSelf: "flex-start" }}>
            Trocar senha
          </button>
        </form>

        <p style={{ ...sectionTitle, color: "#FF6B6B" }}>Excluir conta</p>

        <form
          onSubmit={handleDeleteAccount}
          style={{
            ...accountCard,
            display: "flex",
            flexDirection: "column",
            border: "1px solid rgba(255,107,107,0.4)"
          }}
        >
          <p style={{ margin: "0 0 12px 0", color: "rgba(255,255,255,0.9)", fontSize: "13px" }}>
            Isso remove sua conta e seu acesso a todos os {itemPluralLower} de
            forma permanente. Não tem como desfazer.
          </p>

          <input
            type="password"
            placeholder="Digite sua senha pra confirmar"
            value={deletePassword}
            onChange={e => setDeletePassword(e.target.value)}
            style={{ ...input, marginBottom: "8px" }}
          />

          {deleteError && <p style={{ ...errorMessage, marginBottom: "8px" }}>{deleteError}</p>}

          <button
            type="submit"
            disabled={deleting}
            style={{
              alignSelf: "flex-start",
              padding: "12px 26px",
              borderRadius: "999px",
              border: "1.5px solid #FF6B6B",
              background: "transparent",
              color: "#FF6B6B",
              fontWeight: "bold",
              fontSize: "14px",
              cursor: deleting ? "default" : "pointer",
              opacity: deleting ? 0.6 : 1
            }}
          >
            {deleting ? "Excluindo..." : "Excluir minha conta"}
          </button>
        </form>
        </div>

        {event && <section style={{ background: "#FFFFFF", border: "1px solid #D9DEE7", borderRadius: "16px", overflow: "hidden", color: "#16465A", minWidth: 0 }}>
          <div style={{ padding: "22px 28px 18px", borderBottom: "1px solid #E8ECF1" }}>
            <p style={{ margin: 0, fontSize: "12px", letterSpacing: "1.6px", color: "#22B95E", fontWeight: "bold" }}>CARTEIRA DE FREQUÊNCIA</p>
            <h2 style={{ margin: "6px 0 4px", fontSize: "26px", lineHeight: 1.1 }}>{attendance?.student?.name || selectedStudent?.name}</h2>
            <p style={{ margin: 0, color: "#718096", fontSize: "13px" }}>{attendance?.student?.email || selectedStudent?.email}</p>
          </div>

          {attendanceError ? <p style={{ padding: "24px 28px", color: "#E34B4B", margin: 0 }}>{attendanceError}</p> : !attendance ? <p style={{ padding: "24px 28px", color: "#718096", margin: 0 }}>Carregando frequência...</p> : <>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(70px, 1fr))", gap: "14px", padding: "20px 28px", borderBottom: "1px solid #E8ECF1" }}>
              {[[`${attendance.stats.frequencia ?? "—"}${attendance.stats.frequencia != null ? "%" : ""}`, "Frequência"], [attendance.stats.presencas, "Presenças"], [attendance.stats.a_realizar, "A realizar"]].map(([value, label]) => <div key={label}><strong style={{ fontSize: "25px" }}>{value}</strong><span style={{ display: "block", marginTop: "4px", color: "#718096", textTransform: "uppercase", fontSize: "10px", letterSpacing: "1px" }}>{label}</span></div>)}
            </div>
            <div style={{ padding: "14px 28px 22px" }}>
              <div aria-label="Legenda da frequência" style={{ display: "flex", gap: "12px", flexWrap: "wrap", margin: "0 0 10px", fontSize: "11px", color: "#526579" }}>
                {[['#63bf7f', 'Presença aula síncrona'], ['#497c7e', 'Atividade substitutiva'], ['#9aa8ba', 'Presença não aferida']].map(([color, label]) => <span key={label} style={{ display: "inline-flex", alignItems: "center", gap: "5px" }}><i style={{ width: "9px", height: "9px", background: color, borderRadius: "50%", display: "inline-block" }} />{label}</span>)}
              </div>
              {attendance.modules.length === 0 ? <p style={{ color: "#718096", margin: "8px 0" }}>Nenhuma chamada disponível ainda.</p> : attendance.modules.map((module, index) => <div key={module.id} style={{ display: "grid", gridTemplateColumns: "92px minmax(0, 1fr) 48px", gap: "14px", alignItems: "center", padding: "12px 0" }}>
                <div><strong style={{ fontSize: "14px" }}>{module.name || `M${index + 1}`}</strong></div>
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>{module.parts.map((part, partIndex) => { const partStatus = attendanceStatuses[part.status] || attendanceStatuses.a_realizar; return <div key={part.id} title={part.label} style={{ width: "94px", minHeight: "46px", borderRadius: "8px", border: `1px solid ${partStatus.color}`, background: partStatus.background, color: partStatus.color, textAlign: "center", padding: "5px 3px 0", boxSizing: "border-box" }}><strong style={{ display: "block", lineHeight: 1, fontSize: "10px" }}>{partStatus.symbol}</strong><span style={{ fontSize: "10px" }}>{formatAttendanceDate(part.date)}</span></div> })}</div>
                <strong style={{ color: module.percent == null ? "#718096" : module.percent >= 75 ? "#22B95E" : "#E34B4B", textAlign: "right", fontSize: "12px" }}>{module.percent == null ? "—" : `${module.percent}%`}</strong>
              </div>)}
            </div>
          </>}
        </section>}
        </div>
      </>
    )
  }

  return (
    <div style={pageBackground}>
      <Navbar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        logoUrl={event?.logo_url}
        tabLabels={tabLabels}
        onLogout={() => {
          localStorage.removeItem("loggedStudent")
          onLogout()
        }}
      />

      {isAdmin && (
        <div style={{ display: "flex", gap: "10px", marginBottom: "24px" }}>
          <button
            type="button"
            onClick={onOpenReport}
            style={{
              padding: "8px 16px",
              border: "none",
              borderRadius: "10px",
              background: "#111827",
              color: "white",
              cursor: "pointer",
              fontSize: "13px"
            }}
          >
            Ver relatório do professor
          </button>

          <button
            type="button"
            onClick={onOpenAdmin}
            style={{
              padding: "8px 16px",
              border: "none",
              borderRadius: "10px",
              background: "#059669",
              color: "white",
              cursor: "pointer",
              fontSize: "13px"
            }}
          >
            Painel admin
          </button>
        </div>
      )}

      {activeTab === "meus-cursos" && renderMeusCursos()}
      {activeTab === "todos-cursos" && renderTodosCursos()}
      {activeTab === "conta" && renderConta()}

      {event?.show_footer && <Footer />}
    </div>
  )
}

export default Dashboard
