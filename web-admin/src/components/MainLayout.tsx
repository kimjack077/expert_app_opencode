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
import { EasyAuditLogoIcon } from '@/components/brand/EasyAuditLogo'

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
        width={224}
        collapsedWidth={64}
        style={{
          boxShadow: '2px 0 8px rgba(0, 0, 0, 0.04)',
          zIndex: 10,
          background: '#ffffff',
        }}
      >
        <div className={`sidebar-logo ${collapsed ? 'collapsed' : ''}`}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            width: '100%',
            overflow: 'hidden',
          }}>
            <EasyAuditLogoIcon size={34} style={{ flexShrink: 0 }} />
            {!collapsed && (
              <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, lineHeight: 1.2 }}>
                  <span style={{ fontSize: 17, fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em' }}>
                    易审通
                  </span>
                  <span style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: '#2563eb',
                    fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
                    letterSpacing: '0.02em',
                  }}>
                    EasyAudit
                  </span>
                </div>
                <div style={{
                  fontSize: 11,
                  color: '#94a3b8',
                  fontWeight: 500,
                  marginTop: 2,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  letterSpacing: '0.02em',
                }}>
                  认证审核智能云平台
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
          {/* 左侧：折叠按钮 + Slogan 优雅排版（无生硬方框，纯净融合） */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined style={{ fontSize: 16 }} /> : <MenuFoldOutlined style={{ fontSize: 16 }} />}
              onClick={toggleCollapsed}
              style={{
                width: 32,
                height: 32,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#64748b',
                borderRadius: 6,
                padding: 0,
              }}
            />

            {/* Slogan 品牌排版 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, userSelect: 'none' }}>
              <span style={{
                fontSize: 14,
                fontWeight: 600,
                color: '#1e293b',
                letterSpacing: '0.01em',
              }}>
                让每一次审核都简单高效
              </span>
              <span style={{ color: '#cbd5e1', fontSize: 13, fontWeight: 300 }}>/</span>
              <span style={{
                fontSize: 12,
                color: '#64748b',
                fontWeight: 400,
              }}>
                新一代认证审核与现场评审智能协同系统
              </span>
            </div>
          </div>

          {/* 右侧：纯净状态指示器 + 分割线 + 用户信息（去方框化，轻盈一体） */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {/* 系统服务在线呼吸灯 */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              color: '#059669',
              fontWeight: 500,
            }}>
              <div style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: '#10b981',
                boxShadow: '0 0 6px rgba(16, 185, 129, 0.6)',
              }} />
              <span>智审服务在线</span>
            </div>

            <div style={{ width: 1, height: 16, background: '#e2e8f0' }} />

            {/* 用户下拉菜单 */}
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight" trigger={['click']}>
              <div className="user-dropdown-trigger">
                <Avatar
                  style={{
                    background: 'linear-gradient(135deg, #2563eb 0%, #06b6d4 100%)',
                    boxShadow: '0 1px 4px rgba(37, 99, 235, 0.25)',
                    flexShrink: 0,
                    fontWeight: 700,
                  }}
                  size={32}
                >
                  {user?.full_name?.[0] || user?.username?.[0]?.toUpperCase() || 'U'}
                </Avatar>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                }}>
                  <span style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: '#1e293b',
                    whiteSpace: 'nowrap',
                  }}>
                    {user?.full_name || user?.username || '用户'}
                  </span>
                  <span style={{
                    fontSize: 11,
                    color: '#2563eb',
                    background: '#eff6ff',
                    fontWeight: 600,
                    padding: '1px 6px',
                    borderRadius: 4,
                    whiteSpace: 'nowrap',
                  }}>
                    {roleLabel(user?.role)}
                  </span>
                </div>
              </div>
            </Dropdown>
          </div>
        </Header>
        <Content className="site-layout-content">
          <Outlet />
        </Content>
        <AgentSidebar context={agentContext} />
      </Layout>
    </Layout>
  )
}
