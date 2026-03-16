import request from './request.js'

export const uploadMedia = (taskId, file) => {
  const formData = new FormData()
  formData.append('task_id', taskId)
  formData.append('file', file)
  
  return request.post('/media/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

export const getMediaByTask = (taskId) => {
  return request.get(`/media/task/${taskId}`)
}

export const deleteMedia = (id) => {
  return request.delete(`/media/${id}`)
}
