import { useEffect, useState, type ReactNode } from 'react'
import { Layout, Tag, Select, message } from 'antd'
import { useSessionStore } from './stores/sessionStore'

const SESSION_COST_LIMIT_USD = 5.0
import { useSSE } from './hooks/useSSE'
import { useHistory } from './hooks/useHistory'
import { useApprovalSync } from './hooks/useApprovalSync'
import { MessageStream } from './components/MessageStream'
import { ChatInput } from './components/ChatInput'
import { ApprovalPanel } from './components/ApprovalPanel'
import { FileTree } from './components/FileTree'
import { FilePreview } from './components/FilePreview'
import { SessionList } from './components/SessionList'
import * as api from './api/sessions'

type TabKey = 'chat' | 'files'

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '12px 16px',
        background: 'none',
        border: 'none',
        borderBottom: active ? '2px solid #1890ff' : '2px solid transparent',
        marginBottom: '-1px',
        color: active ? '#1890ff' : '#666',
        cursor: 'pointer',
        fontSize: 14,
        fontWeight: active ? 500 : 400,
      }}
    >
      {children}
    </button>
  )
}

function App() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId)
  const sessions = useSessionStore((s) => s.sessions)
  const scenarios = useSessionStore((s) => s.scenarios)
  const setScenarios = useSessionStore((s) => s.setScenarios)
  const setSessionScenario = useSessionStore((s) => s.setSessionScenario)
  const agentStatus = useSessionStore((s) => s.agentStatus)
  const sseConnected = useSessionStore((s) => s.sseConnected)
  const sessionCost = useSessionStore((s) =>
    s.activeSessionId ? (s.sessionCostBySession[s.activeSessionId] ?? 0) : 0
  )
  const doneCounter = useSessionStore((s) => s.doneCounter)
  const [fileRefreshKey, setFileRefreshKey] = useState(0)
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabKey>('chat')

  useSSE(activeSessionId ?? '')
  useHistory(activeSessionId)
  useApprovalSync(activeSessionId)

  useEffect(() => {
    setFileRefreshKey((k) => k + 1)
  }, [doneCounter])

  useEffect(() => {
    if (scenarios.length === 0) {
      api.listScenarios().then(setScenarios).catch(() => {})
    }
  }, [scenarios.length, setScenarios])

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<string>).detail
      if (typeof detail === 'string' && detail) {
        setSelectedFile(detail)
        setActiveTab('files')
      }
    }
    window.addEventListener('open-file', handler)
    return () => window.removeEventListener('open-file', handler)
  }, [])

  const activeMeta = sessions.find((x) => x.id === activeSessionId)

  const handleScenarioChange = async (v: string) => {
    if (!activeMeta) return
    try {
      await api.patchSession(activeMeta.id, { scenario: v })
      setSessionScenario(activeMeta.id, v)
      const label = scenarios.find((s) => s.key === v)?.label ?? v
      message.success(`已切换到「${label}」`)
    } catch (e: any) {
      message.error('切换场景失败: ' + e.message)
    }
  }

  return (
    <Layout style={{ height: '100vh', overflow: 'hidden' }}>
      <Layout.Header style={{ background: '#fff', borderBottom: '1px solid #eee', display: 'flex', alignItems: 'center', gap: 12, flex: '0 0 auto' }}>
        <strong>HR Recruit Agent</strong>
        <Tag color={sseConnected ? 'green' : 'red'}>SSE {sseConnected ? '在线' : '离线'}</Tag>
        <Tag>{agentStatus}</Tag>
        <Tag>session: {activeSessionId ?? '-'}</Tag>
        {activeSessionId && (
          <Tag color={sessionCost > SESSION_COST_LIMIT_USD * 0.8 ? 'orange' : 'default'}>
            成本 ${sessionCost.toFixed(2)} / ${SESSION_COST_LIMIT_USD.toFixed(2)}
          </Tag>
        )}
        {activeMeta && (
          <Select
            size="small"
            value={activeMeta.scenario}
            onChange={handleScenarioChange}
            style={{ width: 200 }}
            options={scenarios.map((s) => ({ value: s.key, label: s.label }))}
          />
        )}
      </Layout.Header>
      <Layout style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <Layout.Sider
          width={240}
          style={{ background: '#fafafa', borderRight: '1px solid #eee', height: '100%', overflow: 'auto' }}
        >
          <div style={{ padding: 12 }}>
            <SessionList />
          </div>
        </Layout.Sider>
        <Layout.Content style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', borderBottom: '1px solid #eee', padding: '0 16px', flex: '0 0 auto' }}>
            <TabButton active={activeTab === 'chat'} onClick={() => setActiveTab('chat')}>对话</TabButton>
            <TabButton active={activeTab === 'files'} onClick={() => setActiveTab('files')}>文件</TabButton>
          </div>
          <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            {activeTab === 'chat' && (
              activeSessionId ? (
                <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflow: 'hidden' }}>
                  <MessageStream />
                  <ChatInput sessionId={activeSessionId} />
                </div>
              ) : (
                <div style={{ padding: 20, color: '#999' }}>请先创建一个会话</div>
              )
            )}
            {activeTab === 'files' && (
              activeSessionId ? (
                <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
                  <div style={{ width: 240, borderRight: '1px solid #eee', height: '100%', overflowY: 'auto', padding: 12, boxSizing: 'border-box' }}>
                    <FileTree
                      sessionId={activeSessionId}
                      refreshKey={fileRefreshKey}
                      onSelectFile={setSelectedFile}
                    />
                  </div>
                  <div style={{ flex: 1, minWidth: 0, height: '100%', overflow: 'auto' }}>
                    <FilePreview sessionId={activeSessionId} path={selectedFile} />
                  </div>
                </div>
              ) : (
                <div style={{ padding: 20, color: '#999' }}>请先创建一个会话</div>
              )
            )}
          </div>
        </Layout.Content>
        <Layout.Sider
          width={360}
          style={{ background: '#fafafa', borderLeft: '1px solid #eee', height: '100%', overflow: 'auto' }}
        >
          <div style={{ padding: 12 }}>
            <ApprovalPanel />
            {activeMeta && (
              <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid #eee', fontSize: 12, color: '#888' }}>
                <div>id: {activeMeta.id}</div>
                <div>created: {activeMeta.createdAt}</div>
                <div>last: {activeMeta.lastActiveAt}</div>
              </div>
            )}
          </div>
        </Layout.Sider>
      </Layout>
    </Layout>
  )
}

export default App
