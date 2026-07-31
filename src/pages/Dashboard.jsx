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

function getAttendanceStatus(progress) {
  if (progress?.completed) {
    return { label: "Concluído", color: "#7CD992" }
  }

  if (progress?.sessions_count > 0) {
    return { label: "Em andamento", color: "#F2B134" }
  }

  return { label: "Não iniciado", color: "#94A3B8" }
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

    let buttonLabel = "Inscrever"
    let buttonAction = () => handleEnroll(course)
    let buttonDisabled = enrollingCode === course.course_code
    let buttonStyle = coursePillButton

    if (!isMeus) {
      if (isCompleted) {
        buttonLabel = "Concluído"
        buttonAction = () => onOpenCourse(course)
        buttonDisabled = false
        buttonStyle = { ...coursePillButton, opacity: 0.7 }
      } else if (isEnrolled) {
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
          <div>
            <p style={courseCardTitle}>{course.title}</p>
            {isMeus && showProgress && (
              <p style={courseCardSubtitle}>
                {formatHours(progress?.total_session_time)}
              </p>
            )}
          </div>

          {isMeus ? (
            <button
              type="button"
              onClick={() => onOpenCourse(course)}
              style={coursePillButton}
            >
              Acessar
            </button>
          ) : (
            <button
              type="button"
              onClick={buttonAction}
              disabled={buttonDisabled}
              style={buttonStyle}
            >
              {buttonLabel}
            </button>
          )}
        </div>

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
    return (
      <>
        <p style={sectionTitle}>Conta</p>

        <div style={accountCard}>
          <p style={{ margin: 0, fontWeight: "bold", fontSize: "16px" }}>
            {selectedStudent?.name}
          </p>
          <p style={{ margin: "4px 0 0 0", color: "#B9C2D0", fontSize: "14px" }}>
            {selectedStudent?.email}
          </p>
        </div>

        <p style={sectionTitle}>Frequência</p>

        <div style={{ ...accountCard, maxWidth: "520px" }}>
          {courses.length === 0 ? (
            <p style={{ margin: 0, color: "#B9C2D0", fontSize: "14px" }}>
              Você ainda não tem {itemPluralLower} atribuídos.
            </p>
          ) : (
            courses.map(course => {
              const status = getAttendanceStatus(
                progressData[course.course_code]
              )

              return (
                <div
                  key={course.course_code}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "10px 0",
                    borderBottom: "1px solid rgba(255,255,255,0.1)"
                  }}
                >
                  <span style={{ color: "white", fontSize: "14px" }}>
                    {course.title}
                  </span>

                  <span
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      fontSize: "13px",
                      color: status.color,
                      whiteSpace: "nowrap"
                    }}
                  >
                    <span
                      style={{
                        width: "8px",
                        height: "8px",
                        borderRadius: "999px",
                        background: status.color,
                        display: "inline-block"
                      }}
                    />
                    {status.label}
                  </span>
                </div>
              )
            })
          )}
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
          <p style={{ margin: "0 0 12px 0", color: "#B9C2D0", fontSize: "13px" }}>
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