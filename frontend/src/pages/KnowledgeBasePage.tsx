import { DeleteOutlined, MessageOutlined, UploadOutlined } from '@ant-design/icons'
import { Button, Card, Popconfirm, Space, Table, Tag, Typography, Upload, message } from 'antd'
import type { UploadProps } from 'antd'
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  createConversation,
  deleteDocument,
  getDocument,
  listDocuments,
  uploadDocument,
  type DocumentItem,
} from '../api/client'

const statusMap: Record<string, { color: string; text: string }> = {
  pending: { color: 'default', text: '等待处理' },
  processing: { color: 'processing', text: '解析中' },
  ready: { color: 'success', text: '已就绪' },
  failed: { color: 'error', text: '失败' },
}

export default function KnowledgeBasePage() {
  const { kbId } = useParams<{ kbId: string }>()
  const navigate = useNavigate()
  const [docs, setDocs] = useState<DocumentItem[]>([])
  const [loading, setLoading] = useState(true)
  const pollingRef = useRef<Set<string>>(new Set())

  const load = async () => {
    if (!kbId) return
    const data = await listDocuments(kbId)
    setDocs(data)
    setLoading(false)

    const pending = data.filter((d) => d.status === 'pending' || d.status === 'processing')
    for (const doc of pending) {
      if (!pollingRef.current.has(doc.id)) {
        pollingRef.current.add(doc.id)
        pollDocument(doc.id)
      }
    }
  }

  const pollDocument = async (docId: string) => {
    const poll = async () => {
      const doc = await getDocument(docId)
      setDocs((prev) => prev.map((d) => (d.id === docId ? doc : d)))
      if (doc.status === 'pending' || doc.status === 'processing') {
        setTimeout(poll, 2000)
      } else {
        pollingRef.current.delete(docId)
        if (doc.status === 'ready') message.success(`文档「${doc.title}」索引完成`)
        if (doc.status === 'failed') message.error(`文档「${doc.title}」处理失败：${doc.error_message}`)
      }
    }
    poll()
  }

  useEffect(() => {
    load()
  }, [kbId])

  const uploadProps: UploadProps = {
    showUploadList: false,
    beforeUpload: async (file) => {
      if (!kbId) return false
      try {
        await uploadDocument(kbId, file)
        message.success('上传成功，正在解析...')
        await load()
      } catch {
        message.error('上传失败')
      }
      return false
    },
  }

  const startChat = async () => {
    if (!kbId) return
    const readyDocs = docs.filter((d) => d.status === 'ready')
    if (readyDocs.length === 0) {
      message.warning('请先上传文档并等待索引完成')
      return
    }
    const conv = await createConversation(kbId)
    navigate(`/kb/${kbId}/chat/${conv.id}`)
  }

  const columns = [
    { title: '标题', dataIndex: 'title', key: 'title' },
    { title: '类型', dataIndex: 'file_type', key: 'file_type', width: 80 },
    {
      title: '大小',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 100,
      render: (v: number) => `${(v / 1024).toFixed(1)} KB`,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (s: string) => {
        const info = statusMap[s] || { color: 'default', text: s }
        return <Tag color={info.color}>{info.text}</Tag>
      },
    },
    { title: '块数', dataIndex: 'chunk_count', key: 'chunk_count', width: 80 },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: DocumentItem) => (
        <Popconfirm title="确定删除？" onConfirm={async () => { await deleteDocument(record.id); await load() }}>
          <Button type="text" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ]

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>知识库文档</Typography.Title>
        <Space>
          <Upload {...uploadProps}>
            <Button icon={<UploadOutlined />}>上传文档</Button>
          </Upload>
          <Button type="primary" icon={<MessageOutlined />} onClick={startChat}>
            开始对话
          </Button>
        </Space>
      </div>

      <Card>
        <Typography.Paragraph type="secondary">
          支持 PDF、Markdown、TXT。上传后系统自动解析并建立向量索引。
        </Typography.Paragraph>
        <Table rowKey="id" loading={loading} columns={columns} dataSource={docs} pagination={false} />
      </Card>
    </div>
  )
}
