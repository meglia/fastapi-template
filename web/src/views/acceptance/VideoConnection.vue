<template>
  <div class="flex-1 bg-white rounded-lg shadow-sm flex flex-col min-h-0">
    <!-- 标题栏 + 控制区 -->
    <div class="px-4 py-3 border-b border-gray-200 flex-shrink-0">
      <div class="flex items-center justify-between">
        <h2 class="text-base font-semibold text-gray-800">视频画面</h2>
        <div class="flex items-center gap-2">
          <el-select
            v-model="selectedDeviceIndex"
            placeholder="选择视频设备"
            size="small"
            class="!w-44"
            :disabled="connected || loading"
          >
            <el-option
              v-for="d in devices"
              :key="d.device_index"
              :label="d.device_name"
              :value="d.device_index"
            />
          </el-select>
          <el-button
            :type="connected ? 'danger' : 'primary'"
            size="small"
            :loading="loading"
            :disabled="selectedDeviceIndex === null && !connected"
            @click="connected ? handleDisconnect() : handleConnect()"
          >
            {{ connected ? '取消激活' : '激活' }}
          </el-button>
          <el-button
            size="small"
            :icon="Refresh"
            circle
            :disabled="loading"
            @click="refreshDevices"
            title="刷新设备列表"
          />
        </div>
      </div>
    </div>

    <!-- 状态指示条 -->
    <div class="px-4 py-2 border-b border-gray-100 flex-shrink-0 flex items-center gap-3 text-xs">
      <span class="flex items-center gap-1.5">
        <span class="inline-block w-2 h-2 rounded-full" :class="statusDotClass" />
        <span :class="statusTextClass" class="font-medium">{{ statusLabel }}</span>
      </span>
      <span v-if="connected" class="text-gray-400">
        {{ activeDevice?.device_name }} | {{ resolution.width }}x{{ resolution.height }}
      </span>
    </div>

    <!-- 视频画面区域 -->
    <div class="flex-1 overflow-hidden flex items-center justify-center bg-black relative min-h-0">
      <img
        v-if="connected"
        :src="frameUrl"
        class="max-w-full max-h-full object-contain"
        alt="视频画面"
      />
      <el-empty
        v-else
        description="请选择设备并激活"
        :image-size="80"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import {
  getDevices,
  connectDevice,
  disconnectDevice,
  getStatus,
  getFrameUrl,
} from '@/api/video'

// ── 数据状态 ──
const devices = ref([])
const selectedDeviceIndex = ref(null)
const connected = ref(false)
const loading = ref(false)
const activeDevice = ref(null)
const resolution = ref({ width: 0, height: 0 })
const frameUrl = ref('')

let pollTimer = null

// ── 状态指示样式 ──
const statusDotClass = computed(() => {
  if (loading.value) return 'bg-yellow-400 animate-pulse'
  if (connected.value) return 'bg-green-500'
  return 'bg-gray-400'
})

const statusTextClass = computed(() => {
  if (loading.value) return 'text-yellow-600'
  if (connected.value) return 'text-green-600'
  return 'text-gray-500'
})

const statusLabel = computed(() => {
  if (loading.value) return '操作中...'
  if (connected.value) return '已连接'
  return '未连接'
})

// ── 设备操作 ──
async function refreshDevices() {
  try {
    const res = await getDevices()
    devices.value = res.devices || []
    // 若当前选中设备不再存在，清空选择
    if (selectedDeviceIndex.value !== null && !devices.value.some(d => d.device_index === selectedDeviceIndex.value)) {
      selectedDeviceIndex.value = null
    }
    if (devices.value.length === 0) {
      ElMessage.warning('未检测到视频设备')
    }
  } catch (e) {
    ElMessage.error('获取设备列表失败')
  }
}

async function handleConnect() {
  if (selectedDeviceIndex.value === null) {
    ElMessage.warning('请先选择视频设备')
    return
  }
  loading.value = true
  try {
    await connectDevice(selectedDeviceIndex.value)
    connected.value = true
    // 获取最新状态（分辨率等）
    const status = await getStatus()
    activeDevice.value = status.active_device
    resolution.value = status.resolution
    startFramePolling()
    ElMessage.success('视频设备已激活')
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '连接失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

async function handleDisconnect() {
  loading.value = true
  try {
    await disconnectDevice()
    connected.value = false
    activeDevice.value = null
    resolution.value = { width: 0, height: 0 }
    stopFramePolling()
    ElMessage.success('视频设备已断开')
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '断开失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

// ── 帧轮询 ──
function startFramePolling() {
  stopFramePolling()
  frameUrl.value = getFrameUrl()
  pollTimer = setInterval(() => {
    frameUrl.value = getFrameUrl()
  }, 100)
}

function stopFramePolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  frameUrl.value = ''
}

// ── 生命周期 ──
onMounted(async () => {
  // 先检查是否已有活跃连接（其他页面/刷新前可能已连接），再枚举设备
  let alreadyConnected = false
  try {
    const status = await getStatus()
    if (status.connected) {
      connected.value = true
      activeDevice.value = status.active_device
      resolution.value = status.resolution
      selectedDeviceIndex.value = status.active_device?.device_index ?? null
      startFramePolling()
      alreadyConnected = true
    }
  } catch {
    // 静默失败
  }

  // 刷新设备列表（后端已保护：不会干扰已连接设备）
  await refreshDevices()

  // 如果之前已连接，将已激活设备加入下拉列表（get_devices 已自动包含）
  if (alreadyConnected && activeDevice.value) {
    selectedDeviceIndex.value = activeDevice.value.device_index
  }
})

onUnmounted(() => {
  stopFramePolling()
})
</script>
