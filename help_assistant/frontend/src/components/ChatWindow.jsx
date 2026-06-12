import { useEffect, useRef } from 'react'
import MessageBubble from './MessageBubble'

function TypingIndicator() {
  return (
    <div className="bubble-row bot-row">
      <div className="avatar bot-avatar">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
          <rect x="3" y="3" width="18" height="18" rx="4" fill="white" fillOpacity="0.9"/>
          <path d="M8 12h8M12 8v8" stroke="#0052a3" strokeWidth="2" strokeLinecap="round"/>
        </svg>
      </div>
      <div className="bubble bot-bubble typing-bubble">
        <span className="dot" /><span className="dot" /><span className="dot" />
      </div>
    </div>
  )
}

const WELCOME = {
  config: { title: 'Config Analyst Mode', sub: 'Upload a Config Report and ask about lifecycles, roles, workflows, and more.' },
  help:   { title: 'Help Assistant Mode', sub: 'Ask any Veeva Vault question — answered from the built-in knowledge base.' },
}

export default function ChatWindow({ messages, isLoading, mode }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const welcome = WELCOME[mode] || WELCOME['help']

  return (
    <div className="chat-window">
      {messages.length === 0 && (
        <div className="welcome-screen">
          <div className="welcome-icon">🤖</div>
          <h2>{welcome.title}</h2>
          <p className="welcome-sub">{welcome.sub}</p>
        </div>
      )}

      {messages.map((msg, i) => (
        <MessageBubble key={i} message={msg} />
      ))}

      {isLoading && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  )
}
