// 必须最先执行：处理「未勾选记住登录状态」时的会话清理（早于登录态水合）
import './utils/sessionGuard'
import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider, App as AntApp } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#4f46e5',
          colorInfo: '#4f46e5',
          borderRadius: 8,
          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
          colorBgContainer: '#ffffff',
          colorBgLayout: '#f8fafc',
        },
        components: {
          Card: {
            headerBg: '#fafafa',
          },
          Button: {
            borderRadius: 6,
          },
          Table: {
            headerBg: '#f8fafc',
            headerColor: '#64748b',
          }
        }
      }}
    >
      <AntApp>
        <App />
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>
)
