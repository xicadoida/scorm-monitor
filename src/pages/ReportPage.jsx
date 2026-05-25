import { useEffect, useState } from 'react'

function ReportPage({ API_URL, onBack }) {
  const [sessions, setSessions] = useState([])

  useEffect(() => {
    async function loadSessions() {
      const response = await fetch(`${API_URL}/sessions`)
      const data = await response.json()
      setSessions(data)
    }

    loadSessions()
  }, [API_URL])

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
            {sessions.map(session => (
              <tr key={session.id} style={{ borderBottom: "1px solid #eee" }}>
                <td style={td}>{session.student_id}</td>
                <td style={td}>{session.course_id}</td>
                <td style={td}>{session.status}</td>
                <td style={td}>{session.completed ? "Sim" : "Não"}</td>
                <td style={td}>{session.session_time || "-"}</td>
                <td style={td}>{session.started_at}</td>
                <td style={td}>{session.ended_at || "-"}</td>
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

export default ReportPage