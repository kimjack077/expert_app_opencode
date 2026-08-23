<template>
  <div
    class="easy-audit-logo"
    :class="[direction, customClass]"
    :style="{ gap: direction === 'vertical' ? '8px' : '10px' }"
  >
    <svg
      :width="size"
      :height="size"
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      class="logo-svg"
    >
      <defs>
        <linearGradient :id="'h5EasyGrad1_' + uid" x1="4" y1="4" x2="44" y2="44" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#2563EB" />
          <stop offset="50%" stop-color="#3B82F6" />
          <stop offset="100%" stop-color="#06B6D4" />
        </linearGradient>
        <linearGradient :id="'h5EasyGrad2_' + uid" x1="12" y1="12" x2="36" y2="36" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#FFFFFF" />
          <stop offset="100%" stop-color="#E0F2FE" />
        </linearGradient>
        <filter :id="'h5EasyShadow_' + uid" x="0" y="2" width="48" height="46" filterUnits="userSpaceOnUse">
          <feDropShadow dx="0" dy="3" stdDeviation="3" flood-color="#1D4ED8" flood-opacity="0.35" />
        </filter>
      </defs>

      <!-- 外层圆角菱盾轮廓 -->
      <rect
        x="5"
        y="5"
        width="38"
        height="38"
        rx="11"
        :fill="`url(#h5EasyGrad1_${uid})`"
        :filter="`url(#h5EasyShadow_${uid})`"
      />

      <!-- 内部高光折线装饰 -->
      <path
        d="M10 16C10 12.6863 12.6863 10 16 10H32C35.3137 10 38 12.6863 38 16"
        stroke="rgba(255, 255, 255, 0.3)"
        stroke-width="2"
        stroke-linecap="round"
      />

      <!-- 易审通核心“E”与审核对勾“✓”融合符号 -->
      <path
        d="M15 17H33"
        :stroke="`url(#h5EasyGrad2_${uid})`"
        stroke-width="3"
        stroke-linecap="round"
      />
      <path
        d="M15 24H25"
        :stroke="`url(#h5EasyGrad2_${uid})`"
        stroke-width="3"
        stroke-linecap="round"
      />
      <path
        d="M15 31H21L27 37L35 22"
        stroke="#FFFFFF"
        stroke-width="3.2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />

      <!-- 右上角智能火花星芒 -->
      <circle cx="34" cy="14" r="2" fill="#FDE047" />
    </svg>

    <div v-if="showText" class="logo-text-box" :style="{ textAlign: direction === 'vertical' ? 'center' : 'left' }">
      <div class="logo-title-row" :style="{ fontSize: `${size * 0.52}px`, color: textColor }">
        <span class="main-title">易审通</span>
        <span class="en-sub" :style="{ fontSize: `${size * 0.34}px` }">EasyAudit</span>
      </div>
      <div
        v-if="showSlogan"
        class="logo-slogan"
        :style="{ fontSize: `${Math.max(10, size * 0.28)}px`, color: subTextColor }"
      >
        {{ sloganText }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: {
    type: Number,
    default: 36,
  },
  showText: {
    type: Boolean,
    default: true,
  },
  showSlogan: {
    type: Boolean,
    default: true,
  },
  sloganText: {
    type: String,
    default: '让每一次审核都简单高效',
  },
  textColor: {
    type: String,
    default: '#ffffff',
  },
  subTextColor: {
    type: String,
    default: '#94a3b8',
  },
  direction: {
    type: String,
    default: 'horizontal', // 'horizontal' | 'vertical'
  },
  customClass: {
    type: String,
    default: '',
  },
})

const uid = computed(() => Math.random().toString(36).substring(2, 8))
</script>

<style scoped>
.easy-audit-logo {
  display: inline-flex;
  align-items: center;
  user-select: none;
}
.easy-audit-logo.vertical {
  flex-direction: column;
}
.easy-audit-logo.horizontal {
  flex-direction: row;
}
.logo-text-box {
  line-height: 1.2;
}
.logo-title-row {
  font-weight: 800;
  display: flex;
  align-items: center;
  gap: 6px;
  letter-spacing: 0.02em;
}
.main-title {
  font-weight: 800;
}
.en-sub {
  font-weight: 700;
  color: #38bdf8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  letter-spacing: 0.04em;
}
.logo-slogan {
  font-weight: 500;
  margin-top: 2px;
  letter-spacing: 0.04em;
}
</style>
