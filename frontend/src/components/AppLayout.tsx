import { LogoutOutlined, PlusOutlined } from '@ant-design/icons'
import { Button, Dropdown, Layout, Menu, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { clearToken, getMe, listKnowledgeBases, type KnowledgeBase, type User } from '../api/client'

const { Header, Content } = Layout

export default function AppLayout() {
  const navigate = useNavigate()
  const [user, setUser] = useState<User | null>(null)
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])

  const load = async () => {
    try {
      const [me, kbData] = await Promise.all([getMe(), listKnowledgeBases()])
      setUser(me)
      setKbs(kbData.items)
    } catch {
      clearToken()
      navigate('/login')
    }
  }

  useEffect(() => {
    load()
  }, [])

  const logout = () => {
    clearToken()
    message.success('已退出登录')
    navigate('/login')
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <Typography.Title level={4} style={{ color: '#fff', margin: 0, cursor: 'pointer' }} onClick={() => navigate('/')}>
            MindBase
          </Typography.Title>
          <Menu
            theme="dark"
            mode="horizontal"
            selectable={false}
            items={kbs.slice(0, 5).map((kb) => ({
              key: kb.id,
              label: kb.name,
              onClick: () => navigate(`/kb/${kb.id}`),
            }))}
            style={{ flex: 1, minWidth: 0, background: 'transparent' }}
          />
        </div>
        <Dropdown
          menu={{
            items: [
              { key: 'home', label: '知识库列表', onClick: () => navigate('/') },
              { key: 'logout', label: '退出登录', icon: <LogoutOutlined />, onClick: logout },
            ],
          }}
        >
          <Button type="text" style={{ color: '#fff' }}>
            {user?.username || '用户'}
          </Button>
        </Dropdown>
      </Header>
      <Content>
        <Outlet context={{ refreshKbs: load, kbs }} />
      </Content>
    </Layout>
  )
}

export { PlusOutlined }
