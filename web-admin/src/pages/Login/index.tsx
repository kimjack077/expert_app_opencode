import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Form, Input, Button, Checkbox, Segmented, message } from 'antd'
import {
  SafetyCertificateFilled,
  UserOutlined,
  LockOutlined,
  RobotOutlined,
  FileProtectOutlined,
  BarChartOutlined,
  ArrowRightOutlined,
  CheckCircleFilled,
  CrownOutlined,
  AuditOutlined,
  GlobalOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/stores/auth'
import { EasyAuditLogo, EasyAuditLogoIcon } from '@/components/brand/EasyAuditLogo'
import { applyRememberChoice } from '@/utils/sessionGuard'
import './Login.css'

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const login = useAuthStore((state) => state.login)
  const [loading, setLoading] = useState(false)
  const [selectedRole, setSelectedRole] = useState<'admin' | 'expert' | 'custom'>('admin')
  const [form] = Form.useForm()

  const onFinish = async (values: { username: string; password: string; remember?: boolean }) => {
    setLoading(true)
    try {
      await login(values.username, values.password)
      applyRememberChoice(values.remember !== false)
      message.success('登录成功，正在进入系统...')
      // 登录前被拦截的页面（如分享出来的项目链接）登录后直接回到原页面
      const from = (location.state as any)?.from
      const target = from?.pathname && from.pathname !== '/login' ? `${from.pathname}${from.search || ''}` : '/dashboard'
      navigate(target, { replace: true })
    } catch (error: any) {
      message.error(error.response?.data?.detail || error.response?.data?.message || '登录失败，请检查用户名和密码')
    } finally {
      setLoading(false)
    }
  }

  const handleRoleChange = (value: string | number) => {
    const role = value as 'admin' | 'expert' | 'custom'
    setSelectedRole(role)
    if (role === 'admin') {
      form.setFieldsValue({ username: 'admin', password: 'admin123' })
    } else if (role === 'expert') {
      form.setFieldsValue({ username: 'expert', password: 'expert123' })
    } else {
      form.resetFields()
    }
  }

  const quickLogin = (username: string, password: string, role: 'admin' | 'expert') => {
    setSelectedRole(role)
    form.setFieldsValue({ username, password })
    form.submit()
  }

  return (
    <div className="efis-login-page">
      {/* 左侧 Hero 品牌展示面板 */}
      <div className="efis-hero-panel">
        <div className="efis-grid-pattern" />

        <div className="efis-hero-content">
          {/* 系统标识 Badge */}
          <div className="efis-brand-badge">
            <span className="efis-brand-badge-icon">
              <EasyAuditLogoIcon size={18} />
            </span>
            <span>易审通 · EasyAudit SaaS Cloud</span>
          </div>

          {/* 标题 & 副标 */}
          <h1 className="efis-hero-title">
            让每一次审核
            <br />
            <span className="efis-gradient-text">都变得简单高效</span>
          </h1>

          <p className="efis-hero-desc">
            新一代认证审核与现场评审智能云平台。专为认证机构、审核员与评审专家打造，深度融合智审 Agent、标准知识库、首末次会议管理与一键合规成果交付。
          </p>

          {/* 核心能力亮点卡片 */}
          <div className="efis-feature-cards">
            <div className="efis-feature-card">
              <div className="efis-feature-icon-box efis-icon-ai">
                <RobotOutlined />
              </div>
              <div className="efis-feature-info">
                <h4>
                  <span>智审 Agent 现场辅助</span>
                  <CheckCircleFilled style={{ color: '#38bdf8', fontSize: 13 }} />
                </h4>
                <p>内置标准规程 RAG 检索、首末次会议纪要生成与现场证据链智能研判</p>
              </div>
            </div>

            <div className="efis-feature-card">
              <div className="efis-feature-icon-box efis-icon-shield">
                <FileProtectOutlined />
              </div>
              <div className="efis-feature-info">
                <h4>
                  <span>多模态证据链与质量门禁</span>
                  <CheckCircleFilled style={{ color: '#4ade80', fontSize: 13 }} />
                </h4>
                <p>现场照片智能打标、客观事实结构化留痕，执行多重要素质量门禁把关</p>
              </div>
            </div>

            <div className="efis-feature-card">
              <div className="efis-feature-icon-box efis-icon-report">
                <BarChartOutlined />
              </div>
              <div className="efis-feature-info">
                <h4>
                  <span>智能报告与成果一键交付</span>
                  <CheckCircleFilled style={{ color: '#fbbf24', fontSize: 13 }} />
                </h4>
                <p>一键生成合规审核报告、不符合项清单与完整交付归档包</p>
              </div>
            </div>
          </div>
        </div>

        {/* 底部系统状态 */}
        <div className="efis-hero-footer">
          <div className="efis-status-indicator">
            <span className="efis-pulse-dot" />
            <span>核心服务在线 · 数据库正常联机</span>
          </div>
          <div style={{ display: 'flex', gap: 16 }}>
            <span>安全加密: TLS 1.3 / AES-256</span>
            <span>系统版本: v2.4 SaaS Pro</span>
          </div>
        </div>
      </div>

      {/* 右侧登录表单面板 */}
      <div className="efis-auth-panel">
        <div className="efis-auth-card">
          {/* 表单头部 */}
          <div className="efis-auth-header">
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 14 }}>
              <EasyAuditLogo size={40} showText={true} direction="horizontal" textColor="#0f172a" subTextColor="#64748b" />
            </div>
            <h2 className="efis-auth-title">欢迎登录 易审通</h2>
            <p className="efis-auth-subtitle">EasyAudit 认证审核与现场评审智能云平台 · 管理控制台</p>
          </div>

          {/* 角色快捷分段选择器 */}
          <Segmented
            className="efis-role-selector"
            block
            value={selectedRole}
            onChange={handleRoleChange}
            options={[
              {
                label: '管理员',
                value: 'admin',
                icon: <CrownOutlined />,
              },
              {
                label: '审核专家',
                value: 'expert',
                icon: <AuditOutlined />,
              },
              {
                label: '其他账号',
                value: 'custom',
                icon: <UserOutlined />,
              },
            ]}
          />

          {/* 登录表单 */}
          <Form
            form={form}
            name="efis_login"
            initialValues={{
              username: 'admin',
              password: 'admin123',
              remember: true,
            }}
            onFinish={onFinish}
            autoComplete="off"
            layout="vertical"
          >
            {/* Form.Item 必须直接包裹输入控件，否则 value/onChange 注入到 div 上，手动输入无法入表单 */}
            <div style={{ marginBottom: 18 }}>
              <label className="efis-input-label">账号 / 用户名</label>
              <Form.Item
                name="username"
                rules={[{ required: true, message: '请输入用户名' }]}
                style={{ marginBottom: 0 }}
              >
                <Input
                  prefix={<UserOutlined className="efis-input-icon" />}
                  placeholder="请输入用户名"
                  className="efis-input-wrapper"
                  size="large"
                />
              </Form.Item>
            </div>

            <div style={{ marginBottom: 18 }}>
              <label className="efis-input-label">登录密码</label>
              <Form.Item
                name="password"
                rules={[{ required: true, message: '请输入登录密码' }]}
                style={{ marginBottom: 0 }}
              >
                <Input.Password
                  prefix={<LockOutlined className="efis-input-icon" />}
                  placeholder="请输入密码"
                  className="efis-input-wrapper"
                  size="large"
                />
              </Form.Item>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 24,
              }}
            >
              <Form.Item name="remember" valuePropName="checked" noStyle>
                <Checkbox style={{ color: '#94a3b8', fontSize: 13 }}>记住登录状态</Checkbox>
              </Form.Item>
              <a
                href="#"
                onClick={(e) => {
                  e.preventDefault()
                  message.info('请联系系统超级管理员 (admin) 重置密码')
                }}
                style={{ color: '#38bdf8', fontSize: 13, textDecoration: 'none' }}
              >
                忘记密码？
              </a>
            </div>

            <Form.Item style={{ marginBottom: 0 }}>
              <Button
                type="primary"
                htmlType="submit"
                block
                loading={loading}
                className="efis-submit-btn"
              >
                <span>立即登录</span>
                <ArrowRightOutlined />
              </Button>
            </Form.Item>
          </Form>

          {/* 快捷登录卡片 */}
          <div className="efis-quick-login-box">
            <div className="efis-quick-header">快捷体验账号</div>
            <div className="efis-quick-chips">
              <button
                type="button"
                className="efis-quick-chip"
                onClick={() => quickLogin('admin', 'admin123', 'admin')}
              >
                <div className="efis-chip-avatar efis-chip-admin">
                  <CrownOutlined />
                </div>
                <div className="efis-chip-info">
                  <div className="chip-name">管理员</div>
                  <div className="chip-account">admin / admin123</div>
                </div>
              </button>

              <button
                type="button"
                className="efis-quick-chip"
                onClick={() => quickLogin('expert', 'expert123', 'expert')}
              >
                <div className="efis-chip-avatar efis-chip-expert">
                  <AuditOutlined />
                </div>
                <div className="efis-chip-info">
                  <div className="chip-name">审核专家</div>
                  <div className="chip-account">expert / expert123</div>
                </div>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
