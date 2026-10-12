import { Collapse, Tag, Card, Spin, Progress } from 'antd'
import { useSessionStore } from '../stores/sessionStore'
import type { Message } from '../types/events'

function BatchItem({ msg }: { msg: Extract<Message, { kind: 'batch' }> }) {
  const s = msg.state
  const pct = s.total > 0 ? Math.floor((s.completed / s.total) * 100) : 0
  const tagColor = s.status === 'done' ? 'green' : s.status === 'failed' ? 'red' : 'blue'
  const tagLabel =
    s.status === 'running' ? '批量评估中'
    : s.status === 'done' ? '批量评估完成'
    : '批量评估失败'
  return (
    <Card size="small" style={{ margin: '8px 0' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <Tag color={tagColor}>{tagLabel}</Tag>
        <span style={{ color: '#666', fontSize: 12 }}>
          {s.completed} / {s.total}
          {s.current && s.status === 'running' && ` · 正在处理 ${s.current}`}
        </span>
      </div>
      <Progress
        percent={pct}
        size="small"
        status={s.status === 'running' ? 'active' : s.status === 'failed' ? 'exception' : undefined}
        strokeColor={s.status === 'done' ? '#52c41a' : undefined}
      />
      {s.errors.length > 0 && (
        <div style={{ marginTop: 8, fontSize: 12 }}>
          {s.errors.map((e, i) => (
            <div key={i} style={{ color: '#cf1322' }}>❌ {e.file}: {e.message}</div>
          ))}
        </div>
      )}
      {s.status === 'done' && (
        <div style={{ marginTop: 8, fontSize: 12 }}>
          成功 {s.okCount ?? 0} 份，失败 {s.failedCount ?? 0} 份
          {s.summaryPath && (
            <>
              {' · '}
              <a
                onClick={() => {
                  window.dispatchEvent(new CustomEvent('open-file', { detail: s.summaryPath }))
                }}
              >
                查看汇总
              </a>
            </>
          )}
        </div>
      )}
    </Card>
  )
}

function MessageItem({ msg }: { msg: Message }) {
  if (msg.kind === 'pending') {
    return (
      <div style={{ margin: '8px 0', color: '#999', fontStyle: 'italic' }}>
        <Spin size="small" /> 处理中…
      </div>
    )
  }
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
  if (msg.kind === 'batch') {
    return <BatchItem msg={msg} />
  }
  return <div style={{ color: 'red', margin: '8px 0' }}>⚠ {msg.message}</div>
}

export function MessageStream() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId)
  const messages = useSessionStore((s) =>
    (activeSessionId && s.messagesBySession[activeSessionId]) || EMPTY
  )
  return (
    <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: 12 }}>
      {messages.map((m) => <MessageItem key={m.id} msg={m} />)}
    </div>
  )
}

const EMPTY: Message[] = []
