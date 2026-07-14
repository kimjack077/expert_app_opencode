import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Toast, SpinLoading } from 'antd-mobile'
import { UserOutline, LockOutline } from 'antd-mobile-icons'
import { useAuthStore } from '../../stores/auth'
import { authApi } from '../../services/api'
import './style.css'

// 全局登录函数，供演示账号使用
const doLogin = async (username: string, password: string, setAuth: any, navigate: any) => {
  try {
    const res: any = await authApi.login(username, password)
    if (res.access_token) {
      setAuth(res.access_token, res.user)
      Toast.show({
        icon: 'success',
        content: '登录成功',
      })
      navigate('/tasks')
      return true
    } else {
      Toast.show({
        icon: 'fail',
        content: '登录失败',
      })
      return false
    }
  } catch (error: any) {
    Toast.show({
      icon: 'fail',
      content: error.response?.data?.detail || '网络错误',
    })
    return false
  }
}

const Login: React.FC = () => {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const { setAuth } = useAuthStore()

  // 暴露登录函数到全局
  useEffect(() => {
    (window as any).doDemoLogin = () => {
      setUsername('admin')
      setPassword('admin123')
      return doLogin('admin', 'admin123', setAuth, navigate)
    }
  }, [setAuth, navigate])

  const handleLogin = async () => {
    if (!username || !password) {
      Toast.show({
        icon: 'fail',
        content: '请输入用户名和密码',
      })
      return
    }

    setLoading(true)
    await doLogin(username, password, setAuth, navigate)
    setLoading(false)
  }

  return (
    <div className="login-page">
      <div className="login-header">
        <div className="logo">
          <div className="logo-icon">检</div>
        </div>
        <h1 className="title">现场检查助手</h1>
        <p className="subtitle">专家现场工作辅助系统</p>
      </div>

      <div className="login-form-container">
        <div className="form-group">
          <label className="form-label">
            <UserOutline /> 用户名
          </label>
          <input
            type="text"
            className="form-input"
            placeholder="请输入用户名"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label className="form-label">
            <LockOutline /> 密码
          </label>
          <input
            type="password"
            className="form-input"
            placeholder="请输入密码"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        <Button
          block
          color="primary"
          size="large"
          loading={loading}
          loadingIcon={<SpinLoading color="white" />}
          className="login-btn"
          onClick={handleLogin}
        >
          登 录
        </Button>

        <div className="demo-accounts">
          <p className="demo-title">演示账号</p>
          <div 
            className="demo-item" 
            onClick={() => {
              if ((window as any).doDemoLogin) {
                (window as any).doDemoLogin()
              }
            }}
          >
            <span className="demo-role">专家</span>
            <span className="demo-info">admin / admin123</span>
          </div>
        </div>
      </div>

      <div className="login-footer">
        <p>© 2024 现场检查助手 v1.0</p>
      </div>
    </div>
  )
}

export default Login
