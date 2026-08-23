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
            paddingLeft: collapsed ? 0 : 4,
          }}>
            <EasyAuditLogoIcon size={32} style={{ flexShrink: 0 }} />
            {!collapsed && (
              <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, lineHeight: 1.2 }}>
                  <span style={{ fontSize: 16, fontWeight: 800, color: '#0f172a', letterSpacing: '0.02em', whiteSpace: 'nowrap' }}>
                    易审通
                  </span>
                  <span style={{
                    fontSize: 10,
                    fontWeight: 700,
                    color: '#2563eb',
                    background: 'rgba(37, 99, 235, 0.08)',
                    border: '1px solid rgba(37, 99, 235, 0.18)',
                    borderRadius: 4,
                    padding: '1px 5px',
                    fontFamily: 'Inter, system-ui, sans-serif',
                    lineHeight: 1.2,
                    letterSpacing: '0.03em',
                    whiteSpace: 'nowrap',
                  }}>
                    EasyAudit
                  </span>
                </div>
                <div style={{
                  fontSize: 11,
                  color: '#64748b',
                  fontWeight: 500,
                  marginTop: 3,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  letterSpacing: '0.02em',
                }}>
                  智能审核协同云平台
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
          {/* 左侧：折叠按钮 + Slogan 品牌胶囊横幅 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined style={{ fontSize: 16 }} /> : <MenuFoldOutlined style={{ fontSize: 16 }} />}
              onClick={toggleCollapsed}
              style={{
                width: 34,
                height: 34,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#64748b',
                borderRadius: 6,
              }}
            />

            {/* Slogan 品牌胶囊横幅 */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: 'linear-gradient(90deg, rgba(37, 99, 235, 0.07) 0%, rgba(6, 182, 212, 0.07) 100%)',
              border: '1px solid rgba(37, 99, 235, 0.15)',
              borderRadius: 20,
              padding: '4px 14px',
            }}>
              <span style={{ fontSize: 13, display: 'flex', alignItems: 'center' }}>✨</span>
              <span style={{
                fontSize: 13,
                fontWeight: 700,
                background: 'linear-gradient(135deg, #1d4ed8 0%, #0284c7 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                letterSpacing: '0.02em',
                whiteSpace: 'nowrap',
              }}>
                让每一次审核都简单高效
              </span>
              <span style={{ width: 1, height: 12, background: 'rgba(37, 99, 235, 0.2)' }} />
              <span style={{ fontSize: 11, color: '#64748b', fontWeight: 500, whiteSpace: 'nowrap' }}>
                新一代认证审核与现场评审智能云平台
              </span>
            </div>
          </div>

          {/* 中间/右侧前：核心状态与能力徽章（消除空白） */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {/* 智审状态 */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: '#f0fdf4',
              border: '1px solid #bbf7d0',
              borderRadius: 6,
              padding: '3px 10px',
              fontSize: 12,
              color: '#166534',
              fontWeight: 600,
            }}>
              <div style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: '#22c55e',
                boxShadow: '0 0 6px rgba(34, 197, 94, 0.6)',
              }} />
              <span>智审 Agent 在线</span>
            </div>

            {/* 质量门禁 */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: '#eff6ff',
              border: '1px solid #bfdbfe',
              borderRadius: 6,
              padding: '3px 10px',
              fontSize: 12,
              color: '#1e40af',
              fontWeight: 500,
            }}>
              <span>🛡️ 6重质量门禁已就绪</span>
            </div>

            {/* 知识检索 */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: '#faf5ff',
              border: '1px solid #e9d5ff',
              borderRadius: 6,
              padding: '3px 10px',
              fontSize: 12,
              color: '#6b21a8',
              fontWeight: 500,
            }}>
              <span>⚡ RAG 语义索引就绪</span>
            </div>
          </div>

          {/* 右侧：用户下拉 */}
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight" trigger={['click']}>
            <div className="user-dropdown-trigger" style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              cursor: 'pointer',
              padding: '5px 12px',
              borderRadius: 8,
              background: 'rgba(241, 245, 249, 0.8)',
              border: '1px solid rgba(226, 232, 240, 0.85)',
              transition: 'all 0.2s',
            }}>
              <Avatar
                style={{
                  background: 'linear-gradient(135deg, #2563eb 0%, #06b6d4 100%)',
                  boxShadow: '0 2px 6px rgba(37, 99, 235, 0.25)',
                  flexShrink: 0,
                  fontWeight: 700,
                }}
                size={34}
              >
                {user?.full_name?.[0] || user?.username?.[0]?.toUpperCase() || 'U'}
              </Avatar>
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                lineHeight: 1.25,
              }}>
                <span style={{
                  fontSize: 13,
                  fontWeight: 700,
                  color: '#0f172a',
                  whiteSpace: 'nowrap',
                }}>
                  {user?.full_name || user?.username || '用户'}
                </span>
                <span style={{
                  fontSize: 11,
                  color: '#2563eb',
                  fontWeight: 600,
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
