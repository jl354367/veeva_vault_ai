import { useRef, useState } from 'react'
import { uploadFile } from '../services/api'

export default function FileUpload({ onUploadComplete, purpose = 'config' }) {
  const inputRef = useRef(null)
  const [status, setStatus] = useState(null) // null | 'uploading' | 'done' | 'error'
  const [filename, setFilename] = useState('')

  async function handleFile(file) {
    if (!file) return
    setFilename(file.name)
    setStatus('uploading')
    try {
      const result = await uploadFile(file, purpose)
      setStatus('done')
      onUploadComplete(result.message, true, result.sheet_stats || [])   // true = success
    } catch (err) {
      setStatus('error')
      const detail = err.response?.data?.detail || err.message || 'Unknown error'
      onUploadComplete(`⚠️ Upload failed: ${detail}`, false)  // false = failure
    }
  }

  function handleDrop(e) {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    handleFile(file)
  }

  return (
    <div
      className={`file-upload-zone ${status === 'uploading' ? 'uploading' : ''}`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".xlsx,.xls,.csv,.pdf,.docx,.txt,.json"
        style={{ display: 'none' }}
        onChange={(e) => handleFile(e.target.files[0])}
      />
      {status === 'uploading' && <span className="upload-spinner" />}
      {status === 'done' && <span className="upload-icon-done">✓</span>}
      {!status && <span className="upload-icon">📎</span>}
      <span className="upload-label">
        {status === 'uploading' ? `Uploading ${filename}…` :
         status === 'done' ? filename :
         'Upload Config Report (.xlsx / .pdf / .csv / .docx)'}
      </span>
    </div>
  )
}
