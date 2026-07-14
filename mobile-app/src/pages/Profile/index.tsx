import React from 'react'
import {
  NavBar,
  List,
  Avatar,
  Button,
  Dialog,
  Toast,
  Badge,
} from 'antd-mobile'
import {
  UserOutline,
  SetOutline,
  FileOutline,
  QuestionCircleOutline,
  CloseOutline,
  RightOutline,
} from 'antd-mobile-icons'
import { useAuthStore } from '../../stores/auth'
import './style.css'

const Profile: React.FC = () => {
  const { user, logout } = useAuthStore()

  const handleLogout = () => {
    Dialog.confirm({
      title: '退出登录',
      content: '确定要退出登录吗？',
      onConfirm: () => {
        logout()
        Toast.show({
          icon: 'success',
          content: '已退出登录',
        })
      },
    })
  }

  const menuItems = [
    {
      key: 'history',
      icon: <FileOutline />,
      title: '检查历史',
      badge: 0,
    },
    {
      key: 'settings',
      icon: <SetOutline />,
      title: '设置',
      badge: 0,
    },
    {
      key: 'help',
      icon: <QuestionCircleOutline />,
      title: '帮助与反馈',
      badge: 0,
    },
  ]

  return (
    <div className="profile-page">
      <NavBar back={null} className="profile-nav">
        我的
      </NavBar>

      <div className="profile-content">
        {/* 用户信息卡片 */}
        <div className="user-card">
          <Avatar
            src=""
            className="user-avatar"
            fallback={<UserOutline />}
          />
          <div className="user-info">
            <h3 className="user-name">{user?.real_name || user?.username || '未登录'}</h3>
            <p className="user-role">
              {user?.role === 'admin' ? '系统管理员' : '检查专家'}
            </p>
          </div>
        </div>

        {/* 统计信息 */}
        <div className="stats-card">
          <div className="stat-item">
            <span className="stat-value">12</span>
            <span className="stat-label">本月检查</span>
          </div>
          <div className="stat-divider" />
          <div className="stat-item">
            <span className="stat-value">98%</span>
            <span className="stat-label">合规率</span>
          </div>
          <div className="stat-divider" />
          <div className="stat-item">
            <span className="stat-value">156</span>
            <span className="stat-label">累计检查</span>
          </div>
        </div>

        {/* 功能菜单 */}
        <List className="menu-list">
          {menuItems.map((item) => (
            <List.Item
              key={item.key}
              prefix={item.icon}
              arrow={<RightOutline />}
              onClick={() => {
                Toast.show({
                  content: '功能开发中',
                })
              }}
            >
              {item.title}
              {item.badge > 0 && (
                <Badge content={item.badge} className="menu-badge" />
              )}
            </List.Item>
          ))}
        </List>

        {/* 版本信息 */}
        <div className="version-info">
          <p>现场检查助手 v1.0.0</p>
          <p>© 2024 专家现场工作辅助系统</p>
        </div>

        {/* 退出登录 */}
        <Button
          block
          className="logout-btn"
          onClick={handleLogout}
        >
          <CloseOutline /> 退出登录
        </Button>
      </div>
    </div>
  )
}

export default Profile
