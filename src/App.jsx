import { useCallback, useEffect, useRef, useState } from 'react'
import { Scorm12API, Scorm2004API } from 'scorm-again'
import Dashboard from './pages/Dashboard'
import ReportPage from './pages/ReportPage'
import LoginPage from './pages/LoginPage'
import AdminPage from './pages/AdminPage'
import RegisterPage from './pages/RegisterPage'

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
  const [landingEvent, setLandingEvent] = useState(null)
  const [pendingCourseCode, setPendingCourseCode] = useState(null)
  const ADMIN_EMAILS = [
    "admin@admin.com"
  ]
  const isAdmin =
    loggedStudent &&
    ADMIN_EMAILS.includes(loggedStudent.email)        
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
    async function initializeApp() {
      const pathSegment = window.location.pathname.split("/").filter(Boolean)[0]

      if (pathSegment) {
        try {
          const response = await fetch(`${API_URL}/events/slug/${encodeURIComponent(pathSegment)}`)
          const data = await response.json()
          if (data.success) {
            setLandingEvent(data.event)
            setCurrentPage("login")
            return
          }
        } catch {
          // Se a API estiver indisponível, segue para a tela padrão.
        }
      }

      const saved = localStorage.getItem("loggedStudent")

      if (saved) {
        const student = JSON.parse(saved)
        // Contas de evento não podem continuar autenticadas na área padrão.
        if (student.event) {
          localStorage.removeItem("loggedStudent")
          setCurrentPage("login")
          return
        }
        setLoggedStudent(student)
        setSelectedStudent(student)
        setCurrentPage("dashboard")
      } else {
        setCurrentPage("login")
      }
    }

    initializeApp()
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
    const params = new URLSearchParams(window.location.search)
    const cursoParam = params.get("curso")

    if (cursoParam) {
      setPendingCourseCode(cursoParam)
    }
  }, [])
  const reloadCourses = useCallback(async () => {
    if (!selectedStudent) return

    const response = await fetch(
      `${API_URL}/students/${selectedStudent.student_code}/courses`
    )

    const data = await response.json()

    setCourses(data)

    if (pendingCourseCode) {
      const targetCourse = data.find(
        c => c.course_code === pendingCourseCode
      )

      if (targetCourse) {
        setSelectedCourse(targetCourse)
        setCurrentPage("player")
      } else {
        alert("Você não tem acesso a esse curso, ou ele não existe.")
      }

      setPendingCourseCode(null)
      window.history.replaceState({}, "", "/")
    }
  }, [selectedStudent, pendingCourseCode, API_URL])

  useEffect(() => {
    reloadCourses()
  }, [reloadCourses])

  useEffect(() => {
    loadRecords()
  }, [])

  useEffect(() => {
    if (!selectedCourse || !selectedStudent || currentPage !== "player") return

    let currentSessionId = null
    let cancelled = false
    let pendingSessionUpdate = {}
    const interactionResults = new Map()
    let completionTimer = null

    // O SCORM pode iniciar e devolver o resultado antes da resposta do
    // endpoint /sessions/start. Guardamos esses dados para não perder
    // aprovação, reprovação ou progresso nesse intervalo.
    const sendSessionUpdate = (payload) => {
      if (currentSessionId) {
        updateBackendSession(currentSessionId, payload)
      } else {
        pendingSessionUpdate = { ...pendingSessionUpdate, ...payload }
      }
    }

    const sendCalculatedQuizScore = () => {
      const results = [...interactionResults.values()]
      if (results.length === 0) return
      const correct = results.filter(result => result === "correct").length
      const score = (correct / results.length) * 100
      console.info("[SCORM] Nota calculada pelas questões:", score, `${correct}/${results.length}`)
      sendSessionUpdate({ score_raw: score })
    }

    const rememberInteraction = (key, value) => {
      const match = key.match(/^cmi\.interactions\.(\d+)\.result$/)
      if (!match || !["correct", "incorrect"].includes(String(value).toLowerCase())) return
      interactionResults.set(match[1], String(value).toLowerCase())
    }

    startBackendSession().then(id => {
      if (!cancelled) {
        currentSessionId = id
        if (Object.keys(pendingSessionUpdate).length > 0) {
          updateBackendSession(id, pendingSessionUpdate)
          pendingSessionUpdate = {}
        }
      }
    })

    const api = new Scorm12API({
      autocommit: true,
      logLevel: 1
    })
    // Os cursos antigos usam SCORM 1.2; os novos, com quiz, usam SCORM 2004.
    // Os dois objetos precisam estar disponíveis para o pacote identificar a API certa.
    const api2004 = new Scorm2004API({
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
      rememberInteraction(key, value)
      if (
        key.includes("suspend_data") ||
        key.includes("lesson_location") ||
        key.includes("location")
      ) {
        console.log("SCORM PROGRESS:", key, value)
      }
      if (key.includes("suspend_data")) {
        sendSessionUpdate({
          suspend_data: value
        })
      }

      if (
        key.includes("lesson_location") ||
        key.includes("location")
      ) {
        sendSessionUpdate({
          lesson_location: value
        })
      }
      const isStatus = key === "cmi.core.lesson_status"
      const isSessionTime = key === "cmi.core.session_time"
      const isScore = key === "cmi.core.score.raw"

      if (isStatus || isSessionTime) {
        setTrackingData(prev => {
          const updated = { ...prev }

          if (isStatus) {
            sendSessionUpdate({
              status: value,
              completed: value === "passed"
            })  
            updated.status = value

            if (value === "passed") {
              updated.completed = true
              updated.completedAt = new Date().toLocaleString()
              saveCompletion(value)
            }
          }

          if (isSessionTime) {
            sendSessionUpdate({
            session_time: value
          })  
            updated.sessionTime = value
          }

          return updated
        })
      }

      if (key === "cmi.core.lesson_status" && ["completed", "passed"].includes(value)) {
        clearTimeout(completionTimer)
        completionTimer = setTimeout(sendCalculatedQuizScore, 300)
      }

      if (isScore && !Number.isNaN(Number(value))) {
        console.info("[SCORM 1.2] Nota do quiz:", value)
        sendSessionUpdate({ score_raw: Number(value) })
      }

      return originalSetValue(key, value)
    }

    const originalGetValue2004 = api2004.GetValue.bind(api2004)
    const originalSetValue2004 = api2004.SetValue.bind(api2004)

    api2004.GetValue = function(key) {
      if (key === "cmi.suspend_data") {
        return savedProgressRef.current.suspend_data || originalGetValue2004(key)
      }

      if (key === "cmi.location") {
        return savedProgressRef.current.lesson_location || originalGetValue2004(key)
      }

      return originalGetValue2004(key)
    }

    api2004.SetValue = function(key, value) {
      rememberInteraction(key, value)
      if (key === "cmi.suspend_data") {
        sendSessionUpdate({ suspend_data: value })
      }

      if (key === "cmi.location") {
        sendSessionUpdate({ lesson_location: value })
      }

      // No SCORM 2004, aprovado/reprovado fica em success_status;
      // completion_status sozinho não representa o resultado do quiz.
      if (key === "cmi.success_status") {
        console.info("[SCORM 2004] Resultado do quiz:", value)
        sendSessionUpdate({
          status: value,
          completed: value === "passed"
        })

        setTrackingData(prev => ({
          ...prev,
          status: value,
          completed: value === "passed",
          ...(value === "passed" ? { completedAt: new Date().toLocaleString() } : {})
        }))

        if (value === "passed") {
          saveCompletion(value)
        }
      }

      if (key === "cmi.completion_status" && value === "completed") {
        clearTimeout(completionTimer)
        completionTimer = setTimeout(sendCalculatedQuizScore, 300)
      }

      if (key === "cmi.session_time") {
        sendSessionUpdate({ session_time: value })
        setTrackingData(prev => ({ ...prev, sessionTime: value }))
      }

      if (key === "cmi.score.raw" && !Number.isNaN(Number(value))) {
        console.info("[SCORM 2004] Nota do quiz:", value)
        sendSessionUpdate({ score_raw: Number(value) })
      }

      return originalSetValue2004(key, value)
    }

    window.API = api
    window.API_1484_11 = api2004

    const iframe = iframeRef.current

    if (iframe) {
      iframe.onload = () => {
        iframe.contentWindow.API = api
        iframe.contentWindow.API_1484_11 = api2004
      }
    }

    return () => {
      cancelled = true
      clearTimeout(completionTimer)

      if (iframe) {
        iframe.onload = null
      }

      if (window.API === api) {
        window.API = undefined
      }
      if (window.API_1484_11 === api2004) {
        window.API_1484_11 = undefined
      }
    }
  }, [studentId, selectedCourse, currentPage])

  if (currentPage === "report" && isAdmin) {
    return (
      <ReportPage
        API_URL={API_URL}
        onBack={() => setCurrentPage("dashboard")}
      />
    )
  }
  if (currentPage === "register") {
    return (
      <RegisterPage
        API_URL={API_URL}
        event={landingEvent}
        onBackToLogin={() => setCurrentPage("login")}
      />
    )
  }

  if (currentPage === "login") {
    return (
      <LoginPage
        API_URL={API_URL}
        event={landingEvent}
        onGoToRegister={() => setCurrentPage("register")}
        onLogin={(student) => {
          setLoggedStudent(student)
          setSelectedStudent(student)
          setCurrentPage("dashboard")
          
        }}
      />
    )
  }
  if (currentPage === "admin" && isAdmin) {
    return (
      <AdminPage
        API_URL={API_URL}
        onBack={() => setCurrentPage("dashboard")}
      />
    )
  }
  if (currentPage === "dashboard") {
    const event = loggedStudent?.event

    const eventThemeVars = event
      ? {
          ...(event.color_primary && { "--lms-navy": event.color_primary }),
          ...(event.color_secondary && { "--lms-orange": event.color_secondary })
        }
      : {}

    return (
      <div style={eventThemeVars}>
        <Dashboard
          onOpenAdmin={() => setCurrentPage("admin")}
          selectedStudent={selectedStudent}
          courses={courses}
          API_URL={API_URL}
          isAdmin={isAdmin}
          event={event}
          reloadCourses={reloadCourses}
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
      </div>
    )
  }
  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      <button
        onClick={() => setCurrentPage("dashboard")}
        style={{
          position: "absolute",
          top: "10px",
          right: "10px",
          zIndex: 1000,
          padding: "10px 16px",
          border: "none",
          borderRadius: "8px",
          cursor: "pointer"
        }}
      >
        Voltar para cursos
      </button>

      <div style={{ flex: 1 }}>
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
    </div>
  )
}

export default App
