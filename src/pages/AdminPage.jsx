import { useEffect, useState } from 'react'

function AdminPage({ API_URL, onBack }) {
  const [students, setStudents] = useState([])
  const [courses, setCourses] = useState([])

  const [studentForm, setStudentForm] = useState({
    student_code: "",
    name: "",
    email: ""
  })

  const [courseForm, setCourseForm] = useState({
    title: "",
    course_code: "",
    file: null
  })

  const [enrollmentForm, setEnrollmentForm] = useState({
    student_code: "",
    course_code: ""
  })

  async function loadData() {
    const studentsResponse = await fetch(`${API_URL}/students`)
    const studentsData = await studentsResponse.json()

    const coursesResponse = await fetch(`${API_URL}/courses`)
    const coursesData = await coursesResponse.json()

    setStudents(studentsData)
    setCourses(coursesData)
  }

  useEffect(() => {
    loadData()
  }, [])

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
        file: null
    })

    loadData()
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

export default AdminPage