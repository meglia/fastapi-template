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
          <el-table :data="savedData" border stripe size="small" style="min-width: 100%" :max-height="tableMaxHeight">
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
              <span v-if="row.old_backend_screenshot" class="text-blue-500 text-xs cursor-pointer">📷 查看</span>
              <span v-else class="text-gray-300 text-xs">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="old_backend_recognition" label="老后台遥控识别" min-width="140" show-overflow-tooltip />
          <el-table-column prop="new_backend_object" label="新后台遥控对象" min-width="140" show-overflow-tooltip />
          <el-table-column label="新后台遥控截图" min-width="140" align="center">
            <template #default="{ row }">
              <span v-if="row.new_backend_screenshot" class="text-blue-500 text-xs cursor-pointer">📷 查看</span>
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
            <template #default>
              <el-button size="small" text type="primary" disabled>确认</el-button>
              <el-button size="small" text type="primary" disabled>删除</el-button>
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
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { Setting, ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { getAcceptance } from '@/api/acceptance'
import ImportAcceptanceDialog from './ImportAcceptanceDialog.vue'

const props = defineProps({
  projectName: { type: String, required: true },
})

// ── 后台类型单选 ──
const backendType = ref('old')

// ── 设置按钮 ──
function onSettingsClick() {
  // TODO: 预留设置功能
}

// ── 对话框 ──
const dialogVisible = ref(false)

// ── 已保存数据 ──
const hasSavedData = ref(false)
const savedFileName = ref('')
const savedData = ref([])

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
