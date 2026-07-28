import { useEffect, useMemo, useState } from 'react'
import Navbar from '../components/Navbar'
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
  progressWrapper,
  progressPercentLabel,
  progressTrack,
  progressFill,
  emptyStateText,
  paginationWrapper,
  paginationButton,
  paginationButtonActive,
  paginationArrow,
  accountCard
} from '../styles/theme'

const COURSES_PER_PAGE = 6

// Ainda não existe carga horária nem % de progresso real vindos do backend.
// Por enquanto aproximamos os dois a partir do que já temos (status e tempo de sessão),
// só pra ter algo visual coerente pra apresentação. Quando o backend tiver esses dados
// de verdade, é só trocar essas duas funções.
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
  API_URL
}) {
  const [activeTab, setActiveTab] = useState("meus-cursos")
  const [progressData, setProgressData] = useState({})
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(1)

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
    setPage(1)
  }, [search, activeTab])

  const filteredCourses = useMemo(() => {
    return courses.filter(course =>
      course.title.toLowerCase().includes(search.toLowerCase())
    )
  }, [courses, search])

  const totalPages = Math.max(
    1,
    Math.ceil(filteredCourses.length / COURSES_PER_PAGE)
  )

  const pageCourses = filteredCourses.slice(
    (page - 1) * COURSES_PER_PAGE,
    page * COURSES_PER_PAGE
  )

  const completedCourses = courses.filter(
    course => progressData[course.course_code]?.completed
  )

  function renderCourseCard(course) {
    const progress = progressData[course.course_code]
    const percent = estimateProgress(progress)

    return (
      <div key={course.id} style={courseCard}>
        <div style={courseCardHeader}>
          <div>
            <p style={courseCardTitle}>{course.title}</p>
            <p style={courseCardSubtitle}>
              {formatHours(progress?.total_session_time)}
            </p>
          </div>

          <button
            type="button"
            onClick={() => onOpenCourse(course)}
            style={coursePillButton}
          >
            Acessar
          </button>
        </div>

        <div style={progressWrapper}>
          <p style={progressPercentLabel}>{percent}%</p>
          <div style={progressTrack}>
            <div style={progressFill(percent)} />
          </div>
        </div>
      </div>
    )
  }

  function renderPagination() {
    if (totalPages <= 1) return null

    return (
      <div style={paginationWrapper}>
        <button
          type="button"
          style={paginationArrow}
          onClick={() => setPage(p => Math.max(1, p - 1))}
          disabled={page === 1}
        >
          ‹
        </button>

        {Array.from({ length: totalPages }, (_, i) => i + 1).map(n => (
          <button
            key={n}
            type="button"
            style={n === page ? paginationButtonActive : paginationButton}
            onClick={() => setPage(n)}
          >
            {n}
          </button>
        ))}

        <button
          type="button"
          style={paginationArrow}
          onClick={() => setPage(p => Math.min(totalPages, p + 1))}
          disabled={page === totalPages}
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
          <p style={sectionTitle}>Meus cursos</p>

          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Pesquise o curso"
            style={searchInput}
          />
        </div>

        <div style={courseGrid}>
          {pageCourses.map(renderCourseCard)}

          {filteredCourses.length === 0 && (
            <p style={emptyStateText}>
              Nenhum curso encontrado.
            </p>
          )}
        </div>

        {renderPagination()}
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

        <p style={sectionTitle}>Cursos concluídos</p>

        <div style={courseGrid}>
          {completedCourses.map(renderCourseCard)}

          {completedCourses.length === 0 && (
            <p style={emptyStateText}>
              Nenhum curso concluído ainda.
            </p>
          )}
        </div>
      </>
    )
  }

  function renderEmBreve() {
    return <p style={emptyStateText}>Essa área ainda está em construção.</p>
  }

  return (
    <div style={pageBackground}>
      <Navbar
        activeTab={activeTab}
        onTabChange={setActiveTab}
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
      {activeTab === "conta" && renderConta()}
      {activeTab === "inicio" && renderEmBreve()}
      {activeTab === "todos-cursos" && renderEmBreve()}
    </div>
  )
}

export default Dashboard