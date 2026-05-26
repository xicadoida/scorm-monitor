import { useEffect, useRef, useState } from 'react'
import { Scorm12API } from 'scorm-again'
import Dashboard from './pages/Dashboard'
import ReportPage from './pages/ReportPage'
import LoginPage from './pages/LoginPage'
import AdminPage from './pages/AdminPage'


function App() {
  const [currentPage, setCurrentPage] = useState("dashboard")
  const [courses, setCourses] = useState([])
  const [selectedCourse, setSelectedCourse] = useState(null)
  const [students, setStudents] = useState([])
  const [selectedStudent, setSelectedStudent] = useState(null)

  const iframeRef = useRef(null)
  const savedProgressRef = useRef({
    suspend_data: "",
    lesson_location: ""
  })

  const studentId = selectedStudent?.student_code || ""
  const courseId = selectedCourse?.course_code || ""

  const [records, setRecords] = useState([])

  const [trackingData, setTrackingData] = useState({
    status: "-",
    completed: false,
    sessionTime: "-",
    completedAt: "-",
    sessionsCount: 0
  })

  const [sessionId, setSessionId] = useState(null)
  const [loggedStudent, setLoggedStudent] = useState(null)
  const API_URL =
    import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"


  async function finishBackendSession(id) {
    if (!id) return

    await fetch(`${API_URL}/sessions/${id}/finish`, {
      method: "POST"
    })
  }

  async function loadStudentProgress(student, course) {
    if (!student || !course) return

    const response = await fetch(
      `${API_URL}/progress/${student}/${course}`
    )

    const data = await response.json()

    savedProgressRef.current = {
      suspend_data: data.suspend_data || "",
      lesson_location: data.lesson_location || ""
    }

    setTrackingData(prev => ({
      ...prev,
      status: data.last_status,
      completed: data.completed,
      sessionTime: data.total_session_time || "-",
      completedAt: data.completed
        ? "Já concluído anteriormente"
        : "-",
      sessionsCount: data.sessions_count || 0
    }))
  }
  
  function loadRecords() {
    const saved = []

    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)

      if (key.startsWith("completion_")) {
        saved.push(JSON.parse(localStorage.getItem(key)))
      }
    }

    setRecords(saved)
  }

  function saveCompletion(status) {
    const record = {
      studentId,
      courseId,
      status,
      completed: true,
      completedAt: new Date().toLocaleString()
    }

    localStorage.setItem(
      `completion_${studentId}_${courseId}`,
      JSON.stringify(record)
    )

    loadRecords()
  }

  function clearRecords() {
    Object.keys(localStorage).forEach(key => {
      if (key.startsWith("completion_")) {
        localStorage.removeItem(key)
      }
    })

    setRecords([])
  }
  async function startBackendSession() {
    const response = await fetch(`${API_URL}/sessions/start`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        student_id: studentId,
        course_id: courseId
      })
    })

    const data = await response.json()
    setSessionId(data.session_id)

    return data.session_id
  }

  async function updateBackendSession(id, payload) {
    if (!id) return

    await fetch(`${API_URL}/sessions/${id}/update`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    })
  }
  
  useEffect(() => {
    const saved = localStorage.getItem("loggedStudent")

    if (saved) {
      const student = JSON.parse(saved)
      setLoggedStudent(student)
      setSelectedStudent(student)
      setCurrentPage("dashboard")
    } else {
      setCurrentPage("login")
    }
  }, [])

  useEffect(() => {
    const handleBeforeUnload = () => {
      if (sessionId) {
        navigator.sendBeacon(
          `${API_URL}/sessions/${sessionId}/finish`
        )
      }
    }

    window.addEventListener(
      "beforeunload",
      handleBeforeUnload
    )

    return () => {
      window.removeEventListener(
        "beforeunload",
        handleBeforeUnload
      )

      if (sessionId) {
        finishBackendSession(sessionId)
      }
    }
  }, [sessionId])

  useEffect(() => {
    if (selectedCourse) {
      loadStudentProgress(studentId, selectedCourse.course_code)
    }
  }, [studentId, selectedCourse])

  useEffect(() => {
    async function loadCoursesForStudent() {
      if (!selectedStudent) return

      const response = await fetch(
        `${API_URL}/students/${selectedStudent.student_code}/courses`
      )

      const data = await response.json()

      setCourses(data)

      if (data.length > 0) {
        setSelectedCourse(data[0])
      } else {
        setSelectedCourse(null)
      }
    }

    loadCoursesForStudent()
  }, [selectedStudent])

  useEffect(() => {
    loadRecords()
  }, [])

  useEffect(() => {
    if (!selectedCourse || !selectedStudent || currentPage !== "player") return

    let currentSessionId = null

    startBackendSession().then(id => {
      currentSessionId = id
    })

    const api = new Scorm12API({
      autocommit: true,
      logLevel: 1
    })

    const originalSetValue = api.LMSSetValue.bind(api)
    const originalGetValue = api.LMSGetValue.bind(api)
    

    api.LMSGetValue = function(key) {
      if (key === "cmi.suspend_data") {
        return savedProgressRef.current.suspend_data || originalGetValue(key)
      }

      if (key === "cmi.core.lesson_location") {
        return savedProgressRef.current.lesson_location || originalGetValue(key)
      }

      return originalGetValue(key)
    }

    api.LMSSetValue = function(key, value) {
      if (
        key.includes("suspend_data") ||
        key.includes("lesson_location") ||
        key.includes("location")
      ) {
        console.log("SCORM PROGRESS:", key, value)
      }
      if (key.includes("suspend_data")) {
        updateBackendSession(currentSessionId, {
          suspend_data: value
        })
      }

      if (
        key.includes("lesson_location") ||
        key.includes("location")
      ) {
        updateBackendSession(currentSessionId, {
          lesson_location: value
        })
      }
      const isStatus = key === "cmi.core.lesson_status"
      const isSessionTime = key === "cmi.core.session_time"

      if (isStatus || isSessionTime) {
        setTrackingData(prev => {
          const updated = { ...prev }

          if (isStatus) {
            updateBackendSession(currentSessionId, {
              status: value,
              completed: value === "completed" || value === "passed"
            })  
            updated.status = value

            if (value === "completed" || value === "passed") {
              updated.completed = true
              updated.completedAt = new Date().toLocaleString()
              saveCompletion(value)
            }
          }

          if (isSessionTime) {
            updateBackendSession(currentSessionId, {
            session_time: value
          })  
            updated.sessionTime = value
          }

          return updated
        })
      }

      return originalSetValue(key, value)
    }

    window.API = api

    const iframe = iframeRef.current

    if (iframe) {
      iframe.onload = () => {
        iframe.contentWindow.API = api
      }
    }
  }, [studentId, selectedCourse, currentPage])

  if (currentPage === "report") {
    return (
      <ReportPage
        API_URL={API_URL}
        onBack={() => setCurrentPage("dashboard")}
      />
    )
  }
  if (currentPage === "login") {
    return (
      <LoginPage
        API_URL={API_URL}
        onLogin={(student) => {
          setLoggedStudent(student)
          setSelectedStudent(student)
          setCurrentPage("dashboard")
        }}
      />
    )
  }
  if (currentPage === "admin") {
    return (
      <AdminPage
        API_URL={API_URL}
        onBack={() => setCurrentPage("dashboard")}
      />
    )
  }
  if (currentPage === "dashboard") {
    return (
      <Dashboard
        onOpenAdmin={() => setCurrentPage("admin")}
        selectedStudent={selectedStudent}
        courses={courses}
        API_URL={API_URL}
        onOpenReport={() => setCurrentPage("report")}
        onLogout={() => {
          localStorage.removeItem("loggedStudent")
          setLoggedStudent(null)
          setSelectedStudent(null)
          setCurrentPage("login")
        }}
        onOpenCourse={(course) => {
          setSelectedCourse(course)
          setCurrentPage("player")
        }}
      />  
    )
  }
  return (
    <div style={{ display: "flex", height: "100vh" }}>
      <div style={{ flex: 3 }}>
        {selectedCourse ? (
          <iframe
            ref={iframeRef}
            src={selectedCourse.scorm_path}
            width="100%"
            height="100%"
            title="SCORM"
            style={{ border: "none" }}
          />
        ) : (
          <div style={{ padding: "40px" }}>
            Carregando curso...
          </div>
        )}
      </div>

      <div style={{
        flex: 1,
        padding: "20px",
        background: "#1e1e1e",
        color: "white",
        fontFamily: "Arial",
        overflow: "auto"
      }}>
        <h2>Registro do aluno</h2>
        <button
          onClick={() => setCurrentPage("dashboard")}
          style={{ marginBottom: "20px" }}
        >
          Voltar para cursos
        </button>
        <p>
          <strong>Aluno:</strong><br />
          {selectedStudent?.name} — {selectedStudent?.email}
        </p>

        <label>Curso:</label>
          <select
            value={selectedCourse?.course_code || ""}
            onChange={e => {
              const course = courses.find(c => c.course_code === e.target.value)
              setSelectedCourse(course)

              if (iframeRef.current && course) {
                iframeRef.current.src = course.scorm_path + "?reload=" + Date.now()
              }
            }}
            style={{
              width: "100%",
              marginTop: "8px",
              marginBottom: "20px"
            }}
          >
            {courses.map(course => (
              <option key={course.id} value={course.course_code}>
                {course.title}
              </option>
            ))}
          </select>

        <p><strong>Curso:</strong><br />{selectedCourse?.title || "Nenhum curso"}</p>
        <p><strong>Status atual:</strong><br />{trackingData.status}</p>
        <p><strong>Completou?</strong><br />{trackingData.completed ? "Sim" : "Não"}</p>
        <p><strong>Tempo sessão:</strong><br />{trackingData.sessionTime}</p>
        <p>
          <strong>Sessões realizadas:</strong><br />
          {trackingData.sessionsCount}
        </p>
        <p><strong>Concluído em:</strong><br />{trackingData.completedAt}</p>

        <hr />

        <h2>Registros salvos</h2>

        <button onClick={clearRecords}>
          Limpar registros
        </button>

        <div style={{ marginTop: "16px" }}>
          {records.length === 0 && (
            <p>Nenhum registro salvo ainda.</p>
          )}

          {records.map((record, index) => (
            <div
              key={index}
              style={{
                background: "#2b2b2b",
                padding: "12px",
                marginBottom: "10px",
                borderRadius: "6px"
              }}
            >
              <strong>Aluno:</strong> {record.studentId}<br />
              <strong>Curso:</strong> {record.courseId}<br />
              <strong>Status:</strong> {record.status}<br />
              <strong>Concluiu:</strong> {record.completed ? "Sim" : "Não"}<br />
              <strong>Data:</strong> {record.completedAt}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default App