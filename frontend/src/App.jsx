import { useState } from 'react'
import ChatWindow from './components/ChatWindow'
import MessageInput from './components/MessageInput'
import { sendMessage } from './services/api'
import './App.css'

export default function App() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)

  function addMessage(role, content) {
    const ts = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    setMessages((prev) => [...prev, { role, content, timestamp: ts }])
  }

  async function handleSend(text) {
    addMessage('user', text)
    setIsLoading(true)
    try {
      const history = messages.map(({ role, content }) => ({ role, content }))
      const result = await sendMessage(text, 'help', history)
      addMessage('assistant', result.response)
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Unknown error'
      addMessage('assistant', `⚠️ Error: ${detail}`)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="app-layout">
      <div className="main-panel">
        <header className="header">
          <div className="header-left">
            <h1 className="header-title">📖 Help Assistant</h1>
            <span className="header-sub">Get answers from Veeva documentation and best practices</span>
          </div>
          <button className="clear-btn" onClick={() => setMessages([])} title="Clear chat">🗑 Clear</button>
        </header>
        <ChatWindow messages={messages} isLoading={isLoading} mode="help" />
        <MessageInput onSend={handleSend} isLoading={isLoading} mode="help" />
      </div>
    </div>
  )
}
