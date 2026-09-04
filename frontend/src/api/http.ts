import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const http = axios.create({ baseURL: '/api/v1', timeout: 15000 })

http.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) config.headers.Authorization = `Bearer ${auth.token}`
  return config
})

// 统一响应包 {code, message, data}（Spec 03）
http.interceptors.response.use(
  (resp) => {
    const { code, message, data } = resp.data
    if (code !== 0) {
      if (code === 40101) useAuthStore().logout()
      else ElMessage.error(message || '请求失败')
      return Promise.reject(new Error(message))
    }
    return data
  },
  (err) => {
    ElMessage.error(err.message || '网络错误')
    return Promise.reject(err)
  },
)

export default http
