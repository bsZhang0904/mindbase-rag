import { SendOutlined } from '@ant-design/icons'
import { Button, Card, Empty, Input, List, Spin, Typography, message } from 'antd'
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  chatStream,
  createConversation,
  getMessages,
  listConversations,
  type Citation,
  type Conversation,
  type Message,
} from '../api/client'

export default function ChatPage() {
  const { kbId, convId } = useParams<{ kbId: string; convId: string }>()
  const navigate = useNavigate()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const [citations, setCitations] = useState<Citation[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const loadConversations = async () => {
    if (!kbId) return
    const data = await listConversations(kbId)
    setConversations(data)
  }

  const loadMessages = async () => {
    if (!convId) return
    const data = await getMessages(convId)
    setMessages(data)
    const lastAssistant = [...data].reverse().find((m) => m.role === 'assistant')
    if (lastAssistant?.citations?.length) {
      setCitations(lastAssistant.citations)
    }
  }

  useEffect(() => {
    loadConversations()
  }, [kbId])

  useEffect(() => {
    loadMessages()
  }, [convId])

  useEffect(() => {
    scrollToBottom()
  }, [messages, streaming])

  const newConversation = async () => {
    if (!kbId) return
    const conv = await createConversation(kbId)
    await loadConversations()
    navigate(`/kb/${kbId}/chat/${conv.id}`)
  }

  const sendMessage = async () => {
    if (!convId || !input.trim() || loading || streaming) return
    const question = input.trim()
    setInput('')
    setLoading(true)

    const userMsg: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: question,
      citations: [],
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMsg])

    const assistantMsg: Message = {
      id: `temp-assistant-${Date.now()}`,
      role: 'assistant',
      content: '',
      citations: [],
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, assistantMsg])
    setStreaming(true)

    try {
      const result = await chatStream(convId, question, (token) => {
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last.role === 'assistant') {
            updated[updated.length - 1] = { ...last, content: last.content + token }
          }
          return updated
        })
      })
      setCitations(result.citations)
      await loadMessages()
      await loadConversations()
    } catch {
      message.error('发送失败')
      await loadMessages()
    } finally {
      setLoading(false)
      setStreaming(false)
    }
  }

  return (
    <div className="chat-container">
      <div className="chat-sidebar">
        <div style={{ padding: 16, borderBottom: '1px solid #f0f0f0' }}>
          <Button block onClick={newConversation}>+ 新对话</Button>
        </div>
        <List
          dataSource={conversations}
          renderItem={(item) => (
            <List.Item
              style={{
                cursor: 'pointer',
                background: item.id === convId ? '#e6f4ff' : undefined,
                padding: '12px 16px',
              }}
              onClick={() => navigate(`/kb/${kbId}/chat/${item.id}`)}
            >
              <Typography.Text ellipsis>{item.title || '新对话'}</Typography.Text>
            </List.Item>
          )}
        />
      </div>

      <div className="chat-main">
        <div className="chat-messages">
          {messages.length === 0 ? (
            <Empty description="开始提问吧，我会基于你的文档回答" style={{ marginTop: 80 }} />
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={`message-bubble ${msg.role === 'user' ? 'message-user' : 'message-assistant'}`}
              >
                {msg.content || (streaming && msg.role === 'assistant' ? <Spin size="small" /> : '')}
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
        <div className="chat-input-area">
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入问题，Enter 发送，Shift+Enter 换行"
            autoSize={{ minRows: 2, maxRows: 4 }}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault()
                sendMessage()
              }
            }}
          />
          <div style={{ marginTop: 8, textAlign: 'right' }}>
            <Button type="primary" icon={<SendOutlined />} onClick={sendMessage} loading={loading || streaming}>
              发送
            </Button>
          </div>
        </div>
      </div>

      <div className="citation-panel">
        <Typography.Title level={5}>引用来源</Typography.Title>
        {citations.length === 0 ? (
          <Typography.Text type="secondary">回答中的引用将显示在这里</Typography.Text>
        ) : (
          citations.map((cite) => (
            <Card key={cite.index} size="small" style={{ marginBottom: 12 }} title={`[${cite.index}] ${cite.document_title}`}>
              {cite.page_number && <Typography.Text type="secondary">第 {cite.page_number} 页</Typography.Text>}
              <Typography.Paragraph style={{ marginTop: 8, marginBottom: 0 }} ellipsis={{ rows: 4 }}>
                {cite.excerpt}
              </Typography.Paragraph>
              {cite.score != null && (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  相似度: {(cite.score * 100).toFixed(1)}%
                </Typography.Text>
              )}
            </Card>
          ))
        )}
      </div>
    </div>
  )
}
