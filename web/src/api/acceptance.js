import axios from 'axios'
import request from '@/utils/request'

const BASE = '/v1/projects'

/**
 * 上传验收表 Excel 文件，返回工作簿和列信息
 * @param {string} projectName - 工程名称
 * @param {File} file - 上传的文件对象
 * @returns {Promise<{ workbooks: Array<{ name: string, columns: string[] }>, file_name: string }>}
 */
export function uploadAcceptance(projectName, file) {
  const formData = new FormData()
  formData.append('file', file)
  return axios.post(`/api${BASE}/${encodeURIComponent(projectName)}/acceptance/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then((res) => {
    // 直接返回 data（绕过统一拦截器的 data 解包）
    return res.data
  })
}

/**
 * 预览验收表数据
 * @param {string} projectName - 工程名称
 * @param {{ workbook: string, point_column: string, desc_column: string }} data
 * @returns {Promise<{ rows: Array<{ point_number: string, description: string }>, total_count: number }>}
 */
export function previewAcceptance(projectName, data) {
  return request.post(`${BASE}/${encodeURIComponent(projectName)}/acceptance/preview`, data)
}

/**
 * 保存验收表数据到工程文件夹
 * @param {string} projectName - 工程名称
 * @param {{ workbook: string, point_column: string, desc_column: string }} data
 * @returns {Promise<{ message: string, file_path: string, total_count: number }>}
 */
export function saveAcceptance(projectName, data) {
  return request.post(`${BASE}/${encodeURIComponent(projectName)}/acceptance/save`, data)
}

/**
 * 获取已保存的验收表数据
 * @param {string} projectName - 工程名称
 * @returns {Promise<{ exists: boolean, file_name?: string, data?: Array }>}
 */
export function getAcceptance(projectName) {
  return request.get(`${BASE}/${encodeURIComponent(projectName)}/acceptance`)
}

/**
 * 遥控验收记录 — 收到遥控报文时调用的端点
 * @param {string} projectName - 工程名称
 * @param {{ backend_type: 'old'|'new', signal: object, row_indices: number[]|null }} data
 * @returns {Promise<{ rows: Array, filled_indices: number[] }>}
 */
export function recordRemoteAcceptance(projectName, data) {
  return request.post(`${BASE}/${encodeURIComponent(projectName)}/acceptance/record-remote`, data)
}

/**
 * 获取截图 URL
 * @param {string} projectName - 工程名称
 * @param {string} filename - 截图文件名
 * @returns {string} 截图完整 URL
 */
export function getScreenshotUrl(projectName, filename) {
  if (!filename) return ''
  return `/api${BASE}/${encodeURIComponent(projectName)}/acceptance/screenshot/${encodeURIComponent(filename)}`
}
