import { useState } from 'react'
import { Input, Button, message } from 'antd'
import { useSessionStore } from '../stores/sessionStore'
import { UploadZone } from './UploadZone'
import * as api from '../api/sessions'

const SCENARIO_COMMANDS: Record<string, string> = {
  '/jd': 'jd',
  '/screen': 'screen',
  '/interview': 'interview',
  '/policy': 'policy',
}

export function ChatInput({ sessionId }: { sessionId: string }) {
  const [value, setValue] = useState('')
  const { addMessage, setStatus } = useSessionStore()

  const send = async () => {
    const text = value.trim()
    if (!text) return

    const [first, ...rest] = text.split(/\s+/)
    const scenario = SCENARIO_COMMANDS[first]
    let actualContent = text

    if (scenario) {
      addMessage({ kind: 'user', id: 'u_' + Date.now(), text })
      setValue('')
      try {
        await api.patchSession(sessionId, { scenario })
        useSessionStore.getState().setSessionScenario(sessionId, scenario)
        const label = (useSessionStore.getState().scenarios.find((s) => s.key === scenario)?.label) ?? scenario
        message.success(`已切换到「${label}」`)
      } catch (e: any) {
        message.error('切换场景失败: ' + e.message)
        return
      }
      actualContent = rest.join(' ').trim()
      if (!actualContent) {
        addMessage({
          kind: 'assistant',
          id: 'sys_' + Date.now(),
          text: '已进入该场景模式，请描述你的需求。',
          thinking: '',
        })
        return
      }
    } else {
      addMessage({ kind: 'user', id: 'u_' + Date.now(), text })
      setValue('')
    }

    setStatus('thinking')
    await fetch(`/api/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: actualContent }),
    })
  }

  const handleUploaded = async (path: string) => {
    const text = `请解析刚上传的简历：${path}`
    addMessage({ kind: 'user', id: 'u_' + Date.now(), text })
    setStatus('thinking')
    await fetch(`/api/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: text }),
    })
  }

  return (
    <div style={{ borderTop: '1px solid #eee' }}>
      <details style={{ padding: '8px 12px 0' }}>
        <summary style={{ cursor: 'pointer', fontSize: 12, color: '#888' }}>
          上传简历
        </summary>
        <div style={{ marginTop: 8 }}>
          <UploadZone sessionId={sessionId} onUploaded={handleUploaded} />
        </div>
      </details>
      <div style={{ display: 'flex', gap: 8, padding: 12 }}>
        <Input.TextArea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onPressEnter={(e) => {
            if (!e.shiftKey) { e.preventDefault(); send() }
          }}
          autoSize={{ minRows: 1, maxRows: 5 }}
          placeholder="输入消息，Enter 发送，Shift+Enter 换行。试试 /jd /screen /interview /policy"
        />
        <Button type="primary" onClick={send}>发送</Button>
      </div>
    </div>
  )
}
