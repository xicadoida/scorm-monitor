import { useEffect, useState } from 'react'

function AdminPage({ API_URL, onBack }) {
  const [selectedEnrollmentClass, setSelectedEnrollmentClass] = useState("")
  const [selectedEnrollmentCourse, setSelectedEnrollmentCourse] = useState("")
  const [students, setStudents] = useState([])
  const [courses, setCourses] = useState([])
  const [events, setEvents] = useState([])

  const [studentForm, setStudentForm] = useState({
    student_code: "",
    name: "",
    email: ""
  })

  const [courseForm, setCourseForm] = useState({
    title: "",
    course_code: "",
    file: null,
    event_id: ""
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
    color_primary: "",
    color_secondary: "",
    item_name: "",
    show_progress: true,
    show_footer: false
  })

  const [selectedEventId, setSelectedEventId] = useState("")
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

    setClasses(classesData)
    setStudents(studentsData)
    setCourses(coursesData)
    setEvents(eventsData)
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
        event_id: ""
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

  function eventNameFor(eventId) {
    if (!eventId) return "Público"

    const event = events.find(e => e.id === eventId)
    return event ? event.name : "Público"
  }

  return (
    <div style={{
      minHeight: "100vh",
      background: "#f4f6fb",
      padding: "32px",
      fontFamily: "Arial"
    }}>
      <button onClick={onBack}>
        Voltar
      </button>

      <h1>Painel Administrativo</h1>

      <div style={containerStyle}>
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

      <div style={containerStyle}>
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
                    <button onClick={() => setSelectedEventId(String(ev.id))}>
                      Gerenciar emails
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

      <div style={containerStyle}>
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

      <div style={containerStyle}>
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
            marginBottom: "16px"
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
                  borderRadius: "10px"
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

                {" "}
                {student.name}

                {alreadyInClass && (
                  <span
                    style={{
                      color: "green",
                      marginLeft: "8px"
                    }}
                  >
                    ✓ Já está na turma
                  </span>
                )}
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
        <div style={containerStyle}>
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
                </tr>
              </thead>

              <tbody>
                {students.map(student => (
                  <tr key={student.id}>
                    <td style={td}>{student.student_code}</td>
                    <td style={td}>{student.name}</td>
                    <td style={td}>{student.email}</td>
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
      </div>
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
  marginBottom: "12px"
}
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