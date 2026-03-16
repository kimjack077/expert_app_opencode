import React from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { TabBar } from 'antd-mobile'
import {
  UnorderedListOutline,
  ScanningOutline,
  UserOutline,
} from 'antd-mobile-icons'
import './style.css'

const BottomNav: React.FC = () => {
  const location = useLocation()
  const navigate = useNavigate()

  const tabs = [
    {
      key: '/tasks',
      title: '任务',
      icon: <UnorderedListOutline />,
    },
    {
      key: '/quick-check',
      title: '快速检查',
      icon: <ScanningOutline />,
    },
    {
      key: '/profile',
      title: '我的',
      icon: <UserOutline />,
    },
  ]

  const activeKey = tabs.find(tab => location.pathname.startsWith(tab.key))?.key || '/tasks'

  return (
    <div className="bottom-nav">
      <TabBar
        activeKey={activeKey}
        onChange={(key) => navigate(key)}
        safeArea
      >
        {tabs.map(tab => (
          <TabBar.Item
            key={tab.key}
            icon={tab.icon}
            title={tab.title}
          />
        ))}
      </TabBar>
    </div>
  )
}

export default BottomNav
