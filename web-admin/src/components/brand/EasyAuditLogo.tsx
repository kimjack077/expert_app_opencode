import React from 'react'

interface EasyAuditLogoProps {
  size?: number
  showText?: boolean
  textColor?: string
  subTextColor?: string
  direction?: 'horizontal' | 'vertical'
  className?: string
  style?: React.CSSProperties
}

export const EasyAuditLogoIcon: React.FC<{ size?: number; className?: string; style?: React.CSSProperties }> = ({
  size = 36,
  className,
  style,
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={{ display: 'inline-block', verticalAlign: 'middle', ...style }}
    >
      <defs>
        <linearGradient id="easyAuditGrad1" x1="4" y1="4" x2="44" y2="44" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#2563EB" />
          <stop offset="50%" stopColor="#3B82F6" />
          <stop offset="100%" stopColor="#06B6D4" />
        </linearGradient>
        <linearGradient id="easyAuditGrad2" x1="12" y1="12" x2="36" y2="36" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#FFFFFF" />
          <stop offset="100%" stopColor="#E0F2FE" />
        </linearGradient>
        <filter id="easyAuditShadow" x="0" y="2" width="48" height="46" filterUnits="userSpaceOnUse">
          <feDropShadow dx="0" dy="3" stdDeviation="3" floodColor="#1D4ED8" floodOpacity="0.35" />
        </filter>
      </defs>

      {/* 外层圆角菱盾轮廓 */}
      <rect
        x="5"
        y="5"
        width="38"
        height="38"
        rx="11"
        fill="url(#easyAuditGrad1)"
        filter="url(#easyAuditShadow)"
      />

      {/* 内部高光折线装饰 */}
      <path
        d="M10 16C10 12.6863 12.6863 10 16 10H32C35.3137 10 38 12.6863 38 16"
        stroke="rgba(255, 255, 255, 0.3)"
        strokeWidth="2"
        strokeLinecap="round"
      />

      {/* 易审通核心“E”与审核对勾“✓”融合符号 */}
      {/* 顶部审核轨道 */}
      <path
        d="M15 17H33"
        stroke="url(#easyAuditGrad2)"
        strokeWidth="3"
        strokeLinecap="round"
      />
      {/* 中部智能连接点 */}
      <path
        d="M15 24H25"
        stroke="url(#easyAuditGrad2)"
        strokeWidth="3"
        strokeLinecap="round"
      />
      {/* 底部与对勾融合路径 */}
      <path
        d="M15 31H21L27 37L35 22"
        stroke="#FFFFFF"
        strokeWidth="3.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* 右上角智能火花星芒 */}
      <circle cx="34" cy="14" r="2" fill="#FDE047" />
    </svg>
  )
}

export const EasyAuditLogo: React.FC<EasyAuditLogoProps> = ({
  size = 36,
  showText = true,
  textColor = '#0f172a',
  subTextColor = '#64748b',
  direction = 'horizontal',
  className,
  style,
}) => {
  return (
    <div
      className={`easy-audit-logo-container ${className || ''}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        flexDirection: direction === 'vertical' ? 'column' : 'row',
        gap: direction === 'vertical' ? 8 : 10,
        userSelect: 'none',
        ...style,
      }}
    >
      <EasyAuditLogoIcon size={size} />
      {showText && (
        <div style={{ textAlign: direction === 'vertical' ? 'center' : 'left', lineHeight: 1.2 }}>
          <div
            style={{
              fontSize: size * 0.52,
              fontWeight: 800,
              color: textColor,
              letterSpacing: '0.02em',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <span>易审通</span>
            <span
              style={{
                fontSize: size * 0.34,
                fontWeight: 700,
                color: '#2563eb',
                fontFamily: 'Inter, system-ui, sans-serif',
                letterSpacing: '0.04em',
              }}
            >
              EasyAudit
            </span>
          </div>
          <div
            style={{
              fontSize: Math.max(10, size * 0.28),
              color: subTextColor,
              fontWeight: 500,
              marginTop: 2,
              letterSpacing: '0.04em',
            }}
          >
            让每一次审核都简单高效
          </div>
        </div>
      )}
    </div>
  )
}

export default EasyAuditLogo
