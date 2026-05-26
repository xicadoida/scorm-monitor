import { useEffect, useState } from 'react'

function ReportPage({ API_URL, onBack }) {
  const [sessions, setSessions] = useState([])
  const [studentFilter, setStudentFilter] = useState("")
  const [courseFilter, setCourseFilter] = useState("")
  const [statusFilter, setStatusFilter] = useState("")

  useEffect(() => {
    async function loadSessions() {
      const response = await fetch(`${API_URL}/sessions`)
      const data = await response.json()
      setSessions(data)
    }

    loadSessions()
  }, [API_URL])

  function formatDate(dateString) {
    if (!dateString) return "-"

    const date = new Date(dateString)

    return date.toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    })
  }

  function formatStatus(status) {
    const statusMap = {
      completed: "Concluído",
      passed: "Aprovado",
      incomplete: "Em andamento",
      failed: "Reprovado",
      not_attempted: "Não iniciado"
    }

    return statusMap[status] || status || "-"
  }

  function formatCompleted(completed) {
    return completed ? "Sim" : "Não"
  }

  function formatSessionTime(time) {
    if (!time) return "-"

    const parts = time.split(":")

    if (parts.length < 3) return time

    const hours = parseInt(parts[0])
    const minutes = parseInt(parts[1])
    const seconds = Math.floor(parseFloat(parts[2]))

    const result = []

    if (hours > 0) result.push(`${hours}h`)
    if (minutes > 0) result.push(`${minutes}min`)
    if (seconds > 0) result.push(`${seconds}s`)

    return result.length > 0 ? result.join(" ") : "0s"
  }

  const totalSessions = sessions.length

  const completedSessions = sessions.filter(
    session => session.completed
  ).length

  const inProgressSessions = sessions.filter(
    session => !session.completed
  ).length

  const filteredSessions = sessions.filter(session => {
    const matchesStudent =
      studentFilter === "" ||
      session.student_id.toLowerCase().includes(studentFilter.toLowerCase())

    const matchesCourse =
      courseFilter === "" ||
      session.course_id.toLowerCase().includes(courseFilter.toLowerCase())

    const matchesStatus =
      statusFilter === "" ||

      (
        statusFilter === "completed" &&
        (session.status === "completed" || session.status === "passed")
      ) ||

      (
        statusFilter !== "completed" &&
        session.status === statusFilter
      )

    return matchesStudent && matchesCourse && matchesStatus
  })

  return (
    <div style={{
      minHeight: "100vh",
      background: "#f4f6fb",
      padding: "32px",
      fontFamily: "Arial"
    }}>
      <button onClick={onBack}>Voltar</button>

      <h1>Relatório de Progresso</h1>
      <p style={{ color: "#555" }}>
        Acompanhamento geral das sessões dos alunos.
      </p>
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
        gap: "16px",
        marginTop: "24px"
      }}>
        <SummaryCard title="Sessões totais" value={totalSessions} />
        <SummaryCard title="Conclusões" value={completedSessions} />
        <SummaryCard title="Em andamento" value={inProgressSessions} />
      </div>
      <div style={{
        background: "white",
        borderRadius: "16px",
        padding: "20px",
        marginTop: "24px",
        boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
        gap: "16px"
      }}>
        <input
          placeholder="Filtrar por aluno"
          value={studentFilter}
          onChange={e => setStudentFilter(e.target.value)}
          style={inputStyle}
        />

        <input
          placeholder="Filtrar por curso"
          value={courseFilter}
          onChange={e => setCourseFilter(e.target.value)}
          style={inputStyle}
        />

        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          style={inputStyle}
        >
          <option value="">Todos os status</option>
          <option value="incomplete">Em andamento</option>
          <option value="completed">Concluído</option>
          <option value="passed">Aprovado</option>
          <option value="failed">Reprovado</option>
        </select>
      </div>
      <div style={{
        background: "white",
        borderRadius: "16px",
        padding: "24px",
        marginTop: "24px",
        boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
        overflowX: "auto"
      }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>
              <th style={th}>Aluno</th>
              <th style={th}>Curso</th>
              <th style={th}>Status</th>
              <th style={th}>Concluiu</th>
              <th style={th}>Tempo</th>
              <th style={th}>Início</th>
              <th style={th}>Fim</th>
            </tr>
          </thead>

          <tbody>
            {[...filteredSessions]
              .sort((a, b) =>
                new Date(b.started_at) - new Date(a.started_at)
              )
              .map(session => (
              <tr key={session.id} style={{ borderBottom: "1px solid #eee" }}>
                <td style={td}>{session.student_id}</td>
                <td style={td}>{session.course_id}</td>
                <td style={td}>{formatStatus(session.status)}</td>
                <td style={td}>{formatCompleted(session.completed)}</td>
                <td style={td}>{formatSessionTime(session.session_time)}</td>
                <td style={td}>{formatDate(session.started_at)}</td>
                <td style={td}>{formatDate(session.ended_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const th = { padding: "12px", color: "#555" }
const td = { padding: "12px" }
const inputStyle = {
  padding: "10px",
  borderRadius: "10px",
  border: "1px solid #ddd"
}

function formatDate(dateString) {
  if (!dateString) return "-"

  const date = new Date(dateString)

  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  })
}

function SummaryCard({ title, value }) {
  return (
    <div style={{
      background: "white",
      borderRadius: "16px",
      padding: "20px",
      boxShadow: "0 4px 16px rgba(0,0,0,0.08)"
    }}>
      <p style={{ color: "#666", margin: 0 }}>{title}</p>
      <h2 style={{ margin: "8px 0 0", fontSize: "32px" }}>{value}</h2>
    </div>
  )
}

export default ReportPage