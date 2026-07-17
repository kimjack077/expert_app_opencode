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
  AuditOutlined,
  PieChartOutlined,
  ScheduleOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import AgentSidebar from '@/components/agent/AgentSidebar'
import { roleLabel } from '@/utils/display'

const { Header, Sider, Content } = Layout

export default function MainLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const { collapsed, toggleCollapsed } = useAppStore()
  const projectMatch = location.pathname.match(/^\/audit-projects\/([^/]+)/)
  const activeProjectId = projectMatch?.[1] === 'create' ? undefined : projectMatch?.[1]
  const searchParams = new URLSearchParams(location.search)
  const agentContext = {
    page: location.pathname,
    projectId: activeProjectId,
    auditSessionId: searchParams.get('sessionId') || undefined,
    planItemId: searchParams.get('planItemId') || undefined,
  }

  // 根据角色过滤菜单
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin'
  const isFieldUser = user?.role === 'expert' || user?.role === 'auditor'

  // 分组菜单：现场工作 / 项目管理 / 基础配置
  const menuItems = [
    {
      type: 'group' as const,
      label: collapsed ? '' : '现场工作',
      children: [
        { key: '/dashboard', icon: <DashboardOutlined />, label: '工作台' },
        { key: '/my-audit-tasks', icon: <ScheduleOutlined />, label: '我的审核任务' },
        // 日常检查任务：管理员常用；审核员也可见但降为次要
        ...(!isFieldUser || isAdmin
          ? [{ key: '/tasks', icon: <UnorderedListOutlined />, label: '日常检查任务' }]
          : [{ key: '/tasks', icon: <UnorderedListOutlined />, label: '日常检查任务' }]),
        { key: '/records', icon: <FileDoneOutlined />, label: '检查记录' },
      ],
    },
    {
      type: 'group' as const,
      label: collapsed ? '' : '项目管理',
      children: [
        { key: '/audit-projects', icon: <AuditOutlined />, label: '审核项目' },
        { key: '/enterprises', icon: <BankOutlined />, label: '企业管理' },
        { key: '/audit-statistics', icon: <PieChartOutlined />, label: '审核统计' },
      ],
    },
    {
      type: 'group' as const,
      label: collapsed ? '' : '基础配置',
      children: [
        { key: '/templates', icon: <FileTextOutlined />, label: '检查模板' },
        { key: '/knowledge', icon: <BookOutlined />, label: '知识库' },
        { key: '/analytics', icon: <BarChartOutlined />, label: '数据分析' },
        ...(isAdmin
          ? [
              { key: '/users', icon: <TeamOutlined />, label: '用户管理' },
              { key: '/industries', icon: <AppstoreOutlined />, label: '行业分类' },
            ]
          : []),
      ],
    },
  ]

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
              <div>
                <div className="sidebar-logo-text">EFIS</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2, fontWeight: 400 }}>
                  专家现场审核平台
                </div>
              </div>
            )}
          </div>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          defaultOpenKeys={['现场工作', '项目管理', '基础配置']}
          items={menuItems}
          onClick={({ key }) => {
            if (typeof key === 'string' && key.startsWith('/')) navigate(key)
          }}
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
                  {roleLabel(user?.role)}
                </span>
              </div>
            </div>
          </Dropdown>
        </Header>
        <Content className="site-layout-content">
          <Outlet />
        </Content>
        <AgentSidebar context={agentContext} />
      </Layout>
    </Layout>
  )
}
