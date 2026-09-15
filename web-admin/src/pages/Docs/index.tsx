import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  DOCS_CATEGORIES,
  DOCS_ARTICLES,
  ALL_FLATTEN_ARTICLES,
  getDocArticleById,
} from './data/docsContent'
import { DocsHeader } from './components/DocsHeader'
import { DocsSidebar } from './components/DocsSidebar'
import { DocsContent } from './components/DocsContent'
import { DocsToc } from './components/DocsToc'
import { DocsSearchModal } from './components/DocsSearchModal'
import './docs.css'

export default function DocsPage() {
  const { docId } = useParams<{ docId?: string }>()
  const navigate = useNavigate()
  const [searchModalOpen, setSearchModalOpen] = useState(false)

  // 当前选中的文章 ID，默认第一篇 'overview'
  const currentArticleId = docId || 'overview'
  const currentArticle = getDocArticleById(currentArticleId) || DOCS_ARTICLES[0]

  // 获取当前文章所在分类
  const currentCategory = DOCS_CATEGORIES.find((c) => c.id === currentArticle.category)
  const categoryTitle = currentCategory ? currentCategory.title : '使用指南'

  // 计算上一篇与下一篇
  const currentIndex = ALL_FLATTEN_ARTICLES.findIndex((a) => a.id === currentArticle.id)
  const prevArticle = currentIndex > 0 ? ALL_FLATTEN_ARTICLES[currentIndex - 1] : undefined
  const nextArticle =
    currentIndex >= 0 && currentIndex < ALL_FLATTEN_ARTICLES.length - 1
      ? ALL_FLATTEN_ARTICLES[currentIndex + 1]
      : undefined

  // 全局监听快捷键 Ctrl+K 打开搜索
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault()
        setSearchModalOpen(true)
      }
    }
    window.addEventListener('keydown', handleGlobalKeyDown)
    return () => window.removeEventListener('keydown', handleGlobalKeyDown)
  }, [])

  // 切换文章时，滚动到页面顶部
  const handleSelectArticle = (articleId: string, sectionId?: string) => {
    navigate(`/docs/${articleId}`)
    if (sectionId) {
      setTimeout(() => {
        const el = document.getElementById(sectionId)
        if (el) {
          el.scrollIntoView({ behavior: 'smooth' })
        } else {
          window.scrollTo({ top: 0, behavior: 'smooth' })
        }
      }, 100)
    } else {
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  return (
    <div className="docs-root">
      {/* 顶部导航 */}
      <DocsHeader onOpenSearch={() => setSearchModalOpen(true)} />

      {/* 主体三栏布局 */}
      <div className="docs-main-container">
        {/* 左侧目录 */}
        <DocsSidebar
          categories={DOCS_CATEGORIES}
          activeArticleId={currentArticle.id}
          onSelectArticle={(id) => handleSelectArticle(id)}
        />

        {/* 中间正文 */}
        <DocsContent
          article={currentArticle}
          categoryTitle={categoryTitle}
          prevArticle={prevArticle}
          nextArticle={nextArticle}
          onSelectArticle={(id) => handleSelectArticle(id)}
        />

        {/* 右侧大纲 */}
        <DocsToc sections={currentArticle.sections} />
      </div>

      {/* 搜索模态框 */}
      <DocsSearchModal
        open={searchModalOpen}
        onClose={() => setSearchModalOpen(false)}
        onSelectResult={(artId: string, secId?: string) => handleSelectArticle(artId, secId)}
      />
    </div>
  )
}
