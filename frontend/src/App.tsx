import { useEffect, useState } from 'react'
import { Layout, Tag, Tabs, Select, message } from 'antd'
import { useSessionStore } from './stores/sessionStore'
import { useSSE } from './hooks/useSSE'
import { MessageStream } from './components/MessageStream'
import { ChatInput } from './components/ChatInput'
import { ApprovalPanel } from './components/ApprovalPanel'
import { FileTree } from './components/FileTree'
import { FilePreview } from './components/FilePreview'
import { SessionList } from './components/SessionList'
import * as api from './api/sessions'

function App() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId)
  const sessions = useSessionStore((s) => s.sessions)
  const scenarios = useSessionStore((s) => s.scenarios)
  const setScenarios = useSessionStore((s) => s.setScenarios)
  const setSessionScenario = useSessionStore((s) => s.setSessionScenario)
  const agentStatus = useSessionStore((s) => s.agentStatus)
  const sseConnected = useSessionStore((s) => s.sseConnected)
  const doneCounter = useSessionStore((s) => s.doneCounter)
  const [fileRefreshKey, setFileRefreshKey] = useState(0)
  const [selectedFile, setSelectedFile] = useState<string | null>(null)

  useSSE(activeSessionId ?? '')

  useEffect(() => {
    setFileRefreshKey((k) => k + 1)
  }, [doneCounter])

  useEffect(() => {
    if (scenarios.length === 0) {
      api.listScenarios().then(setScenarios).catch(() => {})
    }
  }, [scenarios.length, setScenarios])

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
    <Layout style={{ height: '100vh' }}>
      <Layout.Header style={{ background: '#fff', borderBottom: '1px solid #eee', display: 'flex', alignItems: 'center', gap: 12 }}>
        <strong>HR Recruit Agent</strong>
        <Tag color={sseConnected ? 'green' : 'red'}>SSE {sseConnected ? '在线' : '离线'}</Tag>
        <Tag>{agentStatus}</Tag>
        <Tag>session: {activeSessionId ?? '-'}</Tag>
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
      <Layout style={{ overflow: 'hidden' }}>
        <Layout.Sider width={240} style={{ background: '#fafafa', borderRight: '1px solid #eee', padding: 12 }}>
          <SessionList />
        </Layout.Sider>
        <Layout.Content style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <Tabs
            style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
            tabBarStyle={{ paddingLeft: 16, marginBottom: 0 }}
            items={[
              {
                key: 'chat',
                label: '对话',
                children: activeSessionId ? (
                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <MessageStream />
                    <ChatInput sessionId={activeSessionId} />
                  </div>
                ) : (
                  <div style={{ padding: 20, color: '#999' }}>请先创建一个会话</div>
                ),
              },
              {
                key: 'files',
                label: '文件',
                children: activeSessionId ? (
                  <div style={{ display: 'flex', height: '100%' }}>
                    <div style={{ width: 240, borderRight: '1px solid #eee', padding: 12, overflowY: 'auto' }}>
                      <FileTree
                        sessionId={activeSessionId}
                        refreshKey={fileRefreshKey}
                        onSelectFile={setSelectedFile}
                      />
                    </div>
                    <div style={{ flex: 1, overflow: 'auto' }}>
                      <FilePreview sessionId={activeSessionId} path={selectedFile} />
                    </div>
                  </div>
                ) : (
                  <div style={{ padding: 20, color: '#999' }}>请先创建一个会话</div>
                ),
              },
            ]}
          />
        </Layout.Content>
        <Layout.Sider width={360} style={{ background: '#fafafa', borderLeft: '1px solid #eee', padding: 12, overflowY: 'auto' }}>
          <ApprovalPanel />
          {activeMeta && (
            <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid #eee', fontSize: 12, color: '#888' }}>
              <div>id: {activeMeta.id}</div>
              <div>created: {activeMeta.createdAt}</div>
              <div>last: {activeMeta.lastActiveAt}</div>
            </div>
          )}
        </Layout.Sider>
      </Layout>
    </Layout>
  )
}

export default App
