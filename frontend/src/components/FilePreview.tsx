import { useEffect, useState } from 'react'
import { Spin, Empty, Alert } from 'antd'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { fetchFileContent } from '../api/files'

interface Props {
  sessionId: string
  path: string | null
}

export function FilePreview({ sessionId, path }: Props) {
  const [content, setContent] = useState<string | null>(null)
  const [binary, setBinary] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!path) return
    setLoading(true); setError(null); setBinary(false)
    fetchFileContent(sessionId, path)
      .then((r) => {
        if (r.binary) { setBinary(true); setContent(null) }
        else setContent(r.content)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [sessionId, path])

  if (!path) return <Empty description="从左侧选择文件" style={{ marginTop: 60 }} />
  if (loading) return <Spin style={{ marginTop: 60 }} />
  if (error) return <Alert type="error" message={error} />
  if (binary) return <Alert type="info" message="二进制文件，暂不支持预览" />

  const isMarkdown = path.endsWith('.md') || path.endsWith('.markdown')

  return (
    <div style={{ padding: 16, height: '100%', overflow: 'auto' }}>
      <div style={{ fontSize: 12, color: '#999', marginBottom: 12 }}>{path}</div>
      {isMarkdown ? (
        <div className="markdown-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content ?? ''}</ReactMarkdown>
        </div>
      ) : (
        <pre style={{ fontSize: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
          {content}
        </pre>
      )}
    </div>
  )
}
