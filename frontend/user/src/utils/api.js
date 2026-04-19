import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response) {
      const { status, data } = error.response
      if (status === 401) {
        localStorage.removeItem('token')
        router.push('/login')
        const msg = data?.detail || data?.message || ''
        if (msg.includes('禁用')) {
          ElMessage.error('账户已被禁用，请联系管理员')
        } else if (msg.includes('不存在')) {
          ElMessage.error('账户已被删除')
        } else {
          ElMessage.error('登录已过期，请重新登录')
        }
      }
      error.message = data?.detail || data?.message || '请求失败'
    } else {
      error.message = '网络错误，请检查网络连接'
    }
    return Promise.reject(error)
  }
)

export default api
