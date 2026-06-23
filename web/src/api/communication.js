import request from '@/utils/request'

const BASE = '/v1/communication'

/**
 * 连接设备
 * @param {{ host: string, port: number, protocol_type: string, extra?: object }} data
 */
export function connectDevice(data) {
  return request.post(`${BASE}/connect`, data)
}

/**
 * 断开设备连接
 * @param {{ host: string, port: number, protocol_type: string }} data
 */
export function disconnectDevice(data) {
  return request.post(`${BASE}/disconnect`, data)
}

/**
 * 获取连接状态
 */
export function getStatus() {
  return request.get(`${BASE}/status`)
}

/**
 * 获取报文日志
 * @param {number} since - Unix 时间戳，只返回该时间之后的新报文
 */
export function getMessages(since = 0) {
  return request.get(`${BASE}/messages`, { params: { since } })
}

/**
 * 检测协议管理子进程是否存活
 */
export function pingManager() {
  return request.get(`${BASE}/ping`)
}

/**
 * 设置只接收遥控报文模式
 * @param {{ host: string, port: number, protocol_type: string, enabled: boolean }} data
 */
export function setRemoteOnly(data) {
  return request.post(`${BASE}/remote-only`, data)
}

/**
 * 清空报文日志（后端主进程+子进程缓冲区）
 * @param {{ host: string, port: number, protocol_type: string }} data
 */
export function clearMessages(data) {
  return request.post(`${BASE}/clear-messages`, data)
}
