import { useState } from 'react'
import { Upload, message } from 'antd'
import { InboxOutlined } from '@ant-design/icons'

const { Dragger } = Upload

interface Props {
  sessionId: string
  onUploaded: (path: string) => void
}

export function UploadZone({ sessionId, onUploaded }: Props) {
  const [uploading, setUploading] = useState(false)

  const customRequest = async (options: any) => {
    const { file, onSuccess, onError } = options
    const form = new FormData()
    form.append('file', file)
    setUploading(true)
    try {
      const res = await fetch(`/api/files/${sessionId}/upload`, {
        method: 'POST',
        body: form,
      })
      if (!res.ok) {
        const err = await res.text()
        throw new Error(`HTTP ${res.status}: ${err}`)
      }
      const data = await res.json()
      onSuccess?.(data)
      message.success(`已上传 ${data.filename}`)
      onUploaded(data.path)
    } catch (e: any) {
      message.error('上传失败: ' + e.message)
      onError?.(e)
    } finally {
      setUploading(false)
    }
  }

  return (
    <Dragger
      customRequest={customRequest}
      showUploadList={false}
      accept=".pdf,.docx,.txt"
      multiple={false}
      disabled={uploading}
    >
      <p className="ant-upload-drag-icon"><InboxOutlined /></p>
      <p className="ant-upload-text">
        {uploading ? '上传中...' : '点击或拖拽简历到此处'}
      </p>
      <p className="ant-upload-hint">支持 .pdf / .docx / .txt，单文件 ≤ 10MB</p>
    </Dragger>
  )
}
