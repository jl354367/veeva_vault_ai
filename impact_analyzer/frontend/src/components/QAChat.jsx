import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { askQuestion } from '../services/api'

export default function QAChat({ bedrockConfigured }) {
  const [messages, setMessages]   = useState([])
  const [input, setInput]         = useState('')
  const [loading, setLoading]     = useState(false)
  const bottomRef                 = useRef(null)
  const inputRef                  = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send() {
    const text = input.trim()
    if (!text || loading) return

    const userMsg = { role: 'user', content: text }
    const next    = [...messages, userMsg]
    setMessages(next)
    setInput('')
    setLoading(true)

    try {
      const res = await askQuestion(text, next)
      setMessages([...next, { role: 'assistant', content: res.response }])
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Unknown error'
      setMessages([...next, { role: 'assistant', content: `⚠️ ${detail}` }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="qa-root">
      <div className="qa-header">
        <span>💬</span>
        <strong>Ask About This Report</strong>
        {!bedrockConfigured && (
          <span className="qa-hint">Keyword mode — connect Bedrock for full AI answers</span>
        )}
        {messages.length > 0 && (
          <button className="qa-clear" onClick={() => setMessages([])}>Clear</button>
        )}
      </div>

      <div className="qa-messages">
        {messages.length === 0 && (
          <div className="qa-empty">
            <p>Ask any question about the analysis results:</p>
            <div className="qa-suggestions">
              {[
                'Which integrations are at highest risk?',
                'What should I do before the upgrade?',
                'Explain the critical items in plain English',
                'What is the estimated effort to fix everything?',
              ].map((s) => (
                <button key={s} className="qa-suggestion" onClick={() => { setInput(s); inputRef.current?.focus() }}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`qa-msg qa-msg-${msg.role}`}>
            <span className="qa-msg-label">{msg.role === 'user' ? 'You' : 'VaultBot'}</span>
            <div className="qa-msg-body markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                {msg.content}
              </ReactMarkdown>
            </div>
          </div>
        ))}

        {loading && (
          <div className="qa-msg qa-msg-assistant">
            <span className="qa-msg-label">VaultBot</span>
            <div className="qa-msg-body qa-typing">
              <span /><span /><span />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="qa-input-row">
        <textarea
          ref={inputRef}
          className="qa-input"
          rows={1}
          placeholder="Ask about the impact report or integrations…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          disabled={loading}
        />
        <button className="qa-send" onClick={send} disabled={!input.trim() || loading}>
          {loading ? <span className="upload-spinner" /> : '↑'}
        </button>
      </div>
    </div>
  )
}
