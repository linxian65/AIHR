import { Card, Button, Tag, Input, Space, Empty, message } from 'antd'
import { useState } from 'react'
import { useSessionStore } from '../stores/sessionStore'
import type { PendingApproval } from '../types/events'

function prettifyToolName(name: string): string {
  return name
    .replace(/^mcp__/, '')
    .replace(/__/g, ' / ')
}

function describeAction(name: string): string {
  if (name.includes('send_email')) return '发送邮件'
  if (name.includes('notify')) return '发送通知'
  if (name.includes('ats')) return '更新 ATS 系统'
  return '执行操作'
}

function ApprovalCard({ approval }: { approval: PendingApproval }) {
  const sessionId = useSessionStore((s) => s.activeSessionId)
  const removePendingApproval = useSessionStore((s) => s.removePendingApproval)
  const [rejectReason, setRejectReason] = useState('')
  const [showReject, setShowReject] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const decide = async (approved: boolean) => {
    setSubmitting(true)
    try {
      const res = await fetch(
        `/api/sessions/${sessionId}/approvals/${approval.approval_id}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ approved, reason: approved ? null : rejectReason || 'user_rejected' }),
        }
      )
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      if (!data.ok) {
        message.warning('该审批已被处理或超时')
      }
      removePendingApproval(approval.approval_id)
    } catch (e: any) {
      message.error('提交失败: ' + e.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card
      size="small"
      title={<Tag color="orange">⚠ {describeAction(approval.tool_name)}</Tag>}
      style={{ marginBottom: 12, borderColor: '#ffa940' }}
    >
      <div style={{ fontSize: 12, color: '#888', marginBottom: 8 }}>
        {prettifyToolName(approval.tool_name)}
      </div>
      <pre style={{
        fontSize: 11,
        background: '#fafafa',
        padding: 8,
        borderRadius: 4,
        maxHeight: 200,
        overflow: 'auto',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-all',
      }}>
        {JSON.stringify(approval.input, null, 2)}
      </pre>
      {!showReject ? (
        <Space style={{ marginTop: 8 }}>
          <Button type="primary" size="small" loading={submitting} onClick={() => decide(true)}>
            同意
          </Button>
          <Button danger size="small" disabled={submitting} onClick={() => setShowReject(true)}>
            拒绝
          </Button>
        </Space>
      ) : (
        <div style={{ marginTop: 8 }}>
          <Input.TextArea
            size="small"
            rows={2}
            placeholder="拒绝理由（可选）"
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
          />
          <Space style={{ marginTop: 8 }}>
            <Button danger size="small" loading={submitting} onClick={() => decide(false)}>
              确认拒绝
            </Button>
            <Button size="small" disabled={submitting} onClick={() => setShowReject(false)}>
              取消
            </Button>
          </Space>
        </div>
      )}
    </Card>
  )
}

export function ApprovalPanel() {
  const pending = useSessionStore((s) => s.pendingApprovals)
  return (
    <div>
      <div style={{ marginBottom: 12, fontWeight: 500 }}>
        待审批 {pending.length > 0 && <Tag color="orange">{pending.length}</Tag>}
      </div>
      {pending.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无待审批" />
      ) : (
        pending.map((a) => <ApprovalCard key={a.approval_id} approval={a} />)
      )}
    </div>
  )
}
