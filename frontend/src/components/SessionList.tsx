import { useEffect, useState } from 'react'
import { List, Button, Input, Modal, Dropdown, Empty, message, Space, Select, Tag } from 'antd'
import { PlusOutlined, MoreOutlined, EditOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons'
import { useSessionStore } from '../stores/sessionStore'
import * as api from '../api/sessions'
import type { SessionMeta } from '../stores/sessionStore'

function genId() {
  return 's_' + Math.random().toString(36).slice(2, 10)
}

const SCENARIO_COLORS: Record<string, string> = {
  general: 'default',
  jd: 'blue',
  screen: 'purple',
  interview: 'green',
  policy: 'orange',
}

interface NewSessionModalProps {
  open: boolean
  onClose: () => void
  onCreated: (meta: SessionMeta) => void
}

function NewSessionModal({ open, onClose, onCreated }: NewSessionModalProps) {
  const scenarios = useSessionStore((s) => s.scenarios)
  const setScenarios = useSessionStore((s) => s.setScenarios)
  const [title, setTitle] = useState('新会话')
  const [scenario, setScenario] = useState('general')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (scenarios.length === 0) {
      api.listScenarios().then(setScenarios).catch(() => {})
    }
  }, [scenarios.length, setScenarios])

  const handleOk = async () => {
    setSubmitting(true)
    try {
      const id = genId()
      const meta = await api.createSession(id, title || '新会话', scenario)
      onCreated(meta)
      onClose()
    } catch (e: any) {
      message.error('创建失败: ' + e.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal open={open} onOk={handleOk} onCancel={onClose} title="新建会话" confirmLoading={submitting} okText="创建">
      <div style={{ marginBottom: 12 }}>
        <div style={{ marginBottom: 4 }}>标题</div>
        <Input value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>
      <div>
        <div style={{ marginBottom: 4 }}>场景</div>
        <Select
          value={scenario}
          onChange={setScenario}
          style={{ width: '100%' }}
          options={scenarios.map((s) => ({ value: s.key, label: s.label }))}
        />
      </div>
    </Modal>
  )
}

export function SessionList() {
  const {
    sessions, activeSessionId,
    setActiveSession, setSessions, upsertSession, removeSession,
  } = useSessionStore()
  const [loading, setLoading] = useState(false)
  const [newOpen, setNewOpen] = useState(false)

  const refresh = async () => {
    setLoading(true)
    try {
      const list = await api.listSessions()
      setSessions(list)
      if (!activeSessionId && list.length > 0) {
        setActiveSession(list[0].id)
      }
    } catch (e: any) {
      message.error('加载会话失败: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    (async () => {
      try {
        const list = await api.listSessions()
        if (list.length === 0) {
          setNewOpen(true)
        } else {
          setSessions(list)
          setActiveSession(list[0].id)
        }
      } catch (e: any) {
        message.error('初始化会话失败: ' + e.message)
      }
    })()
  }, [])

  const handleCreated = (meta: SessionMeta) => {
    upsertSession(meta)
    setActiveSession(meta.id)
  }

  const handleRename = (id: string, current: string) => {
    let newTitle = current
    Modal.confirm({
      title: '重命名会话',
      content: (
        <Input defaultValue={current} onChange={(e) => (newTitle = e.target.value)} />
      ),
      onOk: async () => {
        try {
          const meta = await api.renameSession(id, newTitle)
          upsertSession(meta)
        } catch (e: any) {
          message.error('重命名失败: ' + e.message)
        }
      },
    })
  }

  const handleDelete = (id: string) => {
    Modal.confirm({
      title: '删除会话？',
      content: '该操作不可撤销，会话历史消息也会从前端移除。',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await api.deleteSession(id)
          removeSession(id)
          message.success('已删除')
        } catch (e: any) {
          message.error('删除失败: ' + e.message)
        }
      },
    })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <Space style={{ marginBottom: 12, flex: '0 0 auto' }}>
        <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => setNewOpen(true)}>
          新建
        </Button>
        <Button size="small" icon={<ReloadOutlined />} loading={loading} onClick={refresh} />
      </Space>

      <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        {sessions.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无会话" />
        ) : (
          <List
            size="small"
            dataSource={sessions}
            renderItem={(item) => {
              const active = item.id === activeSessionId
              return (
                <List.Item
                  style={{
                    cursor: 'pointer',
                    background: active ? '#e6f4ff' : 'transparent',
                    borderRadius: 4,
                    padding: '6px 8px',
                  }}
                  onClick={() => setActiveSession(item.id)}
                  actions={[
                    <Dropdown
                      key="menu"
                      menu={{
                        items: [
                          { key: 'rename', icon: <EditOutlined />, label: '重命名' },
                          { key: 'delete', icon: <DeleteOutlined />, label: '删除', danger: true },
                        ],
                        onClick: ({ key, domEvent }) => {
                          domEvent.stopPropagation()
                          if (key === 'rename') handleRename(item.id, item.title)
                          if (key === 'delete') handleDelete(item.id)
                        },
                      }}
                      trigger={['click']}
                    >
                      <MoreOutlined onClick={(e) => e.stopPropagation()} />
                    </Dropdown>,
                  ]}
                >
                  <div style={{ overflow: 'hidden' }}>
                    <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.title}
                    </div>
                    {item.scenario && item.scenario !== 'general' && (
                      <Tag color={SCENARIO_COLORS[item.scenario] ?? 'default'} style={{ marginTop: 2, fontSize: 10 }}>
                        {item.scenario}
                      </Tag>
                    )}
                  </div>
                </List.Item>
              )
            }}
          />
        )}
      </div>

      <NewSessionModal
        open={newOpen}
        onClose={() => setNewOpen(false)}
        onCreated={(meta) => {
          handleCreated(meta)
          setNewOpen(false)
        }}
      />
    </div>
  )
}
