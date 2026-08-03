import { useEffect, useState } from 'react'

function AdminPage({ API_URL, onBack }) {
  const [selectedEnrollmentClass, setSelectedEnrollmentClass] = useState("")
  const [selectedEnrollmentCourse, setSelectedEnrollmentCourse] = useState("")
  const [students, setStudents] = useState([])
  const [courses, setCourses] = useState([])
  const [events, setEvents] = useState([])
  const [attendanceModules, setAttendanceModules] = useState([])
  const [attendanceModuleForm, setAttendanceModuleForm] = useState({
    name: "",
    event_id: "",
    position: ""
  })
  const [attendancePartForm, setAttendancePartForm] = useState({
    module_id: "",
    course_code: "",
    label: "",
    date: "",
    position: ""
  })
  const [attendanceRecordForm, setAttendanceRecordForm] = useState({
    emails: "",
    part_id: "",
    status: "presente"
  })
  const [attendanceEventRecordForm, setAttendanceEventRecordForm] = useState({
    event_id: "",
    part_id: "",
    status: "presente",
    student_codes: []
  })
  const [attendanceEventStudents, setAttendanceEventStudents] = useState([])
  const [attendanceReportForm, setAttendanceReportForm] = useState({
    event_id: "",
    period: "week",
    reference_date: new Date().toISOString().slice(0, 10),
    start_date: "",
    end_date: ""
  })
  const [attendanceReport, setAttendanceReport] = useState(null)

  const [studentForm, setStudentForm] = useState({
    student_code: "",
    name: "",
    email: ""
  })

  const [courseForm, setCourseForm] = useState({
    title: "",
    course_code: "",
    file: null,
    event_id: "",
    color_primary: "#152A47"
  })

  const [enrollmentForm, setEnrollmentForm] = useState({
    student_code: "",
    course_code: ""
  })

  const [classes, setClasses] = useState([])
  const [classForm, setClassForm] = useState({name: ""})
  const [selectedClassId, setSelectedClassId] = useState("")
  const [selectedStudentCodes, setSelectedStudentCodes] = useState([])
  const [classStudents, setClassStudents] = useState([])

  const [eventForm, setEventForm] = useState({
    name: "",
    logo_url: "",
    slug: "",
    color_primary: "",
    color_secondary: "",
    item_name: "",
    show_progress: true,
    show_footer: false
  })

  const [selectedEventId, setSelectedEventId] = useState("")
  const [eventEditForm, setEventEditForm] = useState(null)
  const [eventLogoFile, setEventLogoFile] = useState(null)
  const [eventEmails, setEventEmails] = useState([])
  const [emailsInput, setEmailsInput] = useState("")

  async function loadData() {
    const studentsResponse = await fetch(`${API_URL}/students`)
    const studentsData = await studentsResponse.json()

    const coursesResponse = await fetch(`${API_URL}/courses`)
    const coursesData = await coursesResponse.json()

    const classesResponse = await fetch(`${API_URL}/classes`)
    const classesData = await classesResponse.json()

    const eventsResponse = await fetch(`${API_URL}/events`)
    const eventsData = await eventsResponse.json()

    const attendanceResponse = await fetch(`${API_URL}/attendance/modules`)
    const attendanceData = await attendanceResponse.json()

    setClasses(classesData)
    setStudents(studentsData)
    setCourses(coursesData)
    setEvents(eventsData)
    setAttendanceModules(attendanceData)
  }

  useEffect(() => {
    loadData()
  }, [])
  useEffect(() => {
    async function loadClassStudents() {
      if (!selectedClassId) {
        setClassStudents([])
        return
      }

      const response = await fetch(
        `${API_URL}/classes/${selectedClassId}/student-codes`
      )

      const data = await response.json()

      setClassStudents(data)
    }

    loadClassStudents()
  }, [selectedClassId])

  useEffect(() => {
    async function loadEventEmails() {
      if (!selectedEventId) {
        setEventEmails([])
        return
      }

      const response = await fetch(
        `${API_URL}/events/${selectedEventId}/emails`
      )

      const data = await response.json()
      setEventEmails(data)
    }

    loadEventEmails()
  }, [selectedEventId, API_URL])

  useEffect(() => {
    async function loadAttendanceEventStudents() {
      if (!attendanceEventRecordForm.event_id) {
        setAttendanceEventStudents([])
        return
      }

      const response = await fetch(
        `${API_URL}/events/${attendanceEventRecordForm.event_id}/emails`
      )
      const emails = await response.json()
      const allowedEmails = new Set(emails.map(item => item.email.toLowerCase()))

      setAttendanceEventStudents(
        students.filter(student => allowedEmails.has(student.email.toLowerCase()))
      )
    }

    loadAttendanceEventStudents()
  }, [attendanceEventRecordForm.event_id, students, API_URL])

  async function createStudent(e) {
    e.preventDefault()

    await fetch(`${API_URL}/students`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(studentForm)
    })

    setStudentForm({
      student_code: "",
      name: "",
      email: ""
    })

    loadData()
  }

  async function createCourse(e) {
    e.preventDefault()

    const formData = new FormData()

    formData.append("title", courseForm.title)
    formData.append("course_code", courseForm.course_code)
    formData.append("file", courseForm.file)

    if (courseForm.event_id) {
      formData.append("event_id", courseForm.event_id)
    }

    if (courseForm.color_primary) {
      formData.append("color_primary", courseForm.color_primary)
    }

    const response = await fetch(`${API_URL}/courses/upload`, {
        method: "POST",
        body: formData
    })

    const data = await response.json()

    if (data.success === false) {
        alert(data.message)
        return
    }

    alert("Curso cadastrado com sucesso!")

    setCourseForm({
        title: "",
        course_code: "",
        file: null,
        event_id: "",
        color_primary: "#152A47"
    })

    loadData()
    }

  async function deleteCourse(course) {
    const confirmed = window.confirm(
      `Tem certeza que quer excluir o curso "${course.title}"? Essa ação não pode ser desfeita e vai remover o acesso de todos os alunos matriculados.`
    )

    if (!confirmed) return

    const response = await fetch(`${API_URL}/courses/${course.course_code}`, {
      method: "DELETE"
    })

    const data = await response.json()

    if (!data.success) {
      alert(data.message || "Não foi possível excluir o curso.")
      return
    }

    if (data.ftp_warning) {
      alert(
        `Curso excluído do sistema, mas houve um problema ao remover os arquivos do servidor: ${data.ftp_warning}`
      )
    }

    loadData()
  }

  async function deleteStudent(student) {
    const confirmed = window.confirm(
      `Tem certeza que quer excluir o aluno "${student.name}"? Isso remove o acesso dele a todos os cursos e não pode ser desfeito.`
    )

    if (!confirmed) return

    const response = await fetch(`${API_URL}/students/${student.student_code}`, {
      method: "DELETE"
    })

    const data = await response.json()

    if (!data.success) {
      alert(data.message || "Não foi possível excluir o aluno.")
      return
    }

    loadData()
  }

  async function updateCourseEvent(course, eventId) {
    await fetch(`${API_URL}/courses/${course.course_code}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        event_id: eventId ? Number(eventId) : 0
      })
    })

    loadData()
  }

  async function createClass(e) {
    e.preventDefault()

    await fetch(`${API_URL}/classes`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(classForm)
    })

    setClassForm({ name: "" })
    loadData()
  }

  async function addStudentsToClass(e) {
    e.preventDefault()

    if (!selectedClassId) {
      alert("Selecione uma turma.")
      return
    }

    await fetch(`${API_URL}/classes/${selectedClassId}/students`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        student_codes: selectedStudentCodes
      })
    })

    alert("Alunos adicionados à turma!")
    setSelectedStudentCodes([])
  }  

  async function createEnrollment(e) {
    e.preventDefault()

    await fetch(`${API_URL}/enrollments`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(enrollmentForm)
    })

    setEnrollmentForm({
      student_code: "",
      course_code: ""
    })

    alert("Matrícula realizada!")
  }
  async function enrollClassInCourse(e) {
    e.preventDefault()

    const response = await fetch(
      `${API_URL}/classes/${selectedEnrollmentClass}/enroll`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          course_code: selectedEnrollmentCourse
        })
      }
    )

    const data = await response.json()

    alert(
      `Matrículas criadas: ${data.added}\nJá existentes: ${data.skipped}`
    )
  }

  async function createEvent(e) {
    e.preventDefault()

    if (!eventForm.name) {
      alert("Dá um nome pro evento.")
      return
    }

    await fetch(`${API_URL}/events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(eventForm)
    })

    setEventForm({
      name: "",
      logo_url: "",
      slug: "",
      color_primary: "",
      color_secondary: "",
      item_name: "",
      show_progress: true,
      show_footer: false
    })

    loadData()
  }

  async function deleteEvent(eventId) {
    const confirmed = window.confirm(
      "Excluir esse evento? Os cursos vinculados a ele voltam a ser públicos, mas não são excluídos."
    )

    if (!confirmed) return

    await fetch(`${API_URL}/events/${eventId}`, { method: "DELETE" })

    if (selectedEventId === String(eventId)) {
      setSelectedEventId("")
    }

    loadData()
  }

  async function addEmailsToEvent(e) {
    e.preventDefault()

    if (!selectedEventId) {
      alert("Selecione um evento primeiro.")
      return
    }

    const emails = emailsInput
      .split(/[\n,]/)
      .map(email => email.trim())
      .filter(Boolean)

    if (emails.length === 0) return

    await fetch(`${API_URL}/events/${selectedEventId}/emails`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ emails })
    })

    setEmailsInput("")

    const response = await fetch(
      `${API_URL}/events/${selectedEventId}/emails`
    )
    const data = await response.json()
    setEventEmails(data)
  }

  async function removeEmailFromEvent(email) {
    await fetch(
      `${API_URL}/events/${selectedEventId}/emails/${encodeURIComponent(email)}`,
      { method: "DELETE" }
    )

    setEventEmails(prev => prev.filter(e => e.email !== email))
  }

  function selectEventForEditing(event) {
    setSelectedEventId(String(event.id))
    setEventEditForm({
      name: event.name || "",
      slug: event.slug || "",
      logo_url: event.logo_url || "",
      color_primary: event.color_primary || "#152A47",
      color_secondary: event.color_secondary || "#EF4923",
      item_name: event.item_name || "",
      show_progress: event.show_progress !== false,
      show_footer: Boolean(event.show_footer)
    })
    setEventLogoFile(null)
  }

  async function saveEventChanges(e) {
    e.preventDefault()
    const response = await fetch(`${API_URL}/events/${selectedEventId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(eventEditForm)
    })
    const data = await response.json()
    if (!data.success) {
      alert(data.message || "Não foi possível salvar o evento.")
      return
    }
    await loadData()
    alert("Evento atualizado.")
  }

  async function uploadEventLogo(e) {
    e.preventDefault()
    if (!eventLogoFile) return
    const formData = new FormData()
    formData.append("file", eventLogoFile)
    const response = await fetch(`${API_URL}/events/${selectedEventId}/logo`, {
      method: "POST",
      body: formData
    })
    const data = await response.json()
    if (!data.success) {
      alert(data.message || "Não foi possível enviar a logo.")
      return
    }
    setEventEditForm({ ...eventEditForm, logo_url: data.logo_url })
    setEventLogoFile(null)
    await loadData()
  }

  async function createAttendanceModule(e) {
    e.preventDefault()
    if (!attendanceModuleForm.name.trim()) return

    await fetch(`${API_URL}/attendance/modules`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: attendanceModuleForm.name.trim(),
        event_id: attendanceModuleForm.event_id ? Number(attendanceModuleForm.event_id) : null,
        position: Number(attendanceModuleForm.position) || 0
      })
    })

    setAttendanceModuleForm({ name: "", event_id: "", position: "" })
    loadData()
  }

  async function createAttendancePart(e) {
    e.preventDefault()
    if (!attendancePartForm.module_id) {
      alert("Selecione o módulo da parte.")
      return
    }

    await fetch(`${API_URL}/attendance/modules/${attendancePartForm.module_id}/parts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        course_code: attendancePartForm.course_code || null,
        label: attendancePartForm.label.trim() || null,
        date: attendancePartForm.date || null,
        position: Number(attendancePartForm.position) || 0
      })
    })

    setAttendancePartForm({ module_id: attendancePartForm.module_id, course_code: "", label: "", date: "", position: "" })
    loadData()
  }

  async function editAttendanceModule(module) {
    const name = prompt("Nome do módulo:", module.name)
    if (!name?.trim()) return

    await fetch(`${API_URL}/attendance/modules/${module.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim() })
    })
    loadData()
  }

  async function deleteAttendanceModule(module) {
    if (!window.confirm(`Excluir "${module.name}" e todas as suas partes?`)) return
    await fetch(`${API_URL}/attendance/modules/${module.id}`, { method: "DELETE" })
    loadData()
  }

  async function editAttendancePart(part) {
    const label = prompt("Nome da parte:", part.label || "")
    if (label === null) return
    const date = prompt("Data (AAAA-MM-DD):", part.date || "")
    if (date === null) return

    await fetch(`${API_URL}/attendance/parts/${part.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: label.trim() || null, date: date || null })
    })
    loadData()
  }

  async function deleteAttendancePart(part) {
    if (!window.confirm(`Excluir a parte "${part.label}"?`)) return
    await fetch(`${API_URL}/attendance/parts/${part.id}`, { method: "DELETE" })
    loadData()
  }

  async function setManualAttendance(e) {
    e.preventDefault()
    if (!attendanceRecordForm.emails.trim() || !attendanceRecordForm.part_id) {
      alert("Informe pelo menos um e-mail e a parte da chamada.")
      return
    }

    const emails = attendanceRecordForm.emails
      .split(/[\n,]/)
      .map(email => email.trim().toLowerCase())
      .filter(Boolean)
    const studentByEmail = new Map(
      students.map(student => [student.email.toLowerCase(), student])
    )
    const missingEmails = emails.filter(email => !studentByEmail.has(email))
    const matchedStudents = [...new Map(
      emails.filter(email => studentByEmail.has(email)).map(email => [
        studentByEmail.get(email).student_code,
        studentByEmail.get(email)
      ])
    ).values()]

    if (matchedStudents.length === 0) {
      alert("Não encontramos alunos cadastrados para os e-mails informados.")
      return
    }

    const responses = await Promise.all(matchedStudents.map(student =>
      fetch(`${API_URL}/attendance/students/${student.student_code}/parts/${attendanceRecordForm.part_id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: attendanceRecordForm.status })
      })
    ))

    if (responses.some(response => !response.ok)) {
      alert("Algumas presenças não puderam ser registradas.")
      return
    }

    setAttendanceRecordForm({ emails: "", part_id: attendanceRecordForm.part_id, status: attendanceRecordForm.status })
    const missingNote = missingEmails.length ? ` E-mails não encontrados: ${missingEmails.join(", ")}.` : ""
    alert(`Presença registrada para ${matchedStudents.length} aluno(s).${missingNote}`)
  }

  async function setEventAttendance(e) {
    e.preventDefault()
    const { part_id, status, student_codes } = attendanceEventRecordForm
    if (!part_id || student_codes.length === 0) {
      alert("Selecione a parte e pelo menos um aluno do evento.")
      return
    }

    const responses = await Promise.all(student_codes.map(studentCode =>
      fetch(`${API_URL}/attendance/students/${studentCode}/parts/${part_id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status })
      })
    ))

    if (responses.some(response => !response.ok)) {
      alert("Algumas presenças não puderam ser registradas.")
      return
    }

    alert(`Presença registrada para ${student_codes.length} aluno(s).`)
  }

  function getReportRange() {
    if (attendanceReportForm.period === "custom") {
      return { start: attendanceReportForm.start_date, end: attendanceReportForm.end_date }
    }

    const date = new Date(`${attendanceReportForm.reference_date}T12:00:00`)
    if (attendanceReportForm.period === "month") {
      const start = new Date(date.getFullYear(), date.getMonth(), 1)
      const end = new Date(date.getFullYear(), date.getMonth() + 1, 0)
      return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) }
    }

    const day = date.getDay() || 7
    const start = new Date(date)
    start.setDate(date.getDate() - day + 1)
    const end = new Date(start)
    end.setDate(start.getDate() + 6)
    return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) }
  }

  async function loadAttendanceReport(e) {
    e.preventDefault()
    const range = getReportRange()
    const params = new URLSearchParams({ start_date: range.start, end_date: range.end })
    if (attendanceReportForm.event_id) params.set("event_id", attendanceReportForm.event_id)
    const response = await fetch(`${API_URL}/attendance/reports?${params}`)
    const data = await response.json()
    if (!data.success) {
      alert(data.message || "Não foi possível gerar o relatório.")
      return
    }
    setAttendanceReport(data)
  }

  function exportAttendanceReport() {
    if (!attendanceReport) return
    const headers = ["Aluno", "E-mail", "Frequência", "Presenças", "A realizar"]
    const rows = attendanceReport.students.map(student => [
      student.name, student.email, `${student.stats.frequencia ?? 0}%`, student.stats.presencas, student.stats.a_realizar
    ])
    const csv = [headers, ...rows].map(row => row.map(value => `"${String(value ?? "").replaceAll('"', '""')}"`).join(",")).join("\r\n")
    const link = document.createElement("a")
    link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8;" }))
    link.download = "relatorio-frequencia.csv"
    link.click()
    URL.revokeObjectURL(link.href)
  }

  function eventNameFor(eventId) {
    if (!eventId) return "Público"

    const event = events.find(e => e.id === eventId)
    return event ? event.name : "Público"
  }

  const attendanceParts = attendanceModules.flatMap(module =>
    module.parts.map(part => ({ ...part, moduleName: module.name }))
  )

  return (
    <div className="admin-page" style={{
      minHeight: "100vh",
      background: "#f4f6fb",
      padding: "28px 20px 48px",
      fontFamily: "Arial"
    }}>
      <style>{`
        .admin-page * { box-sizing: border-box; }
        .admin-page button { background: #152A47; color: #fff; border: 0; border-radius: 8px; padding: 10px 14px; font-weight: 700; cursor: pointer; }
        .admin-page button:hover { filter: brightness(1.12); }
        .admin-page button:disabled { opacity: .55; cursor: not-allowed; }
        .admin-page table { min-width: 620px; }
        .admin-page .admin-table-wrap { overflow-x: auto; }
        .admin-page h2 { color: #152A47; margin: 0 0 7px; font-size: 21px; }
        .admin-page h3 { color: #1e293b; }
        .admin-page a.admin-nav-link { color: #334155; text-decoration: none; background: #fff; border: 1px solid #dbe4ef; padding: 9px 12px; border-radius: 999px; font-size: 14px; font-weight: 700; }
        .admin-page a.admin-nav-link:hover { color: #fff; background: #152A47; border-color: #152A47; }
      `}</style>
      <main style={{ maxWidth: "1240px", margin: "0 auto" }}>
      <header style={{ background: "linear-gradient(120deg, #152A47, #23466e)", color: "#fff", borderRadius: "18px", padding: "24px", marginBottom: "16px", boxShadow: "0 10px 24px rgba(21,42,71,.18)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "16px", flexWrap: "wrap" }}>
          <div><span style={{ fontSize: "12px", fontWeight: 700, letterSpacing: "1.2px", opacity: .75 }}>GESTÃO DA PLATAFORMA</span><h1 style={{ margin: "5px 0 0", fontSize: "28px" }}>Painel Administrativo</h1><p style={{ margin: "7px 0 0", opacity: .82 }}>Cadastre, organize e acompanhe alunos, cursos, eventos e presença.</p></div>
          <button onClick={onBack} style={{ background: "#fff", color: "#152A47" }}>← Voltar ao painel</button>
        </div>
      </header>
      <nav style={{ display: "flex", gap: "8px", flexWrap: "wrap", margin: "0 0 20px" }}>
        <a className="admin-nav-link" href="#alunos">Alunos</a><a className="admin-nav-link" href="#cursos">Cursos</a><a className="admin-nav-link" href="#frequencia">Frequência</a><a className="admin-nav-link" href="#eventos">Eventos</a><a className="admin-nav-link" href="#turmas">Turmas e matrículas</a><a className="admin-nav-link" href="#cadastros">Listas cadastradas</a>
      </nav>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "12px", marginBottom: "-4px" }}>
        {[['Alunos', students.length], ['Cursos', courses.length], ['Eventos', events.length], ['Módulos de presença', attendanceModules.length]].map(([label, value]) => <div key={label} style={{ background: "#e9f0f8", borderRadius: "12px", padding: "14px 16px", border: "1px solid #d7e2ee" }}><strong style={{ display: "block", color: "#152A47", fontSize: "24px" }}>{value}</strong><span style={{ color: "#526579", fontSize: "13px" }}>{label}</span></div>)}
      </div>

      <div id="alunos" style={containerStyle}>
        <h2>Cadastrar aluno</h2>

        <form onSubmit={createStudent}>
          <input
            placeholder="Código"
            value={studentForm.student_code}
            onChange={e =>
              setStudentForm({
                ...studentForm,
                student_code: e.target.value
              })
            }
            style={inputStyle}
          />

          <input
            placeholder="Nome"
            value={studentForm.name}
            onChange={e =>
              setStudentForm({
                ...studentForm,
                name: e.target.value
              })
            }
            style={inputStyle}
          />

          <input
            placeholder="Email"
            value={studentForm.email}
            onChange={e =>
              setStudentForm({
                ...studentForm,
                email: e.target.value
              })
            }
            style={inputStyle}
          />

          <button type="submit">
            Criar aluno
          </button>
        </form>
      </div>

      <div style={containerStyle}>
        <h2>Cadastrar curso</h2>

        <form onSubmit={createCourse}>
          <input
            placeholder="Título"
            value={courseForm.title}
            onChange={e =>
              setCourseForm({
                ...courseForm,
                title: e.target.value
              })
            }
            style={inputStyle}
          />

          <input
            placeholder="Código"
            value={courseForm.course_code}
            onChange={e =>
              setCourseForm({
                ...courseForm,
                course_code: e.target.value
              })
            }
            style={inputStyle}
          />

          <select
            value={courseForm.event_id}
            onChange={e =>
              setCourseForm({
                ...courseForm,
                event_id: e.target.value
              })
            }
            style={inputStyle}
          >
            <option value="">Curso público (visível pra todo mundo)</option>

            {events.map(ev => (
              <option key={ev.id} value={ev.id}>
                Evento: {ev.name}
              </option>
            ))}
          </select>

          <label style={{ display: "block", marginBottom: "12px", color: "#374151" }}>
            Cor principal do curso
            <input
              type="color"
              value={courseForm.color_primary}
              onChange={e =>
                setCourseForm({ ...courseForm, color_primary: e.target.value })
              }
              style={{ display: "block", marginTop: "6px", height: "36px", width: "64px" }}
            />
          </label>

          <input
            type="file"
            accept=".zip"
            onChange={e =>
                setCourseForm({
                ...courseForm,
                file: e.target.files[0]
                })
            }
            style={inputStyle}
            />

          <button type="submit">
            Criar curso
          </button>
        </form>
      </div>

      <div id="cursos" style={containerStyle}>
        <h2>Chamada e frequência</h2>
        <p style={{ color: "#64748b", marginTop: "-8px" }}>
          Crie os módulos e as partes que aparecerão na carteira de frequência dos alunos.
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "24px", alignItems: "start" }}>
          <form onSubmit={createAttendanceModule} style={subsectionStyle}>
            <h3 style={subsectionTitle}>Novo módulo</h3>
            <input placeholder="Ex.: Módulo 1" value={attendanceModuleForm.name} onChange={e => setAttendanceModuleForm({ ...attendanceModuleForm, name: e.target.value })} style={inputStyle} />
            <select value={attendanceModuleForm.event_id} onChange={e => setAttendanceModuleForm({ ...attendanceModuleForm, event_id: e.target.value })} style={inputStyle}>
              <option value="">Disponível para todos</option>
              {events.map(event => <option key={event.id} value={event.id}>Evento: {event.name}</option>)}
            </select>
            <input type="number" min="0" placeholder="Ordem (opcional)" value={attendanceModuleForm.position} onChange={e => setAttendanceModuleForm({ ...attendanceModuleForm, position: e.target.value })} style={inputStyle} />
            <button type="submit" style={primaryButtonStyle}>Criar módulo</button>
          </form>

          <form onSubmit={createAttendancePart} style={subsectionStyle}>
            <h3 style={subsectionTitle}>Nova parte / aula</h3>
            <select value={attendancePartForm.module_id} onChange={e => setAttendancePartForm({ ...attendancePartForm, module_id: e.target.value })} style={inputStyle}>
              <option value="">Selecione o módulo</option>
              {attendanceModules.map(module => <option key={module.id} value={module.id}>{module.name}</option>)}
            </select>
            <select value={attendancePartForm.course_code} onChange={e => setAttendancePartForm({ ...attendancePartForm, course_code: e.target.value })} style={inputStyle}>
              <option value="">Curso vinculado (opcional)</option>
              {courses.map(course => <option key={course.id} value={course.course_code}>{course.title}</option>)}
            </select>
            <input placeholder="Nome da parte (ex.: Parte 1)" value={attendancePartForm.label} onChange={e => setAttendancePartForm({ ...attendancePartForm, label: e.target.value })} style={inputStyle} />
            <input type="date" value={attendancePartForm.date} onChange={e => setAttendancePartForm({ ...attendancePartForm, date: e.target.value })} style={inputStyle} />
            <input type="number" min="0" placeholder="Ordem (opcional)" value={attendancePartForm.position} onChange={e => setAttendancePartForm({ ...attendancePartForm, position: e.target.value })} style={inputStyle} />
            <button type="submit" style={primaryButtonStyle}>Adicionar parte</button>
          </form>
        </div>

        <h3 style={{ margin: "28px 0 12px", color: "#1e293b" }}>Registrar presença manualmente</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "24px", alignItems: "start" }}>
          <form onSubmit={setManualAttendance} style={subsectionStyle}>
            <h4 style={subsectionTitle}>Por e-mails</h4>
            <textarea placeholder="Cole os e-mails aqui, um por linha ou separados por vírgula" value={attendanceRecordForm.emails} onChange={e => setAttendanceRecordForm({ ...attendanceRecordForm, emails: e.target.value })} style={{ ...inputStyle, minHeight: "100px", resize: "vertical" }} />
            <select value={attendanceRecordForm.part_id} onChange={e => setAttendanceRecordForm({ ...attendanceRecordForm, part_id: e.target.value })} style={inputStyle}>
              <option value="">Selecione a parte / aula</option>
              {attendanceParts.map(part => <option key={part.id} value={part.id}>{part.moduleName} — {part.label || "Parte"} {part.date ? `(${part.date})` : ""}</option>)}
            </select>
            <select value={attendanceRecordForm.status} onChange={e => setAttendanceRecordForm({ ...attendanceRecordForm, status: e.target.value })} style={inputStyle}>
              <option value="presente">Presente</option><option value="falta">Falta</option><option value="justificada">Falta justificada</option><option value="a_realizar">A realizar</option>
            </select>
            <button type="submit" style={primaryButtonStyle}>Registrar e-mails</button>
          </form>

          <form onSubmit={setEventAttendance} style={subsectionStyle}>
            <h4 style={subsectionTitle}>Por alunos do evento</h4>
            <select value={attendanceEventRecordForm.event_id} onChange={e => setAttendanceEventRecordForm({ event_id: e.target.value, part_id: "", status: "presente", student_codes: [] })} style={inputStyle}>
              <option value="">Selecione o evento</option>
              {events.map(event => <option key={event.id} value={event.id}>{event.name}</option>)}
            </select>
            <select value={attendanceEventRecordForm.part_id} onChange={e => setAttendanceEventRecordForm({ ...attendanceEventRecordForm, part_id: e.target.value })} style={inputStyle}>
              <option value="">Selecione a parte / aula</option>
              {attendanceParts.filter(part => { const module = attendanceModules.find(item => item.id === part.module_id); return !module?.event_id || String(module.event_id) === attendanceEventRecordForm.event_id }).map(part => <option key={part.id} value={part.id}>{part.moduleName} — {part.label || "Parte"} {part.date ? `(${part.date})` : ""}</option>)}
            </select>
            <select value={attendanceEventRecordForm.status} onChange={e => setAttendanceEventRecordForm({ ...attendanceEventRecordForm, status: e.target.value })} style={inputStyle}>
              <option value="presente">Presente</option><option value="falta">Falta</option><option value="justificada">Falta justificada</option><option value="a_realizar">A realizar</option>
            </select>
            {attendanceEventRecordForm.event_id && <div style={{ maxHeight: "180px", overflowY: "auto", marginBottom: "12px", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "8px" }}>
              {attendanceEventStudents.length === 0 ? <span style={{ color: "#64748b", fontSize: "13px" }}>Nenhum aluno cadastrado para os e-mails deste evento.</span> : attendanceEventStudents.map(student => <label key={student.id} style={{ display: "block", padding: "5px" }}><input type="checkbox" checked={attendanceEventRecordForm.student_codes.includes(student.student_code)} onChange={e => setAttendanceEventRecordForm({ ...attendanceEventRecordForm, student_codes: e.target.checked ? [...attendanceEventRecordForm.student_codes, student.student_code] : attendanceEventRecordForm.student_codes.filter(code => code !== student.student_code) })} /> {student.name} <span style={{ color: "#64748b", fontSize: "12px" }}>({student.email})</span></label>)}
            </div>}
            <button type="submit" style={primaryButtonStyle}>Registrar selecionados</button>
          </form>
        </div>

        <div style={{ marginTop: "24px" }}>
          {attendanceModules.length === 0 ? <p style={{ color: "#64748b" }}>Nenhum módulo de chamada criado ainda.</p> : attendanceModules.map(module => (
            <div key={module.id} style={{ borderTop: "1px solid #e2e8f0", padding: "16px 0" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
                <div><strong>{module.name}</strong><span style={{ marginLeft: "8px", color: "#64748b", fontSize: "13px" }}>{eventNameFor(module.event_id)} · {module.parts.length} partes</span></div>
                <div><button onClick={() => editAttendanceModule(module)}>Editar módulo</button><button onClick={() => deleteAttendanceModule(module)} style={dangerButtonStyle}>Excluir módulo</button></div>
              </div>
              {module.parts.length > 0 && <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginTop: "12px" }}>{module.parts.map(part => <div key={part.id} style={{ padding: "8px 10px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "13px" }}><strong>{part.label}</strong>{part.date && <span style={{ color: "#64748b" }}> · {part.date}</span>}<button onClick={() => editAttendancePart(part)} style={{ marginLeft: "8px" }}>Editar</button><button onClick={() => deleteAttendancePart(part)} style={dangerButtonStyle}>×</button></div>)}</div>}
            </div>
          ))}
        </div>

        <div style={{ ...subsectionStyle, marginTop: "28px" }}>
          <h3 style={subsectionTitle}>Relatório de presença</h3>
          <form onSubmit={loadAttendanceReport} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "12px", alignItems: "end" }}>
            <label>Evento<select value={attendanceReportForm.event_id} onChange={e => setAttendanceReportForm({ ...attendanceReportForm, event_id: e.target.value })} style={inputStyle}><option value="">Todos os alunos</option>{events.map(event => <option key={event.id} value={event.id}>{event.name}</option>)}</select></label>
            <label>Período<select value={attendanceReportForm.period} onChange={e => setAttendanceReportForm({ ...attendanceReportForm, period: e.target.value })} style={inputStyle}><option value="week">Semanal</option><option value="month">Mensal</option><option value="custom">Personalizado</option></select></label>
            {attendanceReportForm.period === "custom" ? <><label>De<input type="date" value={attendanceReportForm.start_date} onChange={e => setAttendanceReportForm({ ...attendanceReportForm, start_date: e.target.value })} style={inputStyle} /></label><label>Até<input type="date" value={attendanceReportForm.end_date} onChange={e => setAttendanceReportForm({ ...attendanceReportForm, end_date: e.target.value })} style={inputStyle} /></label></> : <label>Data de referência<input type="date" value={attendanceReportForm.reference_date} onChange={e => setAttendanceReportForm({ ...attendanceReportForm, reference_date: e.target.value })} style={inputStyle} /></label>}
            <button type="submit" style={primaryButtonStyle}>Gerar relatório</button>
          </form>

          {attendanceReport && <div style={{ marginTop: "20px", overflowX: "auto" }}>
            <button type="button" onClick={exportAttendanceReport} style={primaryButtonStyle}>Exportar CSV</button>
            <table style={{ ...tableStyle, marginTop: "12px" }}><thead><tr><th style={th}>Aluno</th><th style={th}>E-mail</th><th style={th}>Frequência</th><th style={th}>Presenças</th><th style={th}>A realizar</th></tr></thead><tbody>{attendanceReport.students.map(student => <tr key={student.student_code}><td style={td}>{student.name}</td><td style={td}>{student.email}</td><td style={td}>{student.stats.frequencia ?? "—"}{student.stats.frequencia != null ? "%" : ""}</td><td style={td}>{student.stats.presencas}</td><td style={td}>{student.stats.a_realizar}</td></tr>)}</tbody></table>
          </div>}
        </div>
      </div>

      <div id="frequencia" style={containerStyle}>
        <h2>Eventos</h2>
        <p style={{ color: "#666", marginTop: "-8px" }}>
          Alunos com o email cadastrado num evento veem uma logo/cor diferente
          e só enxergam os cursos vinculados a esse evento.
        </p>

        <form onSubmit={createEvent}>
          <input
            placeholder="Nome do evento"
            value={eventForm.name}
            onChange={e =>
              setEventForm({ ...eventForm, name: e.target.value })
            }
            style={inputStyle}
          />

          <input
            placeholder="URL da logo (opcional)"
            value={eventForm.logo_url}
            onChange={e =>
              setEventForm({ ...eventForm, logo_url: e.target.value })
            }
            style={inputStyle}
          />

          <input
            placeholder="Endereço público (ex.: arctel)"
            value={eventForm.slug}
            onChange={e => setEventForm({ ...eventForm, slug: e.target.value })}
            style={inputStyle}
          />

          <div style={{ display: "flex", gap: "10px", marginBottom: "12px" }}>
            <label style={{ flex: 1 }}>
              Cor principal (fundo)
              <input
                type="color"
                value={eventForm.color_primary || "#152A47"}
                onChange={e =>
                  setEventForm({ ...eventForm, color_primary: e.target.value })
                }
                style={{ width: "100%", height: "40px" }}
              />
            </label>

            <label style={{ flex: 1 }}>
              Cor de destaque (botões)
              <input
                type="color"
                value={eventForm.color_secondary || "#EF4923"}
                onChange={e =>
                  setEventForm({ ...eventForm, color_secondary: e.target.value })
                }
                style={{ width: "100%", height: "40px" }}
              />
            </label>
          </div>

          <input
            placeholder='Nome no lugar de "Curso" (opcional, ex: Módulo)'
            value={eventForm.item_name}
            onChange={e =>
              setEventForm({ ...eventForm, item_name: e.target.value })
            }
            style={inputStyle}
          />

          <div style={{ display: "flex", gap: "20px", marginBottom: "12px" }}>
            <label>
              <input
                type="checkbox"
                checked={eventForm.show_progress}
                onChange={e =>
                  setEventForm({
                    ...eventForm,
                    show_progress: e.target.checked
                  })
                }
              />
              {" "}Mostrar barra de progresso nos cards
            </label>

            <label>
              <input
                type="checkbox"
                checked={eventForm.show_footer}
                onChange={e =>
                  setEventForm({
                    ...eventForm,
                    show_footer: e.target.checked
                  })
                }
              />
              {" "}Mostrar rodapé com logos de apoio (CCOM/RNP/UnB)
            </label>
          </div>

          <button type="submit">
            Criar evento
          </button>
        </form>

        {events.length > 0 && (
          <table style={{ ...tableStyle, marginTop: "20px" }}>
            <thead>
              <tr>
                <th style={th}>Nome</th>
                <th style={th}>Cores</th>
                <th style={th}>Ações</th>
              </tr>
            </thead>

            <tbody>
              {events.map(ev => (
                <tr key={ev.id}>
                  <td style={td}>{ev.name}</td>
                  <td style={td}>
                    <span
                      style={{
                        display: "inline-block",
                        width: "16px",
                        height: "16px",
                        borderRadius: "4px",
                        background: ev.color_primary || "#152A47",
                        marginRight: "6px"
                      }}
                    />
                    <span
                      style={{
                        display: "inline-block",
                        width: "16px",
                        height: "16px",
                        borderRadius: "4px",
                        background: ev.color_secondary || "#EF4923"
                      }}
                    />
                  </td>
                  <td style={td}>
                    <button onClick={() => selectEventForEditing(ev)}>
                      Editar evento
                    </button>
                    <button
                      onClick={() => deleteEvent(ev.id)}
                      style={{ marginLeft: "8px", color: "#b91c1c" }}
                    >
                      Excluir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {selectedEventId && (
          <div style={{ marginTop: "20px" }}>
            {eventEditForm && <>
              <h3>Configurações de "{eventEditForm.name}"</h3>
              <form onSubmit={saveEventChanges} style={subsectionStyle}>
                <input placeholder="Nome do evento" value={eventEditForm.name} onChange={e => setEventEditForm({ ...eventEditForm, name: e.target.value })} style={inputStyle} />
                <input placeholder="Endereço público (ex.: arctel)" value={eventEditForm.slug} onChange={e => setEventEditForm({ ...eventEditForm, slug: e.target.value })} style={inputStyle} />
                <input placeholder="URL da logo" value={eventEditForm.logo_url} onChange={e => setEventEditForm({ ...eventEditForm, logo_url: e.target.value })} style={inputStyle} />
                <div style={{ display: "flex", gap: "12px", marginBottom: "12px" }}>
                  <label style={{ flex: 1 }}>Cor principal<input type="color" value={eventEditForm.color_primary} onChange={e => setEventEditForm({ ...eventEditForm, color_primary: e.target.value })} style={{ display: "block", width: "100%", height: "36px" }} /></label>
                  <label style={{ flex: 1 }}>Cor secundária<input type="color" value={eventEditForm.color_secondary} onChange={e => setEventEditForm({ ...eventEditForm, color_secondary: e.target.value })} style={{ display: "block", width: "100%", height: "36px" }} /></label>
                </div>
                <button type="submit" style={primaryButtonStyle}>Salvar configurações</button>
              </form>
              <form onSubmit={uploadEventLogo} style={{ ...subsectionStyle, marginTop: "12px" }}>
                <strong>Enviar logo</strong>
                <p style={{ color: "#64748b", fontSize: "13px" }}>Aceita PNG, JPG, WEBP, SVG e ICO.</p>
                <input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml,image/x-icon,.ico" onChange={e => setEventLogoFile(e.target.files?.[0] || null)} style={inputStyle} />
                <button type="submit" style={primaryButtonStyle} disabled={!eventLogoFile}>Enviar logo</button>
              </form>
            </>}
            <h3>
              Emails de "{eventNameFor(Number(selectedEventId))}"
            </h3>

            <form onSubmit={addEmailsToEvent}>
              <textarea
                placeholder="Cole os emails aqui, um por linha (ou separados por vírgula)"
                value={emailsInput}
                onChange={e => setEmailsInput(e.target.value)}
                style={{ ...inputStyle, minHeight: "100px" }}
              />

              <button type="submit">
                Adicionar emails
              </button>
            </form>

            {eventEmails.length === 0 ? (
              <p>Nenhum email cadastrado nesse evento ainda.</p>
            ) : (
              <ul>
                {eventEmails.map(item => (
                  <li key={item.id}>
                    {item.email}
                    {" "}
                    <button
                      onClick={() => removeEmailFromEvent(item.email)}
                      style={{ color: "#b91c1c" }}
                    >
                      remover
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <div id="eventos" style={containerStyle}>
        <h2>Criar turma</h2>

        <form onSubmit={createClass}>
          <input
            placeholder="Nome da turma"
            value={classForm.name}
            onChange={e =>
              setClassForm({
                ...classForm,
                name: e.target.value
              })
            }
            style={inputStyle}
          />

          <button type="submit">
            Criar turma
          </button>
        </form>
      </div>

      <div id="turmas" style={containerStyle}>
        <h2>Adicionar alunos à turma</h2>

        <form onSubmit={addStudentsToClass}>
          <select
            value={selectedClassId}
            onChange={e => setSelectedClassId(e.target.value)}
            style={inputStyle}
          >
            <option value="">Selecione uma turma</option>

            {classes.map(classGroup => (
              <option key={classGroup.id} value={classGroup.id}>
                {classGroup.name}
              </option>
            ))}
          </select>

          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "10px",
            marginBottom: "16px",
            maxHeight: "380px",
            overflowY: "auto",
            paddingRight: "8px"
          }}>
            {students.map(student => {
              const alreadyInClass =
                classStudents.includes(student.student_code)

              return (
              
              <label
                key={student.id}
                style={{
                  background: "#f4f6fb",
                  padding: "10px",
                  borderRadius: "10px",
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "8px"
                }}
              >
                <input
                  
                  type="checkbox"
                  checked={selectedStudentCodes.includes(student.student_code)}
                  disabled={alreadyInClass}
                  onChange={e => {
                    if (e.target.checked) {
                      setSelectedStudentCodes([
                        ...selectedStudentCodes,
                        student.student_code
                      ])
                    } else {
                      setSelectedStudentCodes(
                        selectedStudentCodes.filter(
                          code => code !== student.student_code
                        )
                      )
                    }
                  }}
                />

                <span>
                  <strong style={{ display: "block" }}>{student.name}</strong>
                  <span style={{ display: "block", color: "#64748b", fontSize: "12px", marginTop: "3px" }}>
                    {student.email}
                  </span>
                  {alreadyInClass && (
                    <span style={{ color: "#15803d", fontSize: "12px" }}>
                      ✓ Já está na turma
                    </span>
                  )}
                </span>
              </label>
            )})}
          </div>

          <button type="submit">
            Adicionar selecionados
          </button>
        </form>
      </div>
      <div style={containerStyle}>
        <h2>Matricular turma em curso</h2>

        <form onSubmit={enrollClassInCourse}>

          <select
            value={selectedEnrollmentClass}
            onChange={e => setSelectedEnrollmentClass(e.target.value)}
            style={inputStyle}
          >
            <option value="">Selecione uma turma</option>

            {classes.map(classGroup => (
              <option key={classGroup.id} value={classGroup.id}>
                {classGroup.name}
              </option>
            ))}
          </select>

          <select
            value={selectedEnrollmentCourse}
            onChange={e => setSelectedEnrollmentCourse(e.target.value)}
            style={inputStyle}
          >
            <option value="">Selecione um curso</option>

            {courses.map(course => (
              <option
                key={course.id}
                value={course.course_code}
              >
                {course.title}
              </option>
            ))}
          </select>

          <button type="submit">
            Matricular turma
          </button>

        </form>
      </div>
      <div style={containerStyle}>
        <h2>Matricular aluno</h2>

        <form onSubmit={createEnrollment}>
          <select
            value={enrollmentForm.student_code}
            onChange={e =>
              setEnrollmentForm({
                ...enrollmentForm,
                student_code: e.target.value
              })
            }
            style={inputStyle}
          >
            <option value="">
              Selecione aluno
            </option>

            {students.map(student => (
              <option
                key={student.id}
                value={student.student_code}
              >
                {student.name}
              </option>
            ))}
          </select>

          <select
            value={enrollmentForm.course_code}
            onChange={e =>
              setEnrollmentForm({
                ...enrollmentForm,
                course_code: e.target.value
              })
            }
            style={inputStyle}
          >
            <option value="">
              Selecione curso
            </option>

            {courses.map(course => (
              <option
                key={course.id}
                value={course.course_code}
              >
                {course.title}
              </option>
            ))}
          </select>

          <button type="submit">
            Matricular
          </button>
        </form>
      </div>
        <div id="cadastros" style={containerStyle}>
          <h2>Alunos cadastrados</h2>

          {students.length === 0 ? (
            <p>Nenhum aluno cadastrado.</p>
          ) : (
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={th}>Código</th>
                  <th style={th}>Nome</th>
                  <th style={th}>Email</th>
                  <th style={th}>Ações</th>
                </tr>
              </thead>

              <tbody>
                {students.map(student => (
                  <tr key={student.id}>
                    <td style={td}>{student.student_code}</td>
                    <td style={td}>{student.name}</td>
                    <td style={td}>{student.email}</td>
                    <td style={td}>
                      <button
                        onClick={() => deleteStudent(student)}
                        style={{ color: "#b91c1c" }}
                      >
                        Excluir
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div style={containerStyle}>
          <h2>Cursos cadastrados</h2>

          {courses.length === 0 ? (
            <p>Nenhum curso cadastrado.</p>
          ) : (
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={th}>Código</th>
                  <th style={th}>Título</th>
                  <th style={th}>Status</th>
                  <th style={th}>Evento</th>
                  <th style={th}>Ações</th>
                  
                </tr>
              </thead>

              <tbody>
                {courses.map(course => (
                  <tr key={course.id}>
                    <td style={td}>{course.course_code}</td>
                    <td style={td}>{course.title}</td>
                    <td style={td}>{course.active ? "Ativo" : "Inativo"}</td>
                    <td style={td}>
                      <select
                        value={course.event_id || ""}
                        onChange={e => updateCourseEvent(course, e.target.value)}
                      >
                        <option value="">Público</option>

                        {events.map(ev => (
                          <option key={ev.id} value={ev.id}>
                            {ev.name}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td style={td}>
                      <button
                        onClick={async () => {
                          const newTitle = prompt("Novo título do curso:", course.title)

                          if (!newTitle) return

                          await fetch(`${API_URL}/courses/${course.course_code}`, {
                            method: "PUT",
                            headers: {
                              "Content-Type": "application/json"
                            },
                            body: JSON.stringify({
                              title: newTitle
                            })
                          })

                          loadData()
                        }}
                      >
                        Editar nome
                      </button>

                      <button
                        onClick={async () => {
                          await fetch(`${API_URL}/courses/${course.course_code}`, {
                            method: "PUT",
                            headers: {
                              "Content-Type": "application/json"
                            },
                            body: JSON.stringify({
                              active: !course.active
                            })
                          })

                          loadData()
                        }}
                        style={{ marginLeft: "8px" }}
                      >
                        {course.active ? "Desativar" : "Ativar"}
                      </button>

                      <button
                        onClick={() => deleteCourse(course)}
                        style={{ marginLeft: "8px", color: "#b91c1c" }}
                      >
                        Excluir
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
    </main>
    </div>
    
  )
}

const containerStyle = {
  background: "white",
  padding: "24px",
  borderRadius: "16px",
  marginTop: "24px",
  boxShadow: "0 4px 16px rgba(0,0,0,0.08)"
}

const inputStyle = {
  width: "100%",
  padding: "10px",
  marginBottom: "12px",
  borderRadius: "8px",
  border: "1px solid #cbd5e1",
  boxSizing: "border-box"
}

const subsectionStyle = {
  background: "#f8fafc",
  border: "1px solid #e2e8f0",
  borderRadius: "12px",
  padding: "18px"
}

const subsectionTitle = { marginTop: 0, fontSize: "16px", color: "#1e293b" }

const primaryButtonStyle = {
  background: "#152A47",
  color: "#fff",
  border: "none",
  borderRadius: "8px",
  padding: "10px 14px",
  cursor: "pointer",
  fontWeight: "bold"
}

const dangerButtonStyle = { marginLeft: "8px", color: "#b91c1c" }
const tableStyle = {
  width: "100%",
  borderCollapse: "collapse"
}

const th = {
  textAlign: "left",
  padding: "10px",
  borderBottom: "1px solid #ddd",
  color: "#555"
}

const td = {
  padding: "10px",
  borderBottom: "1px solid #eee"
}
export default AdminPage
