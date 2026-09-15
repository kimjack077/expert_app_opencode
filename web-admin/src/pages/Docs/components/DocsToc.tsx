import React, { useEffect, useState } from 'react'
import { UnorderedListOutlined, ArrowUpOutlined } from '@ant-design/icons'
import { DocSection } from '../types'

interface DocsTocProps {
  sections: DocSection[]
}

export const DocsToc: React.FC<DocsTocProps> = ({ sections }) => {
  const [activeSectionId, setActiveSectionId] = useState<string>(sections[0]?.id || '')

  useEffect(() => {
    if (!sections.length) return

    const handleScroll = () => {
      const scrollPosition = window.scrollY + 120
      let currentActive = sections[0].id

      for (const section of sections) {
        const el = document.getElementById(section.id)
        if (el) {
          const top = el.getBoundingClientRect().top + window.scrollY
          if (top <= scrollPosition) {
            currentActive = section.id
          }
        }
      }
      setActiveSectionId(currentActive)
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    handleScroll()
    return () => window.removeEventListener('scroll', handleScroll)
  }, [sections])

  const scrollToSection = (id: string, e: React.MouseEvent) => {
    e.preventDefault()
    const el = document.getElementById(id)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' })
      setActiveSectionId(id)
    }
  }

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  if (sections.length === 0) return null

  return (
    <aside className="docs-toc">
      <div className="docs-toc-title">
        <UnorderedListOutlined />
        <span>本页大纲</span>
      </div>

      <ul className="docs-toc-list">
        {sections.map((sec) => (
          <li key={sec.id} className="docs-toc-item">
            <a
              href={`#${sec.id}`}
              className={`docs-toc-link ${activeSectionId === sec.id ? 'active' : ''}`}
              onClick={(e) => scrollToSection(sec.id, e)}
            >
              {sec.title}
            </a>
          </li>
        ))}
      </ul>

      <div className="docs-toc-backtop" onClick={scrollToTop}>
        <ArrowUpOutlined />
        <span>回到顶部</span>
      </div>
    </aside>
  )
}
