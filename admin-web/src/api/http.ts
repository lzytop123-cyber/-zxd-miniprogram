import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE || '/api'

const http = axios.create({
  baseURL,
  timeout: 15000,
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (res) => {
    const data = res.data
    if (data.code !== 0) {
      return Promise.reject(new Error(data.message || '请求失败'))
    }
    return data
  },
  (err) => Promise.reject(err)
)

export default http
