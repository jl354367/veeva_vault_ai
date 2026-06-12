import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user'

  // Strip invisible NAV state comments before rendering
  const content = message.content?.replace(/<!--NAV:.*?-->/gs, '').trim() || ''

  return (
    <div className={`bubble-row ${isUser ? 'user-row' : 'bot-row'}`}>
      {!isUser && (
        <div className="avatar bot-avatar" title="VaultBot">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <rect x="3" y="3" width="18" height="18" rx="4" fill="white" fillOpacity="0.9"/>
            <path d="M8 12h8M12 8v8" stroke="#0052a3" strokeWidth="2" strokeLinecap="round"/>
          </svg>
        </div>
      )}
      <div className={`bubble ${isUser ? 'user-bubble' : 'bot-bubble'}`}>
        {message.role === 'system' ? (
          <p className="system-msg">{content}</p>
        ) : isUser ? (
          <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.65 }}>{content}</p>
        ) : (
          <div className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>{content}</ReactMarkdown>
          </div>
        )}
        {message.timestamp && (
          <span className="timestamp">{message.timestamp}</span>
        )}
      </div>
      {isUser && (
        <div className="avatar user-avatar" title="You">U</div>
      )}
    </div>
  )
}
