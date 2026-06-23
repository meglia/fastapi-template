import request from '@/utils/request'

const BASE = '/v1/video'

/**
 * 获取帧画面 URL（直接用于 <img> src，带时间戳防缓存）
 * @returns {string} 帧画面 URL
 */
export function getFrameUrl() {
  return `/api${BASE}/frame?t=${Date.now()}`
}

/**
 * 枚举所有视频设备
 * @returns {Promise<{ devices: Array<{ device_index: number, device_name: string }> }>}
 */
export function getDevices() {
  return request.get(`${BASE}/devices`)
}

/**
 * 激活指定视频设备
 * @param {number} deviceIndex - 设备索引
 * @returns {Promise<{ message: string, device_index: number }>}
 */
export function connectDevice(deviceIndex) {
  return request.post(`${BASE}/connect`, { device_index: deviceIndex })
}

/**
 * 断开当前视频连接
 * @returns {Promise<{ message: string }>}
 */
export function disconnectDevice() {
  return request.post(`${BASE}/disconnect`)
}

/**
 * 获取当前视频连接状态
 * @returns {Promise<{ connected: boolean, active_device: object|null, resolution: { width: number, height: number } }>}
 */
export function getStatus() {
  return request.get(`${BASE}/status`)
}
