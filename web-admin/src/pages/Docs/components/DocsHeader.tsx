import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Tooltip } from 'antd'
import {
  SearchOutlined,
  HomeOutlined,
  BookOutlined,
  CompassOutlined,
} from '@ant-design/icons'
import { EasyAuditLogoIcon } from '@/components/brand/EasyAuditLogo'

interface DocsHeaderProps {
  onOpenSearch: () => void
}

export const DocsHeader: React.FC<DocsHeaderProps> = ({ onOpenSearch }) => {
  const navigate = useNavigate()

  return (
    <header className="docs-header">
      <div className="docs-header-left">
        <div className="docs-brand-logo" onClick={() => navigate('/docs')}>
          <EasyAuditLogoIcon size={30} />
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="docs-brand-title">易审通</span>
              <span className="docs-brand-badge">在线文档</span>
            </div>
          </div>
        </div>
      </div>

      <div className="docs-header-center">
        <div className="docs-search-trigger" onClick={onOpenSearch}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <SearchOutlined style={{ fontSize: 14, color: '#94a3b8' }} />
            <span>搜索文档、模块或操作步骤...</span>
          </div>
          <span className="docs-search-kbd">
            <kbd>Ctrl</kbd> + <kbd>K</kbd>
          </span>
        </div>
      </div>

      <div className="docs-header-right">
        <Tooltip title="浏览平台核心业务链路">
          <Button
            type="text"
            icon={<CompassOutlined />}
            style={{ color: '#475569' }}
            onClick={() => navigate('/docs/quickstart')}
          >
            快速上手
          </Button>
        </Tooltip>

        <Button
          type="primary"
          className="docs-btn-back"
          icon={<HomeOutlined />}
          onClick={() => navigate('/dashboard')}
        >
          返回系统工作台
        </Button>
      </div>
    </header>
  )
}
