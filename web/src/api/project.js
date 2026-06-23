import request from '@/utils/request'

const BASE = '/v1/projects'

/**
 * 获取工程列表
 */
export function listProjects() {
  return request.get(BASE)
}

/**
 * 创建工程
 * @param {{ name: string, description?: string }} data
 */
export function createProject(data) {
  return request.post(BASE, data)
}

/**
 * 重命名工程
 * @param {string} name - 原工程名
 * @param {{ new_name: string }} data
 */
export function renameProject(name, data) {
  return request.put(`${BASE}/${encodeURIComponent(name)}/rename`, data)
}

/**
 * 更新工程描述
 * @param {string} name - 工程名
 * @param {{ description: string }} data
 */
export function updateProject(name, data) {
  return request.put(`${BASE}/${encodeURIComponent(name)}`, data)
}

/**
 * 删除工程
 * @param {string} name - 工程名
 */
export function deleteProject(name) {
  return request.delete(`${BASE}/${encodeURIComponent(name)}`)
}
