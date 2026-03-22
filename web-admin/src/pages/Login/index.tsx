import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Form, Input, Button, Checkbox, message } from 'antd'
import {
  SafetyCertificateOutlined,
  UserOutlined,
  LockOutlined,
  FieldTimeOutlined,
  TeamOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/stores/auth'

export default function Login() {
  const navigate = useNavigate()
  const login = useAuthStore((state) => state.login)
  const [loading, setLoading] = useState(false)
  const [form] = Form.useForm()

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      await login(values.username, values.password)
      message.success('登录成功')
      navigate('/dashboard')
    } catch (error: any) {
      message.error(error.response?.data?.detail || '登录失败，请检查用户名和密码')
    } finally {
      setLoading(false)
    }
  }

  const quickLogin = (username: string, password: string) => {
    form.setFieldsValue({ username, password })
    form.submit()
  }

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden' }}>
      {/* 左侧视觉区域 */}
      <div
        style={{
          flex: '0 0 58.33%',
          position: 'relative',
          overflow: 'hidden',
          background: '#0b1c30',
          display: 'flex',
        }}
        className="login-left-panel"
      >
        {/* 背景渐变 */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background:
              'linear-gradient(135deg, rgba(11,28,48,0.85) 0%, rgba(0,102,137,0.4) 50%, rgba(28,169,223,0.2) 100%)',
            zIndex: 1,
          }}
        />
        {/* 装饰图案 */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            zIndex: 0,
            opacity: 0.08,
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          }}
        />
        {/* 内容 */}
        <div
          style={{
            position: 'relative',
            zIndex: 2,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            padding: 64,
            width: '100%',
          }}
        >
          {/* 顶部Logo */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 48 }}>
              <div
                style={{
                  width: 40,
                  height: 40,
                  background: '#1ca9df',
                  borderRadius: 8,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <SafetyCertificateOutlined style={{ fontSize: 20, color: '#fff' }} />
              </div>
              <span
                style={{
                  fontSize: 22,
                  fontWeight: 900,
                  color: '#fff',
                  letterSpacing: '-0.02em',
                }}
              >
                专家现场工作辅助系统
              </span>
            </div>
            <div style={{ maxWidth: 520 }}>
              <h1
                style={{
                  fontSize: '3rem',
                  lineHeight: 1.15,
                  fontWeight: 800,
                  color: '#fff',
                  marginBottom: 24,
                  letterSpacing: '-0.02em',
                }}
              >
                企业现场
                <br />
                <span style={{ color: '#1ca9df' }}>检查管理平台</span>
              </h1>
              <p
                style={{
                  fontSize: 17,
                  color: 'rgba(255,255,255,0.7)',
                  fontWeight: 400,
                  maxWidth: 420,
                  lineHeight: 1.7,
                }}
              >
                面向专家审查员的专业级现场检查系统，支持检查模板管理、任务分配、现场记录与智能分析。
              </p>
            </div>
          </div>
          {/* 底部数据 */}
          <div style={{ display: 'flex', gap: 48 }}>
            <div>
              <div style={{ color: '#fff', fontSize: 28, fontWeight: 700, letterSpacing: '-0.02em' }}>
                v1.0.0
              </div>
              <div
                style={{
                  fontSize: 11,
                  textTransform: 'uppercase',
                  letterSpacing: '0.1em',
                  fontWeight: 600,
                  color: 'rgba(255,255,255,0.45)',
                  marginTop: 4,
                }}
              >
                系统版本
              </div>
            </div>
            <div>
              <div style={{ color: '#fff', fontSize: 28, fontWeight: 700, letterSpacing: '-0.02em' }}>
                多角色
              </div>
              <div
                style={{
                  fontSize: 11,
                  textTransform: 'uppercase',
                  letterSpacing: '0.1em',
                  fontWeight: 600,
                  color: 'rgba(255,255,255,0.45)',
                  marginTop: 4,
                }}
              >
                权限管理
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 右侧登录表单 */}
      <div
        style={{
          flex: '0 0 41.67%',
          background: '#eff4ff',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          padding: '0 96px',
          position: 'relative',
        }}
        className="login-right-panel"
      >
        <div style={{ width: '100%', maxWidth: 400 }}>
          {/* 标题 */}
          <div style={{ marginBottom: 48 }}>
            <h2
              style={{
                fontSize: 22,
                fontWeight: 700,
                color: '#0b1c30',
                marginBottom: 8,
              }}
            >
              专家检查系统
            </h2>
            <p style={{ color: '#3e484f', fontSize: 14, fontWeight: 500, margin: 0 }}>
              请登录以访问检查管理平台
            </p>
          </div>

          {/* 登录表单 */}
          <Form
            form={form}
            name="login"
            onFinish={onFinish}
            autoComplete="off"
            size="large"
          >
            <Form.Item
              name="username"
              rules={[{ required: true, message: '请输入用户名' }]}
              style={{ marginBottom: 24 }}
            >
              <div>
                <label
                  style={{
                    fontSize: 11,
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em',
                    fontWeight: 700,
                    color: '#6e7980',
                    display: 'block',
                    marginBottom: 4,
                  }}
                >
                  用户名
                </label>
                <Input
                  prefix={<UserOutlined style={{ color: '#bdc8d0', marginRight: 8 }} />}
                  placeholder="请输入用户名"
                  bordered={false}
                  style={{
                    borderBottom: '2px solid #bdc8d0',
                    borderRadius: 0,
                    padding: '8px 0',
                    fontSize: 15,
                    color: '#0b1c30',
                  }}
                  className="login-input"
                />
              </div>
            </Form.Item>

            <Form.Item
              name="password"
              rules={[{ required: true, message: '请输入密码' }]}
              style={{ marginBottom: 24 }}
            >
              <div>
                <label
                  style={{
                    fontSize: 11,
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em',
                    fontWeight: 700,
                    color: '#6e7980',
                    display: 'block',
                    marginBottom: 4,
                  }}
                >
                  密码
                </label>
                <Input.Password
                  prefix={<LockOutlined style={{ color: '#bdc8d0', marginRight: 8 }} />}
                  placeholder="请输入密码"
                  bordered={false}
                  style={{
                    borderBottom: '2px solid #bdc8d0',
                    borderRadius: 0,
                    padding: '8px 0',
                    fontSize: 15,
                  }}
                  className="login-input"
                />
              </div>
            </Form.Item>

            {/* 记住我 & 忘记密码 */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 32,
              }}
            >
              <Checkbox
                style={{
                  fontSize: 14,
                  fontWeight: 500,
                  color: '#3e484f',
                }}
              >
                记住我
              </Checkbox>
              <a
                href="#"
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: '#006689',
                  textDecoration: 'none',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = '#1ca9df')}
                onMouseLeave={(e) => (e.currentTarget.style.color = '#006689')}
              >
                忘记密码？
              </a>
            </div>

            {/* 登录按钮 */}
            <Form.Item style={{ marginBottom: 0 }}>
              <Button
                type="primary"
                htmlType="submit"
                block
                loading={loading}
                style={{
                  height: 52,
                  fontSize: 16,
                  fontWeight: 700,
                  borderRadius: 12,
                  background: 'linear-gradient(135deg, #006689 0%, #1ca9df 100%)',
                  border: 'none',
                  boxShadow: '0 8px 24px rgba(0,102,137,0.25)',
                  letterSpacing: '0.02em',
                }}
                className="login-btn"
              >
                登录系统
              </Button>
            </Form.Item>
          </Form>

          {/* 快速登录 */}
          <div
            style={{
              marginTop: 64,
              paddingTop: 32,
              borderTop: '1px solid rgba(110,121,128,0.15)',
            }}
          >
            <p
              style={{
                fontSize: 11,
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                fontWeight: 700,
                color: '#6e7980',
                marginBottom: 16,
                textAlign: 'center',
              }}
            >
              快速登录
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <button
                onClick={() => quickLogin('admin', 'admin123')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: 12,
                  borderRadius: 12,
                  background: '#fff',
                  border: '1px solid rgba(110,121,128,0.1)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.2s',
                }}
                className="quick-login-btn"
              >
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: '50%',
                    background: 'rgba(195,192,255,0.3)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  <TeamOutlined style={{ fontSize: 16, color: '#0f0069' }} />
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#0b1c30' }}>管理员</div>
                  <div style={{ fontSize: 11, color: '#3e484f' }}>admin / admin123</div>
                </div>
              </button>
              <button
                onClick={() => quickLogin('expert', 'expert123')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: 12,
                  borderRadius: 12,
                  background: '#fff',
                  border: '1px solid rgba(110,121,128,0.1)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.2s',
                }}
                className="quick-login-btn"
              >
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: '50%',
                    background: 'rgba(255,182,144,0.3)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  <FieldTimeOutlined style={{ fontSize: 16, color: '#5c2400' }} />
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#0b1c30' }}>检查专家</div>
                  <div style={{ fontSize: 11, color: '#3e484f' }}>expert / expert123</div>
                </div>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
