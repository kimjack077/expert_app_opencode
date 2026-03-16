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
