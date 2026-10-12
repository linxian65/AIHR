import { useEffect, useState } from 'react'
import { Tree, Empty, Button, message } from 'antd'
import { ReloadOutlined, FileOutlined, FolderOutlined } from '@ant-design/icons'
import { fetchTree } from '../api/files'
import type { FileNode } from '../types/files'

function toTreeData(node: FileNode): any {
  if (node.type === 'file') {
    return {
      key: node.path,
      title: node.name,
      isLeaf: true,
      icon: <FileOutlined />,
      data: node,
    }
  }
  return {
    key: node.path || '__root__',
    title: node.name,
    icon: <FolderOutlined />,
    selectable: false,
    children: (node.children ?? []).map(toTreeData),
  }
}

interface Props {
  sessionId: string
  onSelectFile: (path: string) => void
  refreshKey: number
}

export function FileTree({ sessionId, onSelectFile, refreshKey }: Props) {
  const [tree, setTree] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const root = await fetchTree(sessionId)
      const children = root.children ?? []
      setTree(children.map(toTreeData))
    } catch (e: any) {
      message.error('加载文件树失败: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [sessionId, refreshKey])

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontWeight: 500 }}>工作区</span>
        <Button size="small" icon={<ReloadOutlined />} loading={loading} onClick={load} />
      </div>
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        {tree.length === 0 && !loading ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无文件" />
        ) : (
          <Tree
            showIcon
            treeData={tree}
            onSelect={(keys) => {
              const k = keys[0]
              if (k && typeof k === 'string' && !k.endsWith('/')) {
                onSelectFile(k)
              }
            }}
          />
        )}
      </div>
    </div>
  )
}
