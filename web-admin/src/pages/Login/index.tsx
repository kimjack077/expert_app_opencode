import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Form, Input, Button, message, Divider } from 'antd'
import { UserOutlined, LockOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { useAuthStore } from '@/stores/auth'

export default function Login() {
  const navigate = useNavigate()
  const login = useAuthStore((state) => state.login)
  const [loading, setLoading] = useState(false)

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

  return (
    <div className="login-container">
      <div className="login-card">
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 64,
            height: 64,
            margin: '0 auto 16px',
            background: 'linear-gradient(135deg, var(--primary-color) 0%, var(--accent-color) 100%)',
            borderRadius: 16,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 8px 16px rgba(100, 116, 139, 0.3)',
          }}>
            <SafetyCertificateOutlined style={{ fontSize: 32, color: 'white' }} />
          </div>
          <h1 className="login-title" style={{ marginBottom: 8 }}>专家现场工作辅助系统</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: 0 }}>
            Enterprise Field Inspection System
          </p>
        </div>

        <Form
          name="login"
          onFinish={onFinish}
          autoComplete="off"
          size="large"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input 
              prefix={<UserOutlined style={{ color: 'var(--text-light)' }} />} 
              placeholder="用户名" 
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password 
              prefix={<LockOutlined style={{ color: 'var(--text-light)' }} />} 
              placeholder="密码" 
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 16 }}>
            <Button 
              type="primary" 
              htmlType="submit" 
              block 
              loading={loading}
              style={{ 
                height: 48,
                fontSize: 16,
                fontWeight: 600,
              }}
            >
              登录
            </Button>
          </Form.Item>
        </Form>

        <Divider style={{ margin: '24px 0', color: 'var(--text-light)', fontSize: 12 }}>
          演示账号
        </Divider>

        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: '1fr 1fr', 
          gap: 12,
        }}>
          <div style={{
            background: 'linear-gradient(135deg, rgba(100, 116, 139, 0.06) 0%, rgba(249, 115, 22, 0.06) 100%)',
            padding: '12px 16px',
            borderRadius: 8,
            border: '1px solid var(--border-color)',
          }}>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>管理员</div>
            <div style={{ fontSize: 13, color: 'var(--text-main)', fontWeight: 500 }}>
              admin / admin123
            </div>
          </div>
          <div style={{
            background: 'linear-gradient(135deg, rgba(100, 116, 139, 0.06) 0%, rgba(249, 115, 22, 0.06) 100%)',
            padding: '12px 16px',
            borderRadius: 8,
            border: '1px solid var(--border-color)',
          }}>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>专家</div>
            <div style={{ fontSize: 13, color: 'var(--text-main)', fontWeight: 500 }}>
              expert / expert123
            </div>
          </div>
        </div>

        <div style={{ 
          marginTop: 24, 
          textAlign: 'center',
          color: 'var(--text-light)',
          fontSize: 12,
        }}>
          <p style={{ margin: 0 }}>企业安全生产检查专家辅助系统</p>
          <p style={{ margin: '4px 0 0' }}>v1.0.0</p>
        </div>
      </div>
    </div>
  )
}
