export interface DocStep {
  title: string
  desc: string
  tip?: string
}

export interface DocCallout {
  type: 'info' | 'tip' | 'warning' | 'danger'
  title: string
  content: string
}

export interface DocImage {
  src: string
  caption: string
  alt?: string
}

export interface DocSection {
  id: string
  title: string
  level: 2 | 3
  content?: string
  steps?: DocStep[]
  image?: DocImage
  callout?: DocCallout
  keyPoints?: string[]
}

export interface DocArticle {
  id: string
  title: string
  category: string
  order: number
  description: string
  badge?: string
  routeLink?: string // 系统内对应功能的实际跳转路径，例如 /audit-projects
  actionText?: string // 跳转按钮文字，例如 "前往审核项目"
  updatedAt?: string
  author?: string
  keywords: string[]
  intro?: string
  sections: DocSection[]
}

export interface DocCategory {
  id: string
  title: string
  icon: string
  description?: string
  articles: DocArticle[]
}

export interface SearchResultItem {
  articleId: string
  articleTitle: string
  categoryTitle: string
  sectionId?: string
  sectionTitle?: string
  snippet: string
  matchedKeyword: string
}
