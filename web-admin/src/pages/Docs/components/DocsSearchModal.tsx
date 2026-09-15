import React, { useState, useEffect, useRef } from 'react'
import { Modal, Input } from 'antd'
import { SearchOutlined, FileTextOutlined, ArrowRightOutlined } from '@ant-design/icons'
import { DOCS_CATEGORIES, DOCS_ARTICLES } from '../data/docsContent'
import { SearchResultItem } from '../types'

interface DocsSearchModalProps {
  open: boolean
  onClose: () => void
  onSelectResult: (articleId: string, sectionId?: string) => void
}

export const DocsSearchModal: React.FC<DocsSearchModalProps> = ({
  open,
  onClose,
  onSelectResult,
}) => {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResultItem[]>([])
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<any>(null)

  // 快捷键 Ctrl+K / Cmd+K 监听
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault()
        if (!open) {
          // 在父组件控制
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open])

  // 打开弹窗自动聚焦输入框
  useEffect(() => {
    if (open) {
      setTimeout(() => {
        inputRef.current?.focus()
      }, 100)
    } else {
      setQuery('')
      setResults([])
      setSelectedIndex(0)
    }
  }, [open])

  // 执行搜索
  useEffect(() => {
    const trimmed = query.trim().toLowerCase()
    if (!trimmed) {
      // 默认展示精选推荐
      const defaultRecommendations: SearchResultItem[] = DOCS_ARTICLES.slice(0, 5).map((art) => {
        const cat = DOCS_CATEGORIES.find((c) => c.id === art.category)
        return {
          articleId: art.id,
          articleTitle: art.title,
          categoryTitle: cat ? cat.title : '',
          snippet: art.description,
          matchedKeyword: '',
        }
      })
      setResults(defaultRecommendations)
      setSelectedIndex(0)
      return
    }

    const matched: SearchResultItem[] = []

    for (const article of DOCS_ARTICLES) {
      const cat = DOCS_CATEGORIES.find((c) => c.id === article.category)
      const catTitle = cat ? cat.title : ''

      // 1. 匹配文章标题或描述或关键词
      if (
        article.title.toLowerCase().includes(trimmed) ||
        article.description.toLowerCase().includes(trimmed) ||
        article.keywords.some((k) => k.toLowerCase().includes(trimmed))
      ) {
        matched.push({
          articleId: article.id,
          articleTitle: article.title,
          categoryTitle: catTitle,
          snippet: article.description,
          matchedKeyword: trimmed,
        })
      }

      // 2. 匹配各小节标题或正文或步骤
      for (const sec of article.sections) {
        if (sec.title.toLowerCase().includes(trimmed)) {
          matched.push({
            articleId: article.id,
            articleTitle: article.title,
            categoryTitle: catTitle,
            sectionId: sec.id,
            sectionTitle: sec.title,
            snippet: sec.content || sec.title,
            matchedKeyword: trimmed,
          })
        } else if (sec.content && sec.content.toLowerCase().includes(trimmed)) {
          // 截取匹配点前后文字
          const idx = sec.content.toLowerCase().indexOf(trimmed)
          const start = Math.max(0, idx - 20)
          const end = Math.min(sec.content.length, idx + trimmed.length + 40)
          const snippet = (start > 0 ? '...' : '') + sec.content.slice(start, end) + (end < sec.content.length ? '...' : '')
          matched.push({
            articleId: article.id,
            articleTitle: article.title,
            categoryTitle: catTitle,
            sectionId: sec.id,
            sectionTitle: sec.title,
            snippet,
            matchedKeyword: trimmed,
          })
        } else if (sec.steps) {
          for (const step of sec.steps) {
            if (step.title.toLowerCase().includes(trimmed) || step.desc.toLowerCase().includes(trimmed)) {
              matched.push({
                articleId: article.id,
                articleTitle: article.title,
                categoryTitle: catTitle,
                sectionId: sec.id,
                sectionTitle: sec.title,
                snippet: `${step.title}: ${step.desc.slice(0, 50)}...`,
                matchedKeyword: trimmed,
              })
              break
            }
          }
        }
      }
    }

    setResults(matched.slice(0, 15))
    setSelectedIndex(0)
  }, [query])

  // 键盘上下导航与 Enter 确认
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((prev) => (results.length ? (prev + 1) % results.length : 0))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((prev) => (results.length ? (prev - 1 + results.length) % results.length : 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (results[selectedIndex]) {
        const item = results[selectedIndex]
        onSelectResult(item.articleId, item.sectionId)
        onClose()
      }
    }
  }

  // 高亮文本辅助函数
  const highlightMatch = (text: string, kw: string) => {
    if (!kw) return text
    const parts = text.split(new RegExp(`(${kw})`, 'gi'))
    return (
      <>
        {parts.map((part, i) =>
          part.toLowerCase() === kw.toLowerCase() ? (
            <span key={i} className="docs-search-highlight">
              {part}
            </span>
          ) : (
            part
          )
        )}
      </>
    )
  }

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      closable={false}
      width={640}
      className="docs-search-modal"
      centered
      destroyOnClose
    >
      <div className="docs-search-input-wrapper">
        <SearchOutlined style={{ fontSize: 18, color: '#0284c7' }} />
        <Input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="检索功能、操作步骤或标准规范 (如：审核计划、检查表、AI)..."
          className="docs-search-input"
        />
      </div>

      <div className="docs-search-results-list">
        {results.length > 0 ? (
          results.map((item, index) => {
            const isSelected = index === selectedIndex
            return (
              <div
                key={`${item.articleId}-${item.sectionId || ''}-${index}`}
                className={`docs-search-item ${isSelected ? 'selected' : ''}`}
                onClick={() => {
                  onSelectResult(item.articleId, item.sectionId)
                  onClose()
                }}
                onMouseEnter={() => setSelectedIndex(index)}
              >
                <div className="docs-search-item-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <FileTextOutlined style={{ color: '#0284c7' }} />
                    <span className="docs-search-item-title">
                      {highlightMatch(item.articleTitle, query.trim())}
                      {item.sectionTitle && ` ➔ ${item.sectionTitle}`}
                    </span>
                  </div>
                  <span className="docs-search-item-category">
                    {item.categoryTitle}
                  </span>
                </div>
                <div className="docs-search-item-snippet">
                  {highlightMatch(item.snippet, query.trim())}
                </div>
              </div>
            )
          })
        ) : (
          <div className="docs-search-empty">
            没有找到与 “{query}” 相关的操作说明，请尝试其他关键词
          </div>
        )}
      </div>

      <div className="docs-search-footer">
        <div style={{ display: 'flex', gap: 14 }}>
          <span><kbd className="docs-search-kbd">↑</kbd> <kbd className="docs-search-kbd">↓</kbd> 切换选项</span>
          <span><kbd className="docs-search-kbd">Enter</kbd> 查看文章</span>
          <span><kbd className="docs-search-kbd">Esc</kbd> 关闭</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#0284c7' }}>
          <span>直达操作指南</span>
          <ArrowRightOutlined style={{ fontSize: 11 }} />
        </div>
      </div>
    </Modal>
  )
}
