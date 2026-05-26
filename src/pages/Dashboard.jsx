import { useEffect, useState } from 'react'

function Dashboard({
  selectedStudent,
  courses,
  onOpenCourse,
  onOpenReport,
  onLogout,
  onOpenAdmin,
  API_URL
}) {

  const [progressData, setProgressData] = useState({})

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

  return (
    <div style={{
      minHeight: "100vh",
      background: "#f4f6fb",
      padding: "32px",
      fontFamily: "Arial"
    }}>
    <button
      onClick={() => {
        localStorage.removeItem("loggedStudent")
        onLogout()
      }}
      style={{
        padding: "10px 16px",
        border: "none",
        borderRadius: "10px",
        background: "#dc2626",
        color: "white",
        cursor: "pointer",
        marginBottom: "20px"
      }}
    >
      Sair
    </button>
      <h1>Plataforma de Cursos</h1>
        
      <p style={{ color: "#555" }}>
        Acompanhe os cursos disponíveis e o progresso dos alunos.
      </p>
      <button
        onClick={onOpenReport}
        style={{
            padding: "10px 16px",
            border: "none",
            borderRadius: "10px",
            background: "#111827",
            color: "white",
            cursor: "pointer"
        }}
        >
        Ver relatório do professor
        </button>
      <button
        onClick={onOpenAdmin}
        style={{
          padding: "10px 16px",
          border: "none",
          borderRadius: "10px",
          background: "#059669",
          color: "white",
          cursor: "pointer",
          marginLeft: "12px"
        }}
      >
        Painel admin
      </button>
      <div style={{
        background: "white",
        padding: "20px",
        borderRadius: "16px",
        marginTop: "24px",
        boxShadow: "0 4px 16px rgba(0,0,0,0.08)"
      }}>
        <strong>Aluno logado:</strong>
        <p style={{ marginBottom: 0 }}>
          {selectedStudent?.name} — {selectedStudent?.email}
        </p>
      </div>
    
      <h2 style={{ marginTop: "32px" }}>Cursos disponíveis</h2>

      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
        gap: "20px"
      }}>
        {courses.map(course => {
          const progress = progressData[course.course_code]

          return (
            <div
              key={course.id}
              style={{
                background: "white",
                borderRadius: "16px",
                padding: "24px",
                boxShadow: "0 4px 16px rgba(0,0,0,0.08)"
              }}
            >
              <h3>{course.title}</h3>

              <p style={{ color: "#666" }}>
                Código: {course.course_code}
              </p>

              <div style={{ marginTop: "16px" }}>
                <p>
                  <strong>Status:</strong>{" "}
                  {progress?.completed
                    ? "Concluído"
                    : progress?.sessions_count > 0
                    ? "Em andamento"
                    : "Não iniciado"}
                </p>

                <p>
                  <strong>Sessões:</strong>{" "}
                  {progress?.sessions_count || 0}
                </p>

                <p>
                  <strong>Tempo:</strong>{" "}
                  {progress?.total_session_time || "-"}
                </p>
              </div>

              <button
                onClick={() => onOpenCourse(course)}
                style={{
                  marginTop: "16px",
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
                {progress?.completed ? "Revisar curso" : "Continuar curso"}
              </button>
            </div>
          )
        })}

        {courses.length === 0 && (
          <p>Nenhum curso liberado para este aluno.</p>
        )}
      </div>
    </div>
    
  )
}

export default Dashboard