import type { FileNode } from '../types/files'

export async function fetchTree(sessionId: string): Promise<FileNode> {
  const res = await fetch(`/api/files/${sessionId}/tree`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchFileContent(
  sessionId: string,
  path: string
): Promise<{ path: string; binary: boolean; content: string | null }> {
  const res = await fetch(
    `/api/files/${sessionId}/content?path=${encodeURIComponent(path)}`
  )
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
