import { DeleteOutlined, FolderOpenOutlined, MessageOutlined, PlusOutlined } from '@ant-design/icons'
import { Button, Card, Col, Empty, Form, Input, Modal, Popconfirm, Row, Tag, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { createKnowledgeBase, deleteKnowledgeBase, listKnowledgeBases, type KnowledgeBase } from '../api/client'

interface OutletContext {
  refreshKbs: () => Promise<void>
}

export default function HomePage() {
  const navigate = useNavigate()
  const { refreshKbs } = useOutletContext<OutletContext>()
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const data = await listKnowledgeBases()
      setKbs(data.items)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleCreate = async () => {
    const values = await form.validateFields()
    await createKnowledgeBase(values.name, values.description)
    message.success('知识库创建成功')
    setModalOpen(false)
    form.resetFields()
    await load()
    await refreshKbs()
  }

  const handleDelete = async (id: string) => {
    await deleteKnowledgeBase(id)
    message.success('已删除')
    await load()
    await refreshKbs()
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <Typography.Title level={3} style={{ margin: 0 }}>我的知识库</Typography.Title>
          <Typography.Text type="secondary">上传文档，基于私有资料进行 AI 问答</Typography.Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新建知识库
        </Button>
      </div>

      {!loading && kbs.length === 0 ? (
        <Empty description="还没有知识库，创建一个开始吧">
          <Button type="primary" onClick={() => setModalOpen(true)}>新建知识库</Button>
        </Empty>
      ) : (
        <Row gutter={[16, 16]}>
          {kbs.map((kb) => (
            <Col xs={24} sm={12} lg={8} key={kb.id}>
              <Card
                hoverable
                actions={[
                  <FolderOpenOutlined key="open" onClick={() => navigate(`/kb/${kb.id}`)} />,
                  <MessageOutlined key="chat" onClick={() => navigate(`/kb/${kb.id}`)} />,
                  <Popconfirm key="del" title="确定删除该知识库？" onConfirm={() => handleDelete(kb.id)}>
                    <DeleteOutlined style={{ color: '#ff4d4f' }} />
                  </Popconfirm>,
                ]}
                onClick={() => navigate(`/kb/${kb.id}`)}
              >
                <Card.Meta
                  title={kb.name}
                  description={
                    <div>
                      <div style={{ marginBottom: 8, minHeight: 40 }}>{kb.description || '暂无描述'}</div>
                      <Tag color="blue">{kb.document_count} 个文档</Tag>
                    </div>
                  }
                />
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal title="新建知识库" open={modalOpen} onOk={handleCreate} onCancel={() => setModalOpen(false)} okText="创建">
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如：操作系统笔记" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea placeholder="可选" rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
