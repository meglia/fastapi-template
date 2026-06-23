import axios from 'axios'
import { ElMessage } from 'element-plus'

// 创建 Axios 实例
const request = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ========================
// 请求拦截器
// ========================
request.interceptors.request.use(
  (config) => {
    // 可从 Pinia store 或 localStorage 获取 token
    // const token = localStorage.getItem('token')
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`
    // }
    return config
  },
  (error) => {
    return Promise.reject(error)
  },
)

// ========================
// 响应拦截器
// ========================
request.interceptors.response.use(
  (response) => {
    const res = response.data

    // 根据后端约定的数据结构调整：
    // 假设后端返回 { code: 200, data: ..., message: '...' }
    // 如果 code 非 200 则视为业务错误
    if (res.code !== undefined && res.code !== 200) {
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || '请求失败'))
    }

    // 直接返回 data 字段，方便调用方使用
    return res.data !== undefined ? res.data : res
  },
  (error) => {
    const { response } = error || {}
    const status = response?.status

    let message = '网络错误，请稍后重试'

    switch (status) {
      case 400:
        message = '请求参数错误'
        break
      case 401:
        message = '未授权，请重新登录'
        // 可在此处理 token 过期跳转登录页
        // router.push('/login')
        break
      case 403:
        message = '拒绝访问'
        break
      case 404:
        message = '请求资源不存在'
        break
      case 500:
        message = '服务器内部错误'
        break
      case 502:
        message = '网关错误'
        break
      case 503:
        message = '服务暂不可用'
        break
    }

    ElMessage.error(message)
    return Promise.reject(error)
  },
)

export default request
