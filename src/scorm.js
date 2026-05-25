import { Scorm12API } from 'scorm-again'

const api = new Scorm12API({

  lmsInitialize() {
    console.log("SCORM iniciado")
    return "true"
  },

  lmsSetValue(key, value) {

    console.log("SET:", key, value)

    return "true"
  },

  lmsCommit() {
    console.log("Commit")
    return "true"
  },

  lmsFinish() {
    console.log("Finalizado")
    return "true"
  }
})

window.API = api
window.API_1484_11 = api

window.parent.API = api
window.parent.API_1484_11 = api

window.top.API = api
window.top.API_1484_11 = api
