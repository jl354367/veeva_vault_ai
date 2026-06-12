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

export async function clearUpload(purpose = 'config') {
  const { data } = await api.delete(`/upload?purpose=${purpose}`)
  return data
}

export async function getBedrockStatus() {
  try {
    const { data } = await axios.get('/api/bedrock-status')
    return data
  } catch {
    return { configured: false }
  }
}

export async function analyzeIntegration() {
  const { data } = await api.post('/analyze-integration')
  return data
}

export async function askQuestion(message, history = []) {
  const { data } = await api.post('/ask', { message, mode: 'qa', history })
  return data
}

export async function clearIntegration() {
  const { data } = await api.delete('/upload-integration')
  return data
}
