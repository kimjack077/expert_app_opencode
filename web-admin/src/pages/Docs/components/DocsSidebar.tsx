import React, { useState } from 'react'
import { RightOutlined } from '@ant-design/icons'
import { DocCategory } from '../types'

interface DocsSidebarProps {
  categories: DocCategory[]
  activeArticleId: string
  onSelectArticle: (articleId: string) => void
}

export const DocsSidebar: React.FC<DocsSidebarProps> = ({
  categories,
  activeArticleId,
  onSelectArticle,
}) => {
  // 默认所有分类全部展开
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({})

  const toggleGroup = (categoryId: string) => {
    setCollapsedGroups((prev) => ({
      ...prev,
      [categoryId]: !prev[categoryId],
    }))
  }

  return (
    <aside className="docs-sidebar">
      {categories.map((category) => {
        const isCollapsed = collapsedGroups[category.id]
        return (
          <div key={category.id} className="docs-nav-group">
            <div
              className="docs-nav-group-header"
              onClick={() => toggleGroup(category.id)}
            >
              <div className="docs-nav-group-title">
                <span>{category.title}</span>
              </div>
              <RightOutlined
                className={`docs-nav-group-caret ${!isCollapsed ? 'expanded' : ''}`}
              />
            </div>

            {!isCollapsed && (
              <div className="docs-nav-items-wrapper">
                {category.articles.map((article) => {
                  const isActive = article.id === activeArticleId
                  return (
                    <div
                      key={article.id}
                      className={`docs-nav-item ${isActive ? 'active' : ''}`}
                      onClick={() => onSelectArticle(article.id)}
                    >
                      <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {article.title}
                      </span>
                      {article.badge && (
                        <span className="docs-nav-item-badge">{article.badge}</span>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}
    </aside>
  )
}
