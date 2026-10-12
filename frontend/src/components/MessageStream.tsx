import { Collapse, Tag, Card } from 'antd'
import { useSessionStore } from '../stores/sessionStore'
import type { Message } from '../types/events'

function MessageItem({ msg }: { msg: Message }) {
  if (msg.kind === 'user') {
    return (
      <div style={{ textAlign: 'right', margin: '8px 0' }}>
        <Tag color="blue">你</Tag>
        <div style={{ display: 'inline-block', background: '#e6f4ff', padding: '8px 12px', borderRadius: 8, maxWidth: '70%', textAlign: 'left' }}>
          {msg.text}
        </div>
      </div>
    )
  }
  if (msg.kind === 'assistant') {
    return (
      <div style={{ margin: '8px 0' }}>
        <Tag color="green">Agent</Tag>
        {msg.thinking && (
          <Collapse
            ghost
            size="small"
            items={[{ key: '1', label: '思考过程', children: <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{msg.thinking}</pre> }]}
            style={{ marginBottom: 4 }}
          />
        )}
        <div style={{ background: '#f6ffed', padding: '8px 12px', borderRadius: 8, whiteSpace: 'pre-wrap' }}>
          {msg.text || <em style={{ color: '#999' }}>...</em>}
        </div>
      </div>
    )
  }
  if (msg.kind === 'tool_use') {
    const color = msg.status === 'running' ? 'processing' : msg.status === 'success' ? 'success' : 'error'
    return (
      <Card size="small" style={{ margin: '8px 0', background: '#fafafa' }}>
        <div>
          <Tag color={color}>🔧 {msg.name}</Tag>
          <span style={{ color: '#999', fontSize: 12 }}>{msg.status}</span>
        </div>
        <pre style={{ fontSize: 11, margin: '4px 0', whiteSpace: 'pre-wrap' }}>
          {JSON.stringify(msg.input, null, 2)}
        </pre>
        {msg.result && (
          <pre style={{ fontSize: 11, margin: '4px 0', color: '#666', whiteSpace: 'pre-wrap' }}>
            {msg.result}
          </pre>
        )}
      </Card>
    )
  }
  return <div style={{ color: 'red', margin: '8px 0' }}>⚠ {msg.message}</div>
}

export function MessageStream() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId)
  const messages = useSessionStore((s) =>
    (activeSessionId && s.messagesBySession[activeSessionId]) || EMPTY
  )
  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
      {messages.map((m) => <MessageItem key={m.id} msg={m} />)}
    </div>
  )
}

const EMPTY: Message[] = []
