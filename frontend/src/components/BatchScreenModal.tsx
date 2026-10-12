import { useEffect, useState } from 'react'
import { Modal, Input, Select, message, Button } from 'antd'
import { useSessionStore } from '../stores/sessionStore'
import { fetchTree } from '../api/files'
import type { FileNode } from '../types/files'

interface Props {
  open: boolean
  sessionId: string
  onClose: () => void
}

function collectResumes(node: FileNode): string[] {
  const out: string[] = []
  const walk = (n: FileNode) => {
    if (n.type === 'file') {
      if (/\.(pdf|docx|txt)$/i.test(n.name)) out.push(n.path)
      return
    }
    for (const c of n.children ?? []) walk(c)
  }
  walk(node)
  return out
}

export function BatchScreenModal({ open, sessionId, onClose }: Props) {
  const [jd, setJd] = useState('')
  const [options, setOptions] = useState<{ value: string; label: string }[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [submitting, setSubmitting] = useState(false)

  const addMessage = useSessionStore((s) => s.addMessage)
  const upsertBatchMessage = useSessionStore((s) => s.upsertBatchMessage)

  useEffect(() => {
    if (!open) return
    fetchTree(sessionId)
      .then((tree) => {
        const list = collectResumes(tree).filter((p) => p.startsWith('uploads/'))
        setOptions(list.map((p) => ({ value: p, label: p.replace(/^uploads\//, '') })))
      })
      .catch((e: Error) => message.error('加载文件列表失败: ' + e.message))
  }, [open, sessionId])

  const submit = async () => {
    if (!jd.trim()) { message.warning('请填写 JD 文本'); return }
    if (selected.length === 0) { message.warning('请至少选择一份简历'); return }
    setSubmitting(true)
    try {
      const res = await fetch(`/api/sessions/${sessionId}/batch-screen`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jd_text: jd, resume_paths: selected }),
      })
      if (res.status === 409) { message.warning('该会话有任务正在进行中'); return }
      if (!res.ok) {
        const err = await res.text()
        message.error(`启动失败: HTTP ${res.status} ${err}`)
        return
      }
      addMessage({
        kind: 'user',
        id: 'u_' + Date.now(),
        text: `[批量评估] ${selected.length} 份简历`,
      })
      upsertBatchMessage({
        total: selected.length,
        completed: 0,
        current: null,
        errors: [],
        status: 'running',
      })
      onClose()
      setJd('')
      setSelected([])
    } catch (e) {
      message.error('提交异常: ' + (e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      title="批量评估简历"
      onCancel={onClose}
      footer={[
        <Button key="cancel" onClick={onClose}>取消</Button>,
        <Button key="ok" type="primary" loading={submitting} onClick={submit}>
          开始评估
        </Button>,
      ]}
      width={640}
    >
      <div style={{ marginBottom: 12 }}>
        <div style={{ marginBottom: 4, fontWeight: 500 }}>岗位要求（JD）</div>
        <Input.TextArea
          rows={6}
          value={jd}
          onChange={(e) => setJd(e.target.value)}
          placeholder="粘贴 JD 或描述岗位要求"
        />
      </div>
      <div>
        <div style={{ marginBottom: 4, fontWeight: 500 }}>
          选择简历（来自 uploads/）
        </div>
        <Select
          mode="multiple"
          value={selected}
          onChange={setSelected}
          options={options}
          style={{ width: '100%' }}
          placeholder={options.length === 0 ? '当前会话没有可用的简历文件，请先上传' : '选择要评估的简历'}
          disabled={options.length === 0}
        />
      </div>
    </Modal>
  )
}
