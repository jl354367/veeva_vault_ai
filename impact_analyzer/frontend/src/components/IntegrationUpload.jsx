import { useRef, useState } from 'react'
import axios from 'axios'

export default function IntegrationUpload({ onUploadComplete }) {
  const inputRef = useRef(null)
  const [status, setStatus]     = useState(null)
  const [filename, setFilename] = useState('')

  async function handleFile(file) {
    if (!file) return
    setFilename(file.name)
    setStatus('uploading')
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await axios.post('/api/upload-integration', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setStatus('done')
      onUploadComplete(res.data.message, true, res.data.sheet_stats || [])
    } catch (err) {
      setStatus('error')
      const detail = err.response?.data?.detail || err.message || 'Unknown error'
      onUploadComplete(`⚠️ Upload failed: ${detail}`, false)
    }
  }

  return (
    <div
      className={`file-upload-zone ${status === 'uploading' ? 'uploading' : ''}`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => { e.preventDefault(); handleFile(e.dataTransfer.files[0]) }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".xlsx,.xls,.csv,.pdf,.docx,.txt,.json"
        style={{ display: 'none' }}
        onChange={(e) => handleFile(e.target.files[0])}
      />
      {status === 'uploading' && <span className="upload-spinner" />}
      {status === 'done'      && <span className="upload-icon-done">✓</span>}
      {!status                && <span className="upload-icon">🔌</span>}
      <span className="upload-label">
        {status === 'uploading' ? `Uploading ${filename}…` :
         status === 'done'      ? filename :
         'Upload Integration Spec (.xlsx / .pdf / .csv / .docx)'}
      </span>
    </div>
  )
}
