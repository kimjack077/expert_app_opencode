import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Image, Tooltip } from 'antd'
import {
  RightOutlined,
  ExportOutlined,
  CalendarOutlined,
  UserOutlined,
  InfoCircleOutlined,
  BulbOutlined,
  WarningOutlined,
  ArrowLeftOutlined,
  ArrowRightOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'
import { DocArticle } from '../types'

interface DocsContentProps {
  article: DocArticle
  categoryTitle: string
  prevArticle?: DocArticle
  nextArticle?: DocArticle
  onSelectArticle: (articleId: string) => void
}

export const DocsContent: React.FC<DocsContentProps> = ({
  article,
  categoryTitle,
  prevArticle,
  nextArticle,
  onSelectArticle,
}) => {
  const navigate = useNavigate()

  const handleOpenFeature = () => {
    if (article.routeLink) {
      navigate(article.routeLink)
    }
  }

  return (
    <main className="docs-content-container">
      <article className="docs-article">
        {/* 面包屑导航 */}
        <div className="docs-breadcrumb">
          <span className="docs-breadcrumb-item" style={{ cursor: 'pointer' }} onClick={() => onSelectArticle('overview')}>
            在线使用文档
          </span>
          <RightOutlined style={{ fontSize: 10 }} />
          <span className="docs-breadcrumb-item">{categoryTitle}</span>
          <RightOutlined style={{ fontSize: 10 }} />
          <span className="docs-breadcrumb-item" style={{ color: '#0f172a', fontWeight: 600 }}>
            {article.title}
          </span>
        </div>

        {/* 文章头部 */}
        <header className="docs-article-header">
          <div className="docs-article-title-row">
            <h1 className="docs-article-h1">{article.title}</h1>
            {article.badge && (
              <span className="docs-article-badge">{article.badge}</span>
            )}
          </div>

          <div className="docs-article-meta">
            {article.updatedAt && (
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <CalendarOutlined /> 更新于：{article.updatedAt}
              </span>
            )}
            {article.author && (
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <UserOutlined /> 编撰：{article.author}
              </span>
            )}
            {article.routeLink && (
              <Tooltip title={`直达系统页面: ${article.routeLink}`}>
                <button
                  type="button"
                  className="docs-btn-feature-jump"
                  onClick={handleOpenFeature}
                >
                  <span>{article.actionText || '在系统中打开此功能'}</span>
                  <ExportOutlined style={{ fontSize: 12 }} />
                </button>
              </Tooltip>
            )}
          </div>

          {article.intro && (
            <div className="docs-article-intro">
              {article.intro}
            </div>
          )}
        </header>

        {/* 章节正文 */}
        <div className="docs-article-body">
          {article.sections.map((section) => (
            <section key={section.id} id={section.id} className="docs-section">
              <h2 className="docs-section-h2">{section.title}</h2>

              {section.content && (
                <p className="docs-section-desc">{section.content}</p>
              )}

              {/* 核心要点列表 */}
              {section.keyPoints && section.keyPoints.length > 0 && (
                <div className="docs-keypoints-box">
                  {section.keyPoints.map((point, idx) => (
                    <div key={idx} className="docs-keypoint-item">
                      {point}
                    </div>
                  ))}
                </div>
              )}

              {/* 步骤指引卡片 */}
              {section.steps && section.steps.length > 0 && (
                <div className="docs-steps-container">
                  {section.steps.map((step, idx) => (
                    <div key={idx} className="docs-step-card">
                      <div className="docs-step-num">{idx + 1}</div>
                      <div className="docs-step-body">
                        <div className="docs-step-title">{step.title}</div>
                        <div className="docs-step-desc">{step.desc}</div>
                        {step.tip && (
                          <div style={{ marginTop: 6, fontSize: 13, color: '#0369a1' }}>
                            💡 {step.tip}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* 高保真截图展示窗 */}
              {section.image && (
                <div className="docs-screenshot-frame">
                  <div className="docs-screenshot-header">
                    <div className="docs-window-dots">
                      <span className="docs-window-dot red" />
                      <span className="docs-window-dot yellow" />
                      <span className="docs-window-dot green" />
                    </div>
                    <span className="docs-window-title">易审通 · 界面实操截图</span>
                  </div>
                  <div className="docs-screenshot-img-box">
                    <Image
                      src={section.image.src}
                      alt={section.image.caption}
                      className="docs-screenshot-img"
                      preview={{
                        mask: '点击查看高清大图',
                      }}
                    />
                  </div>
                  <div className="docs-screenshot-caption">
                    📷 {section.image.caption}
                  </div>
                </div>
              )}

              {/* 提示卡片 */}
              {section.callout && (
                <div className={`docs-callout ${section.callout.type}`}>
                  <div className="docs-callout-header">
                    {section.callout.type === 'tip' && <BulbOutlined />}
                    {section.callout.type === 'info' && <InfoCircleOutlined />}
                    {section.callout.type === 'warning' && <WarningOutlined />}
                    <span>{section.callout.title}</span>
                  </div>
                  <div>{section.callout.content}</div>
                </div>
              )}
            </section>
          ))}
        </div>

        {/* 底部上一篇 / 下一篇卡片 */}
        <footer className="docs-article-footer">
          {prevArticle ? (
            <div
              className="docs-footer-nav-card"
              onClick={() => onSelectArticle(prevArticle.id)}
            >
              <span className="docs-footer-nav-direction">
                <ArrowLeftOutlined /> 上一篇
              </span>
              <span className="docs-footer-nav-title">{prevArticle.title}</span>
            </div>
          ) : (
            <div style={{ flex: 1 }} />
          )}

          {nextArticle && (
            <div
              className="docs-footer-nav-card"
              style={{ textAlign: 'right', alignItems: 'flex-end' }}
              onClick={() => onSelectArticle(nextArticle.id)}
            >
              <span className="docs-footer-nav-direction">
                下一篇 <ArrowRightOutlined />
              </span>
              <span className="docs-footer-nav-title">{nextArticle.title}</span>
            </div>
          )}
        </footer>
      </article>
    </main>
  )
}
