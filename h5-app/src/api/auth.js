import request from './request.js'

export const login = (data) => {
  return request.post('/auth/login', {
    username: data.username,
    password: data.password
  })
}

export const getCurrentUser = () => {
  return request.get('/auth/me')
}

export const logout = () => {
  return request.post('/auth/logout')
}

export const changePassword = (data) => {
  return request.put('/auth/me/password', data)
}
