<template>
  <el-dialog
    v-model="dialogVisible"
    title="识别设置"
    width="680px"
    :close-on-click-modal="false"
    @open="onOpen"
    @close="onClose"
  >
    <!-- 划定识别区域 -->
    <div class="mb-6">
      <div class="flex items-center gap-3 mb-3">
        <h3 class="text-base font-semibold text-gray-800">划定识别区域</h3>
        <el-switch v-model="form.region_enabled" size="small" />
        <span class="text-sm text-gray-500">{{ form.region_enabled ? '已启用' : '未启用' }}</span>
      </div>

      <div v-if="form.region_enabled" class="space-y-2">
        <div
          ref="videoAreaRef"
          class="relative bg-black rounded-lg overflow-hidden select-none"
          style="height: 280px; cursor: crosshair;"
          @mousedown="onMouseDown"
          @mousemove="onMouseMove"
          @mouseup="onMouseUp"
          @mouseleave="onMouseUp"
        >
          <!-- 视频画面 -->
          <img
            v-if="connected"
            ref="videoImgRef"
            :src="frameUrl"
            class="w-full h-full object-contain pointer-events-none"
            alt="视频画面"
            @load="onImageLoad"
          />
          <div v-else class="w-full h-full flex items-center justify-center text-gray-400 text-sm">
            请先在右侧视频画面区域激活摄像头
          </div>

          <!-- 框选矩形 -->
          <div
            v-if="showRect"
            class="absolute border-2 border-green-400 bg-green-400/20 pointer-events-none"
            :style="rectStyle"
          />
        </div>

        <!-- 坐标显示与重置 -->
        <div class="flex items-center gap-3 text-xs text-gray-500">
          <span v-if="form.region_width < 0.99">
            选区: ({{ (form.region_x * 100).toFixed(0) }}%, {{ (form.region_y * 100).toFixed(0) }}%) —
            {{ (form.region_width * 100).toFixed(0) }}% × {{ (form.region_height * 100).toFixed(0) }}%
          </span>
          <span v-else class="text-gray-400">拖拽鼠标框选识别区域</span>
          <el-button
            v-if="form.region_width < 0.99"
            size="small"
            text
            type="primary"
            @click="resetRegion"
          >
            重置
          </el-button>
        </div>
      </div>
    </div>

    <el-divider />

    <!-- 识别方式选择 -->
    <div>
      <h3 class="text-base font-semibold text-gray-800 mb-3">识别方式选择</h3>
      <el-radio-group v-model="form.method" class="mb-4">
        <el-radio value="llm">大模型识别</el-radio>
        <el-radio value="local_vision">本地视觉识别</el-radio>
      </el-radio-group>

      <!-- 大模型配置 -->
      <div v-if="form.method === 'llm'" class="pl-6 space-y-3">
        <div class="flex items-center gap-3">
          <label class="w-20 text-sm text-gray-600 flex-shrink-0">API 地址</label>
          <el-input v-model="form.llm.api_url" size="small" placeholder="https://api.example.com/v1/chat" />
        </div>
        <div class="flex items-center gap-3">
          <label class="w-20 text-sm text-gray-600 flex-shrink-0">模型名称</label>
          <el-input v-model="form.llm.model_name" size="small" placeholder="gpt-4-vision-preview" />
        </div>
        <div class="flex items-center gap-3">
          <label class="w-20 text-sm text-gray-600 flex-shrink-0">API Key</label>
          <el-input
            v-model="form.llm.api_key"
            size="small"
            type="password"
            show-password
            placeholder="sk-..."
          />
        </div>
      </div>

      <!-- 本地视觉识别配置 -->
      <div v-if="form.method === 'local_vision'" class="pl-6 space-y-3">
        <div class="flex items-center gap-3">
          <label class="w-20 text-sm text-gray-600 flex-shrink-0">模型路径</label>
          <el-input v-model="form.local_vision.model_path" size="small" placeholder="/models/yolo/best.pt" />
        </div>
        <div class="flex items-center gap-3">
          <label class="w-20 text-sm text-gray-600 flex-shrink-0">置信度阈值</label>
          <div class="flex-1">
            <el-slider
              v-model="form.local_vision.confidence_threshold"
              :min="0"
              :max="1"
              :step="0.05"
              show-input
              size="small"
            />
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="onSave">保存配置</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch, computed, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { getRecognitionConfig, saveRecognitionConfig } from '@/api/acceptance'
import { getStatus as getVideoStatus, getFrameUrl } from '@/api/video'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  projectName: { type: String, required: true },
})

const emit = defineEmits(['update:modelValue', 'saved'])

// ── 对话框 ──
const dialogVisible = ref(false)

watch(() => props.modelValue, (v) => { dialogVisible.value = v })
watch(dialogVisible, (v) => { emit('update:modelValue', v) })

// ── 表单 ──
const defaultForm = () => ({
  method: 'llm',
  region_enabled: false,
  region_x: 0,
  region_y: 0,
  region_width: 1,
  region_height: 1,
  llm: { api_url: '', model_name: '', api_key: '' },
  local_vision: { model_path: '', confidence_threshold: 0.5 },
})

const form = reactive(defaultForm())

// ── 视频区域框选 ──
const videoAreaRef = ref(null)
const videoImgRef = ref(null)
const connected = ref(false)
const frameUrl = ref('')
let pollTimer = null

const drawing = ref(false)
const dragStart = ref({ x: 0, y: 0 })
const imgBounds = ref({ left: 0, top: 0, width: 0, height: 0 })

const showRect = computed(() => {
  return form.region_enabled && (drawing.value || form.region_width < 0.99)
})

const rectStyle = computed(() => {
  if (!showRect.value) return { display: 'none' }
  let x, y, w, h
  if (drawing.value) {
    x = Math.min(dragStart.value.x, dragCurrent.value.x)
    y = Math.min(dragStart.value.y, dragCurrent.value.y)
    w = Math.abs(dragCurrent.value.x - dragStart.value.x)
    h = Math.abs(dragCurrent.value.y - dragStart.value.y)
  } else {
    const b = imgBounds.value
    x = form.region_x * b.width
    y = form.region_y * b.height
    w = form.region_width * b.width
    h = form.region_height * b.height
  }
  return {
    left: x + 'px',
    top: y + 'px',
    width: w + 'px',
    height: h + 'px',
  }
})

const dragCurrent = ref({ x: 0, y: 0 })

function onImageLoad() {
  updateImgBounds()
}

function updateImgBounds() {
  const area = videoAreaRef.value
  const img = videoImgRef.value
  if (!area || !img) return
  const areaRect = area.getBoundingClientRect()
  const imgRect = img.getBoundingClientRect()
  imgBounds.value = {
    left: imgRect.left - areaRect.left,
    top: imgRect.top - areaRect.top,
    width: imgRect.width,
    height: imgRect.height,
  }
}

function clampToBounds(px, py) {
  const b = imgBounds.value
  return {
    x: Math.max(0, Math.min(px, b.width)),
    y: Math.max(0, Math.min(py, b.height)),
  }
}

function onMouseDown(e) {
  if (!form.region_enabled) return
  updateImgBounds()
  const area = videoAreaRef.value
  if (!area) return
  const rect = area.getBoundingClientRect()
  const pos = clampToBounds(e.clientX - rect.left - imgBounds.value.left, e.clientY - rect.top - imgBounds.value.top)
  dragStart.value = pos
  dragCurrent.value = pos
  drawing.value = true
}

function onMouseMove(e) {
  if (!drawing.value) return
  const area = videoAreaRef.value
  if (!area) return
  const rect = area.getBoundingClientRect()
  dragCurrent.value = clampToBounds(e.clientX - rect.left - imgBounds.value.left, e.clientY - rect.top - imgBounds.value.top)
}

function onMouseUp() {
  if (!drawing.value) return
  drawing.value = false
  const b = imgBounds.value
  if (b.width === 0 || b.height === 0) return

  const x1 = Math.min(dragStart.value.x, dragCurrent.value.x)
  const y1 = Math.min(dragStart.value.y, dragCurrent.value.y)
  const x2 = Math.max(dragStart.value.x, dragCurrent.value.x)
  const y2 = Math.max(dragStart.value.y, dragCurrent.value.y)
  const w = x2 - x1
  const h = y2 - y1

  // 忽略极小框选（小于 10px）
  if (w < 10 || h < 10) return

  form.region_x = x1 / b.width
  form.region_y = y1 / b.height
  form.region_width = w / b.width
  form.region_height = h / b.height
}

function resetRegion() {
  form.region_x = 0
  form.region_y = 0
  form.region_width = 1
  form.region_height = 1
}

// ── 视频帧轮询 ──
function startFramePolling() {
  stopFramePolling()
  frameUrl.value = getFrameUrl()
  pollTimer = setInterval(() => {
    frameUrl.value = getFrameUrl()
  }, 200)
}

function stopFramePolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  frameUrl.value = ''
}

// ── 生命周期 ──
async function onOpen() {
  // 加载已保存配置
  try {
    const config = await getRecognitionConfig(props.projectName)
    form.method = config.method || 'llm'
    form.region_enabled = config.region_enabled || false
    form.region_x = config.region_x ?? 0
    form.region_y = config.region_y ?? 0
    form.region_width = config.region_width ?? 1
    form.region_height = config.region_height ?? 1
    form.llm = { api_url: '', model_name: '', api_key: '' }
    if (config.llm) {
      form.llm.api_url = config.llm.api_url || ''
      form.llm.model_name = config.llm.model_name || ''
      form.llm.api_key = config.llm.api_key || ''
    }
    form.local_vision = { model_path: '', confidence_threshold: 0.5 }
    if (config.local_vision) {
      form.local_vision.model_path = config.local_vision.model_path || ''
      form.local_vision.confidence_threshold = config.local_vision.confidence_threshold ?? 0.5
    }
  } catch {
    // 使用默认值
  }

  // 检测视频连接状态
  try {
    const status = await getVideoStatus()
    connected.value = status.connected
    if (status.connected) {
      startFramePolling()
      await nextTick()
      updateImgBounds()
    }
  } catch {
    connected.value = false
  }
}

function onClose() {
  stopFramePolling()
  connected.value = false
  drawing.value = false
}

const saving = ref(false)

async function onSave() {
  saving.value = true
  try {
    const payload = {
      method: form.method,
      region_enabled: form.region_enabled,
      region_x: form.region_x,
      region_y: form.region_y,
      region_width: form.region_width,
      region_height: form.region_height,
      llm: { ...form.llm },
      local_vision: { ...form.local_vision },
    }
    await saveRecognitionConfig(props.projectName, payload)
    ElMessage.success('识别配置已保存')
    emit('saved', payload)
    dialogVisible.value = false
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '保存失败'
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}
</script>
