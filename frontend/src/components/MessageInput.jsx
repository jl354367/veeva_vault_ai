import { useState, useRef } from 'react'
import FileUpload from './FileUpload'

export default function MessageInput({ onSend, onUploadComplete, isLoading, mode, resetKey }) {
  const [text, setText] = useState('')
  const textareaRef = useRef(null)

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function handleChange(e) {
    setText(e.target.value)
    // Auto-resize like ChatGPT / Copilot
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }

  function submit() {
    const trimmed = text.trim()
    if (!trimmed || isLoading) return
    onSend(trimmed)
    setText('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.focus()
    }
  }

  return (
    <div className="input-area">
      {mode === 'config' && (
        <div className="upload-row">
          <FileUpload key={resetKey} onUploadComplete={onUploadComplete} />
        </div>
      )}
      <div className="input-bar">
        <textarea
          ref={textareaRef}
          className="message-input"
          placeholder={
            mode === 'config' ? 'Ask about lifecycles, roles, workflows…' :
                                'Ask any Veeva Vault question…'
          }
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          rows={1}
          style={{ resize: 'none', overflow: 'hidden' }}
          disabled={isLoading}
        />
        <button
          className="send-btn"
          onClick={submit}
          disabled={!text.trim() || isLoading}
          aria-label="Send"
        >
          {isLoading ? (
            <span className="send-spinner" />
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M22 2L11 13" stroke="white" strokeWidth="2" strokeLinecap="round"/>
              <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="white" strokeWidth="2"
                strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
        </button>
      </div>
      <p className="input-hint">Press Enter to send · Shift+Enter for new line</p>
    </div>
  )
}
