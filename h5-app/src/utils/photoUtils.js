const TARGET_SIZE = 500 * 1024
const MAX_WIDTH = 1920
const MAX_HEIGHT = 1080
const QUALITY_STEP = 0.1
const MIN_QUALITY = 0.3

export function getCurrentPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('浏览器不支持地理定位'))
      return
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
          timestamp: position.timestamp
        })
      },
      (error) => {
        let message = '获取位置失败'
        switch (error.code) {
          case error.PERMISSION_DENIED:
            message = '用户拒绝了位置请求'
            break
          case error.POSITION_UNAVAILABLE:
            message = '位置信息不可用'
            break
          case error.TIMEOUT:
            message = '获取位置超时'
            break
        }
        reject(new Error(message))
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 60000
      }
    )
  })
}

export function formatCoordinates(latitude, longitude) {
  if (!latitude || !longitude) return ''
  
  const latDir = latitude >= 0 ? 'N' : 'S'
  const lngDir = longitude >= 0 ? 'E' : 'W'
  const lat = Math.abs(latitude).toFixed(6)
  const lng = Math.abs(longitude).toFixed(6)
  
  return `${lat}°${latDir} ${lng}°${lngDir}`
}

export function formatDateTime(timestamp) {
  const date = new Date(timestamp || Date.now())
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

export async function compressImage(file, targetSize = TARGET_SIZE) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      const img = new Image()
      img.onload = () => {
        let width = img.width
        let height = img.height
        
        if (width > MAX_WIDTH || height > MAX_HEIGHT) {
          const ratio = Math.min(MAX_WIDTH / width, MAX_HEIGHT / height)
          width = Math.round(width * ratio)
          height = Math.round(height * ratio)
        }
        
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        const ctx = canvas.getContext('2d')
        ctx.drawImage(img, 0, 0, width, height)
        
        let quality = 0.9
        let compressedBlob = null
        
        const compress = () => {
          canvas.toBlob(
            (blob) => {
              if (!blob) {
                reject(new Error('图片压缩失败'))
                return
              }
              
              if (blob.size <= targetSize || quality <= MIN_QUALITY) {
                compressedBlob = blob
                resolve({
                  blob: compressedBlob,
                  originalSize: file.size,
                  compressedSize: compressedBlob.size,
                  compressionRatio: ((1 - compressedBlob.size / file.size) * 100).toFixed(1),
                  quality: quality
                })
              } else {
                quality -= QUALITY_STEP
                compress()
              }
            },
            'image/jpeg',
            quality
          )
        }
        
        compress()
      }
      img.onerror = () => reject(new Error('图片加载失败'))
      img.src = e.target.result
    }
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.readAsDataURL(file)
  })
}

export async function addWatermark(imageBlob, options = {}) {
  const {
    datetime = Date.now(),
    latitude = null,
    longitude = null,
    inspector = '',
    fontSize = 14,
    padding = 10,
    lineHeight = 22
  } = options

  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      const img = new Image()
      img.onload = () => {
        const canvas = document.createElement('canvas')
        canvas.width = img.width
        canvas.height = img.height
        
        const ctx = canvas.getContext('2d')
        ctx.drawImage(img, 0, 0)
        
        const lines = []
        lines.push(`时间: ${formatDateTime(datetime)}`)
        
        if (latitude && longitude) {
          lines.push(`位置: ${formatCoordinates(latitude, longitude)}`)
        } else {
          lines.push('位置: 未获取')
        }
        
        if (inspector) {
          lines.push(`检查员: ${inspector}`)
        }
        
        const boxHeight = lines.length * lineHeight + padding * 2
        const boxY = canvas.height - boxHeight - padding
        
        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)'
        ctx.fillRect(0, boxY, canvas.width, boxHeight)
        
        ctx.fillStyle = '#ffffff'
        ctx.font = `${fontSize}px Arial, sans-serif`
        ctx.textBaseline = 'top'
        
        lines.forEach((line, index) => {
          ctx.fillText(line, padding, boxY + padding + index * lineHeight)
        })
        
        canvas.toBlob(
          (blob) => {
            if (blob) {
              resolve(blob)
            } else {
              reject(new Error('水印添加失败'))
            }
          },
          'image/jpeg',
          0.92
        )
      }
      img.onerror = () => reject(new Error('图片加载失败'))
      img.src = e.target.result
    }
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.readAsDataURL(imageBlob)
  })
}

export async function processPhoto(file, options = {}) {
  const {
    addWatermark: shouldAddWatermark = true,
    compress: shouldCompress = true,
    inspector = '',
    targetSize = TARGET_SIZE
  } = options

  let position = null
  try {
    position = await getCurrentPosition()
  } catch (error) {
    console.warn('获取位置失败:', error.message)
  }

  let processedBlob = file
  
  if (shouldCompress && file.size > targetSize) {
    const result = await compressImage(file, targetSize)
    processedBlob = result.blob
    console.log(`图片压缩: ${result.originalSize} -> ${result.compressedSize} (${result.compressionRatio}% 压缩)`)
  }

  if (shouldAddWatermark) {
    processedBlob = await addWatermark(processedBlob, {
      datetime: Date.now(),
      latitude: position?.latitude,
      longitude: position?.longitude,
      inspector: inspector
    })
  }

  return {
    blob: processedBlob,
    position: position,
    originalSize: file.size,
    finalSize: processedBlob.size
  }
}

export function blobToFile(blob, fileName) {
  return new File([blob], fileName, { type: blob.type || 'image/jpeg' })
}

export function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onloadend = () => resolve(reader.result)
    reader.onerror = reject
    reader.readAsDataURL(blob)
  })
}

export function base64ToBlob(base64, mimeType = 'image/jpeg') {
  const byteString = atob(base64.split(',')[1])
  const ab = new ArrayBuffer(byteString.length)
  const ia = new Uint8Array(ab)
  for (let i = 0; i < byteString.length; i++) {
    ia[i] = byteString.charCodeAt(i)
  }
  return new Blob([ab], { type: mimeType })
}
