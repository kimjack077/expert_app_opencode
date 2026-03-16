import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Dropdown, Avatar, Button } from 'antd'
import {
  DashboardOutlined,
  FileTextOutlined,
  UnorderedListOutlined,
  BarChartOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UserOutlined,
  LogoutOutlined,
  BankOutlined,
  BookOutlined,
  FileDoneOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
  AppstoreOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import AgentSidebar from '@/components/agent/AgentSidebar'

const { Header, Sider, Content } = Layout

export default function MainLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const { collapsed, toggleCollapsed } = useAppStore()

  // 根据角色过滤菜单
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin'

  const allMenuItems = [
    { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘', adminOnly: false },
    { key: '/enterprises', icon: <BankOutlined />, label: '企业管理', adminOnly: false },
    { key: '/templates', icon: <FileTextOutlined />, label: '检查模板', adminOnly: false },
    { key: '/records', icon: <FileDoneOutlined />, label: '检查记录', adminOnly: false },
    { key: '/tasks', icon: <UnorderedListOutlined />, label: '检查任务', adminOnly: false },
    { key: '/knowledge', icon: <BookOutlined />, label: '知识库', adminOnly: false },
    { key: '/analytics', icon: <BarChartOutlined />, label: '数据分析', adminOnly: false },
    { key: '/users', icon: <TeamOutlined />, label: '用户管理', adminOnly: true },
    { key: '/industries', icon: <AppstoreOutlined />, label: '行业分类', adminOnly: true },
  ]

  const menuItems = allMenuItems
    .filter(item => !item.adminOnly || isAdmin)
    .map(({ adminOnly, ...rest }) => rest)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人信息',
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      danger: true,
      onClick: handleLogout,
    },
  ]

  return (
    <Layout className="layout-container">
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        theme="light"
        style={{
          boxShadow: '2px 0 8px rgba(0, 0, 0, 0.04)',
          zIndex: 10,
        }}
      >
        <div className="sidebar-logo">
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: collapsed ? 0 : 10,
          }}>
            <div style={{
              width: 36,
              height: 36,
              background: 'linear-gradient(135deg, var(--primary-color) 0%, var(--accent-color) 100%)',
              borderRadius: 10,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}>
              <SafetyCertificateOutlined style={{ fontSize: 20, color: 'white' }} />
            </div>
            {!collapsed && (
              <span className="sidebar-logo-text">EFIS</span>
            )}
          </div>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{
            borderRight: 0,
            paddingTop: 8,
            paddingBottom: 8,
          }}
        />
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          padding: '16px 12px',
          borderTop: '1px solid var(--border-color)',
          background: 'var(--card-bg)',
        }}>
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={toggleCollapsed}
            style={{
              width: '100%',
              height: 40,
              display: 'flex',
              alignItems: 'center',
              justifyContent: collapsed ? 'center' : 'flex-start',
              gap: 8,
              color: 'var(--text-muted)',
            }}
          >
            {!collapsed && '收起菜单'}
          </Button>
        </div>
      </Sider>
      <Layout>
        <Header className="header-container">
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}>
              <div style={{
                width: 8,
                height: 8,
                background: 'var(--success-color)',
                borderRadius: '50%',
                boxShadow: '0 0 8px rgba(16, 185, 129, 0.5)',
              }} />
              <span style={{
                color: 'var(--text-muted)',
                fontSize: 13,
              }}>
                系统运行正常
              </span>
            </div>
          </div>
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight" trigger={['click']}>
            <div className="user-dropdown-trigger" style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              cursor: 'pointer',
              padding: '6px 12px',
              borderRadius: 8,
              transition: 'all 0.2s',
            }}>
              <Avatar
                style={{
                  backgroundColor: 'var(--primary-color)',
                  flexShrink: 0,
                }}
                size={36}
              >
                {user?.full_name?.[0] || user?.username?.[0]?.toUpperCase() || 'U'}
              </Avatar>
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                lineHeight: 1.3,
              }}>
                <span style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: 'var(--text-main)',
                  whiteSpace: 'nowrap',
                }}>
                  {user?.full_name || user?.username || '用户'}
                </span>
                <span style={{
                  fontSize: 12,
                  color: 'var(--text-muted)',
                  whiteSpace: 'nowrap',
                }}>
                  {user?.role === 'admin' ? '管理员' : user?.role === 'manager' ? '主管' : '专家'}
                </span>
              </div>
            </div>
          </Dropdown>
        </Header>
        <Content className="site-layout-content">
          <Outlet />
        </Content>
        <AgentSidebar context={{}} />
      </Layout>
    </Layout>
  )
}
