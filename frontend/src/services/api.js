import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export async function sendMessage(message, mode, history) {
  const { data } = await api.post('/chat', { message, mode, history })
  return data
}

export async function uploadFile(file, purpose = 'config') {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post(`/upload?purpose=${purpose}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

