import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { message } from 'antd'
import { CopyOutlined } from '@ant-design/icons'
import './MarkdownView.css'

interface MarkdownViewProps {
  content: string
  className?: string
}

export default function MarkdownView({ content, className = '' }: MarkdownViewProps) {
  if (!content) return null

  const handleCopyCode = async (codeText: string) => {
    try {
      await navigator.clipboard.writeText(codeText)
      message.success('代码已复制')
    } catch {
      message.error('复制失败')
    }
  }

  return (
    <div className={`markdown-view ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          table: ({ node, ...props }) => (
            <div className="markdown-table-wrapper">
              <table {...props} />
            </div>
          ),
          code: ({ node, inline, className, children, ...props }: any) => {
            const match = /language-(\w+)/.exec(className || '')
            const codeString = String(children).replace(/\n$/, '')

            if (!inline && (match || codeString.includes('\n'))) {
              return (
                <div className="markdown-code-block">
                  <div className="markdown-code-header">
                    <span>{match ? match[1] : 'text'}</span>
                    <span
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleCopyCode(codeString)}
                      title="复制代码"
                    >
                      <CopyOutlined style={{ marginRight: 4 }} />
                      复制
                    </span>
                  </div>
                  <pre>
                    <code className={className} {...props}>
                      {children}
                    </code>
                  </pre>
                </div>
              )
            }
            return (
              <code className={className} {...props}>
                {children}
              </code>
            )
          },
          p: ({ node, children, ...props }) => {
            // 检测是否为 ⚠️ 风险提示或 ✅ 建议段落，增强渲染
            const textContent = React.Children.toArray(children)
              .map((c) => (typeof c === 'string' ? c : ''))
              .join('')

            if (textContent.startsWith('⚠️ 风险') || textContent.startsWith('⚠️')) {
              return (
                <div className="markdown-alert-card warning">
                  <span>{children}</span>
                </div>
              )
            }
            if (textContent.startsWith('✅ 建议') || textContent.startsWith('✅')) {
              return (
                <div className="markdown-alert-card success">
                  <span>{children}</span>
                </div>
              )
            }
            if (textContent.startsWith('ℹ️') || textContent.startsWith('💡')) {
              return (
                <div className="markdown-alert-card info">
                  <span>{children}</span>
                </div>
              )
            }
            return <p {...props}>{children}</p>
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
