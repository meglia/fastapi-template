<template>
  <div class="flex flex-col h-full">
    <!-- 顶行：标题 + 导入按钮 + 右侧单选 + 设置 -->
    <div class="flex items-center gap-3 px-4 py-3 border-b border-gray-200 flex-shrink-0">
      <h2 class="text-lg font-semibold text-gray-800">遥控验收</h2>
      <el-button type="primary" @click="dialogVisible = true">导入验收表</el-button>
      <span v-if="hasSavedData" class="text-sm text-green-600 ml-2">
        ✅ 已导入 {{ savedFileName }}
      </span>
      <div class="ml-auto flex items-center gap-3">
        <el-radio-group v-model="backendType" size="small">
          <el-radio-button value="old">验收老后台</el-radio-button>
          <el-radio-button value="new">验收新后台</el-radio-button>
        </el-radio-group>
        <el-button size="small" :icon="Setting" circle @click="onSettingsClick" />
      </div>
    </div>

    <!-- 数据表格区域 -->
    <div class="flex-1 p-4 overflow-hidden min-w-0 flex flex-col">
      <el-empty v-if="!hasSavedData" description="请先导入验收表" />
      <template v-else>
        <div class="text-sm text-gray-500 mb-2 flex-shrink-0">验收表数据已加载，共 {{ savedData.length }} 条记录</div>
        <div ref="tableScrollRef" class="flex-1 min-h-0 overflow-x-auto" @scroll="onTableScroll">
          <el-table
            ref="tableRef"
            :data="savedData"
            border stripe size="small"
            style="min-width: 100%"
            :max-height="tableMaxHeight"
            @selection-change="onSelectionChange"
          >
          <el-table-column type="selection" width="45" fixed="left" />
          <el-table-column label="序号" width="55" fixed="left" align="center">
            <template #default="{ $index }">
              <span class="text-yellow-600 font-medium">{{ $index + 1 }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="point_number" label="点号" min-width="120" fixed="left" show-overflow-tooltip />
          <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
          <el-table-column prop="old_backend_object" label="老后台遥控对象" min-width="140" show-overflow-tooltip />
          <el-table-column label="老后台遥控截图" min-width="140" align="center">
            <template #default="{ row }">
              <el-image
                v-if="row.old_backend_screenshot"
                :src="getScreenshotUrl(projectName, row.old_backend_screenshot)"
                :preview-src-list="[getScreenshotUrl(projectName, row.old_backend_screenshot)]"
                fit="cover"
                class="w-16 h-12 rounded cursor-pointer"
                preview-teleported
              />
              <span v-else class="text-gray-300 text-xs">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="old_backend_recognition" label="老后台遥控识别" min-width="140" show-overflow-tooltip />
          <el-table-column prop="new_backend_object" label="新后台遥控对象" min-width="140" show-overflow-tooltip />
          <el-table-column label="新后台遥控截图" min-width="140" align="center">
            <template #default="{ row }">
              <el-image
                v-if="row.new_backend_screenshot"
                :src="getScreenshotUrl(projectName, row.new_backend_screenshot)"
                :preview-src-list="[getScreenshotUrl(projectName, row.new_backend_screenshot)]"
                fit="cover"
                class="w-16 h-12 rounded cursor-pointer"
                preview-teleported
              />
              <span v-else class="text-gray-300 text-xs">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="new_backend_recognition" label="新后台遥控识别" min-width="140" show-overflow-tooltip />
          <el-table-column label="验收状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.acceptance_status)" size="small">
                {{ row.acceptance_status || '待验收' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="验收时间" width="160">
            <template #default="{ row }">
              <span class="text-xs">{{ row.acceptance_time || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right" align="center">
            <template #default="{ $index }">
              <el-button size="small" text type="primary" disabled>确认</el-button>
              <el-dropdown trigger="click">
                <el-button size="small" text type="primary">
                  清空<el-icon class="el-icon--right"><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="onClearCommand($index, 'old')">清空老后台验收信息</el-dropdown-item>
                    <el-dropdown-item @click="onClearCommand($index, 'new')">清空新后台验收信息</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </el-table-column>
          </el-table>
        </div>
      </template>
    </div>

    <!-- 导入对话框 -->
    <ImportAcceptanceDialog
      v-model="dialogVisible"
      :project-name="projectName"
      @saved="onSaved"
    />

    <!-- 识别设置对话框 -->
    <RecognitionSettingsDialog
      v-model="settingsDialogVisible"
      :project-name="projectName"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Setting, ArrowLeft, ArrowRight, ArrowDown } from '@element-plus/icons-vue'
import { getAcceptance, recordRemoteAcceptance, getScreenshotUrl, clearAcceptance } from '@/api/acceptance'
import ImportAcceptanceDialog from './ImportAcceptanceDialog.vue'
import RecognitionSettingsDialog from './RecognitionSettingsDialog.vue'

const props = defineProps({
  projectName: { type: String, required: true },
})

// ── 后台类型单选 ──
const backendType = ref('old')

// ── 设置按钮 ──
const settingsDialogVisible = ref(false)

function onSettingsClick() {
  settingsDialogVisible.value = true
}

// ── 对话框 ──
const dialogVisible = ref(false)

// ── 已保存数据 ──
const hasSavedData = ref(false)
const savedFileName = ref('')
const savedData = ref([])

// ── 表格勾选 ──
const tableRef = ref(null)
const selectedRows = ref([])

function onSelectionChange(selection) {
  selectedRows.value = selection
}

// ── 表格滚动 ──
const tableScrollRef = ref(null)
const scrollLeft = ref(0)
const canScrollRight = ref(false)

function updateScrollState() {
  const el = tableScrollRef.value
  if (!el) return
  scrollLeft.value = el.scrollLeft
  canScrollRight.value = el.scrollLeft + el.clientWidth < el.scrollWidth - 1
}

function onTableScroll() {
  updateScrollState()
}

function scrollTable(delta) {
  const el = tableScrollRef.value
  if (!el) return
  el.scrollBy({ left: delta, behavior: 'smooth' })
}

// 数据变化后更新滚动状态
watch([savedData, hasSavedData], async () => {
  await nextTick()
  updateScrollState()
})

// ── 表格高度 ──
const tableMaxHeight = ref(window.innerHeight - 260)

// ── 状态标签颜色 ──
function statusTagType(status) {
  const map = { '通过': 'success', '不通过': 'danger', '待验收': 'info' }
  return map[status] || 'info'
}

// ── 对话框保存回调 ──
function onSaved({ rows, fileName }) {
  hasSavedData.value = true
  savedData.value = rows
  savedFileName.value = fileName
}

// ── 清空验收数据（仅清空当前行）──
async function onClearCommand(rowIndex, backendType) {
  if (!hasSavedData.value) return

  const label = backendType === 'old' ? '老后台' : '新后台'
  const rowNum = rowIndex + 1
  try {
    await ElMessageBox.confirm(
      `确定要清空第${rowNum}行的${label}验收信息吗？此操作将清空该行${label}的遥控对象、遥控截图、遥控识别数据，不可恢复。`,
      '确认清空',
      { confirmButtonText: '确认清空', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return // 用户取消
  }

  try {
    const res = await clearAcceptance(props.projectName, backendType, rowIndex)
    if (res.rows) {
      savedData.value = res.rows
    }
    ElMessage.success(`第${rowNum}行${label}验收信息已清空`)
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '清空失败'
    ElMessage.error(msg)
  }
}

// ── 遥控信号处理（由父组件 AcceptanceLayout 调用）──
async function handleRemoteSignal({ signal }) {
  if (!hasSavedData.value) return

  const bt = backendType.value
  // 收集勾选行索引
  let rowIndices = null
  if (selectedRows.value.length > 0) {
    rowIndices = selectedRows.value.map(r => savedData.value.indexOf(r)).filter(i => i >= 0)
  }

  try {
    const res = await recordRemoteAcceptance(props.projectName, {
      backend_type: bt,
      signal,
      row_indices: rowIndices,
    })
    if (res.rows) {
      savedData.value = res.rows
    }
    if (res.filled_indices && res.filled_indices.length > 0) {
      ElMessage.success(
        `遥控验收已记录: ${bt === 'old' ? '老后台' : '新后台'} ` +
        `→ 第${res.filled_indices.map(i => i + 1).join(',')}行`
      )
    }
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '遥控验收记录失败'
    ElMessage.error(msg)
  }
}

defineExpose({ handleRemoteSignal })

// ── 加载已有数据 ──
onMounted(async () => {
  try {
    const data = await getAcceptance(props.projectName)
    if (data.exists) {
      hasSavedData.value = true
      savedFileName.value = data.file_name || ''
      savedData.value = data.items || []
    }
  } catch {
    // 忽略
  }
})
</script>
