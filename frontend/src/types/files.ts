export interface FileNode {
  name: string
  path: string
  type: 'file' | 'dir'
  size?: number
  mtime?: number
  children?: FileNode[]
}
