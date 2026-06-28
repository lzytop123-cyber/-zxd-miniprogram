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
    // 解包：返回 res.data（{code, message, data}），不是 AxiosResponse
    return data as any
  },
  (err) => Promise.reject(err)
)

// 告知 TS：所有方法返回的是 UnwrappedResponse
type UnwrappedResponse<T = any> = { code: number; message: string; data: T }

const api = {
  get: <T = any>(...args: Parameters<typeof http.get>) => http.get(...args) as Promise<UnwrappedResponse<T>>,
  post: <T = any>(...args: Parameters<typeof http.post>) => http.post(...args) as Promise<UnwrappedResponse<T>>,
  put: <T = any>(...args: Parameters<typeof http.put>) => http.put(...args) as Promise<UnwrappedResponse<T>>,
  patch: <T = any>(...args: Parameters<typeof http.patch>) => http.patch(...args) as Promise<UnwrappedResponse<T>>,
  delete: <T = any>(...args: Parameters<typeof http.delete>) => http.delete(...args) as Promise<UnwrappedResponse<T>>,
}

export default api
