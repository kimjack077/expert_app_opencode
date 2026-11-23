import { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Dropdown, Avatar, Button, Tooltip, Modal, Descriptions, Form, Input, message } from 'antd'
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
  DownOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { authApi } from '@/services/api'
import AgentSidebar from '@/components/agent/AgentSidebar'
import NotificationBell from '@/components/NotificationBell'
import { roleLabel } from '@/utils/display'
import { isAdminRole } from '@/utils/roles'
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
  const isAdmin = isAdminRole(user?.role)

  // 分组菜单：现场工作 / 项目管理 / 基础配置
  const menuItems = [
    {
      type: 'group' as const,
      label: collapsed ? '' : '现场工作',
      children: [
        { key: '/dashboard', icon: <DashboardOutlined />, label: '工作台' },
        { key: '/my-audit-tasks', icon: <ScheduleOutlined />, label: '我的审核任务' },
        // 「日常检查（待执行）」= 部署下去、待现场执行的任务；「检查记录与报告」= 已完成的归档成果
        { key: '/tasks', icon: <UnorderedListOutlined />, label: '日常检查（待执行）' },
        { key: '/records', icon: <FileDoneOutlined />, label: '检查记录与报告' },
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

  const [profileOpen, setProfileOpen] = useState(false)
  const [pwdSaving, setPwdSaving] = useState(false)
  const [pwdForm] = Form.useForm()

  const handleLogout = async () => {
    try {
      await authApi.logout()
    } catch {
      // 服务端不可用时仍允许本地退出
    } finally {
      logout()
      navigate('/login')
    }
  }

  const handleChangePassword = async () => {
    try {
      const values = await pwdForm.validateFields()
      setPwdSaving(true)
      await authApi.changePassword(values.old_password, values.new_password)
      message.success('密码修改成功，请重新登录')
      setProfileOpen(false)
      pwdForm.resetFields()
      logout()
      navigate('/login')
    } catch (error: any) {
      if (!error?.errorFields) {
        message.error(error?.response?.data?.message || error?.response?.data?.detail || '密码修改失败')
      }
    } finally {
      setPwdSaving(false)
    }
  }

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人信息',
      onClick: () => setProfileOpen(true),
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
        className="main-layout-sider"
        style={{
          boxShadow: '2px 0 8px rgba(0, 0, 0, 0.04)',
          zIndex: 10,
          background: '#ffffff',
        }}
      >
        <div
          className={`sidebar-logo ${collapsed ? 'collapsed' : ''}`}
          onClick={() => navigate('/dashboard')}
          title="返回工作台"
          style={{ cursor: 'pointer' }}
        >
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 9,
            width: '100%',
            overflow: 'hidden',
          }}>
            <EasyAuditLogoIcon size={30} style={{ flexShrink: 0 }} />
            {!collapsed && (
              <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, lineHeight: 1.1 }}>
                  <span style={{ fontSize: 16, fontWeight: 800, color: '#ffffff', letterSpacing: '-0.02em' }}>
                    易审通
                  </span>
                  <span style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: '#38bdf8',
                    fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
                    letterSpacing: '0.02em',
                  }}>
                    EasyAudit
                  </span>
                </div>
                <div style={{
                  fontSize: 10,
                  color: '#94a3b8',
                  fontWeight: 500,
                  marginTop: 1,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  letterSpacing: '0.02em',
                  lineHeight: 1,
                }}>
                  认证审核智能云平台
                </div>
              </div>
            )}
          </div>
        </div>
        <div className="sidebar-menu-wrapper">
          <Menu
            mode="inline"
            selectedKeys={[(() => {
              const p = location.pathname
              if (p.startsWith('/audit-projects')) return '/audit-projects'
              if (p.startsWith('/tasks') || p.startsWith('/inspection')) return '/tasks'
              if (p.startsWith('/records') || p.startsWith('/record/')) return '/records'
              if (p.startsWith('/audit-item/')) return '/my-audit-tasks'
              return p
            })()]}
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
        </div>
        <div className="sidebar-footer">
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={toggleCollapsed}
            style={{
              width: '100%',
              height: 36,
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
      <Layout className="main-layout-body">
        <Header className="header-container">
          {/* 左侧：折叠按钮 + 品牌 Slogan 与系统标识 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Button
              type="text"
              className="header-toggle-btn"
              icon={collapsed ? <MenuUnfoldOutlined style={{ fontSize: 16 }} /> : <MenuFoldOutlined style={{ fontSize: 16 }} />}
              onClick={toggleCollapsed}
            />

            {/* Slogan 品牌排版 */}
            <div style={{ display: 'flex', alignItems: 'center', userSelect: 'none' }}>
              <span className="header-brand-title">
                让每一次审核都简单高效
              </span>
              <span className="header-brand-divider">/</span>
              <span className="header-brand-sub">
                新一代认证审核与现场评审智能协同云平台
              </span>
            </div>
          </div>

          {/* 右侧：状态指示器 + 快捷入口 + 分割线 + 用户信息 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {/* 系统服务在线呼吸灯胶囊 */}
            <div className="header-status-pill">
              <span className="pulse-dot" />
              <span>智审服务在线</span>
            </div>

            {/* 智审主动提醒：复审到期 / NC 超期 / 草稿积压 */}
            <NotificationBell />

            {/* 快捷知识库检索 */}
            <Tooltip title="知识库与审核标准">
              <Button
                type="text"
                className="header-icon-btn"
                icon={<BookOutlined style={{ fontSize: 15 }} />}
                onClick={() => navigate('/knowledge')}
              />
            </Tooltip>

            {/* 快捷审核项目 */}
            <Tooltip title="审核项目库">
              <Button
                type="text"
                className="header-icon-btn"
                icon={<AuditOutlined style={{ fontSize: 15 }} />}
                onClick={() => navigate('/audit-projects')}
              />
            </Tooltip>

            {/* 面向业务用户的在线使用文档（/docs）；开发者 Swagger 仍可通过 /api/docs 访问 */}
            <Tooltip title="使用文档与操作指南（新标签页）">
              <Button
                type="text"
                className="header-icon-btn"
                style={{ color: '#0284c7' }}
                icon={<QuestionCircleOutlined style={{ fontSize: 16 }} />}
                onClick={() => window.open('/docs', '_blank')}
              />
            </Tooltip>

            <div className="header-divider-v" />

            {/* 用户下拉菜单 */}
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight" trigger={['click']}>
              <div className="user-dropdown-trigger">
                <Avatar
                  style={{
                    background: 'linear-gradient(135deg, #38bdf8 0%, #0284c7 100%)',
                    border: '1.5px solid rgba(255, 255, 255, 0.6)',
                    flexShrink: 0,
                    fontWeight: 700,
                    fontSize: 13,
                    color: '#ffffff',
                  }}
                  size={28}
                >
                  {user?.full_name?.[0] || user?.username?.[0]?.toUpperCase() || 'U'}
                </Avatar>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}>
                  <span className="user-name-text">
                    {user?.full_name || user?.username || '用户'}
                  </span>
                  {(user?.full_name || user?.username) && (user?.full_name || user?.username) !== roleLabel(user?.role) && (
                    <span className="user-role-badge">
                      {roleLabel(user?.role)}
                    </span>
                  )}
                  <DownOutlined style={{ fontSize: 10, color: 'rgba(255, 255, 255, 0.6)', marginLeft: 2 }} />
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

      <Modal
        title="个人信息"
        open={profileOpen}
        onCancel={() => setProfileOpen(false)}
        footer={null}
        width={480}
        destroyOnHidden
      >
        <Descriptions column={1} size="small" bordered style={{ marginBottom: 20 }}>
          <Descriptions.Item label="用户名">{user?.username || '-'}</Descriptions.Item>
          <Descriptions.Item label="姓名">{user?.full_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="邮箱">{user?.email || '-'}</Descriptions.Item>
          <Descriptions.Item label="角色">{roleLabel(user?.role)}</Descriptions.Item>
        </Descriptions>

        <div style={{ fontWeight: 600, marginBottom: 12 }}>修改密码</div>
        <Form form={pwdForm} layout="vertical">
          <Form.Item
            label="当前密码"
            name="old_password"
            rules={[{ required: true, message: '请输入当前密码' }]}
          >
            <Input.Password placeholder="请输入当前密码" autoComplete="current-password" />
          </Form.Item>
          <Form.Item
            label="新密码"
            name="new_password"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 6, message: '密码至少 6 位' },
            ]}
          >
            <Input.Password placeholder="至少 6 位" autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            label="确认新密码"
            name="confirm_password"
            dependencies={['new_password']}
            rules={[
              { required: true, message: '请再次输入新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('new_password') === value) return Promise.resolve()
                  return Promise.reject(new Error('两次输入的新密码不一致'))
                },
              }),
            ]}
          >
            <Input.Password placeholder="再次输入新密码" autoComplete="new-password" />
          </Form.Item>
          <Button type="primary" loading={pwdSaving} onClick={handleChangePassword} block>
            确认修改
          </Button>
        </Form>
      </Modal>
    </Layout>
  )
}
