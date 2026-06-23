<template>
  <div class="flex-1 bg-white rounded-lg shadow-sm flex flex-col min-h-0">
    <!-- 标题栏 -->
    <div class="px-4 py-3 border-b border-gray-200 flex-shrink-0 flex items-center justify-between">
      <h2 class="text-base font-semibold text-gray-800">通讯管理</h2>
      <el-button :icon="Setting" size="small" circle @click="configDialogVisible = true" title="通讯配置" />
    </div>

    <!-- 状态指示条 -->
    <div class="px-4 py-2 border-b border-gray-100 flex-shrink-0 flex items-center gap-3 text-xs">
      <span class="flex items-center gap-1.5">
        <span class="inline-block w-2 h-2 rounded-full" :class="statusDotClass" />
        <span :class="statusTextClass" class="font-medium">{{ statusLabel }}</span>
      </span>
      <span v-if="connected" class="text-gray-400">
        发送 {{ sentCount }} / 接收 {{ recvCount }}
      </span>
    </div>

    <!-- 报文日志区 -->
    <div class="flex-1 flex flex-col min-h-0">
      <div class="px-3 py-1.5 flex items-center justify-between flex-shrink-0">
        <span class="text-xs text-gray-400">共 {{ messages.length }} 条</span>
        <div class="flex gap-2 items-center">
          <el-checkbox v-model="configForm.remoteOnly" size="small">只接收遥控报文</el-checkbox>
          <el-checkbox v-model="autoScroll" size="small">自动滚动</el-checkbox>
          <el-button size="small" text :icon="Delete" @click="clearMessages" class="!h-5">清空</el-button>
        </div>
      </div>

      <div ref="logContainer" class="log-container flex-1 overflow-y-auto bg-gray-900 font-mono text-sm min-h-0">
        <div v-if="messages.length === 0" class="flex items-center justify-center h-full text-gray-500">
          <el-empty description="暂无报文，请先连接设备" :image-size="60" />
        </div>
        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          class="log-line px-3 py-0.5 border-b border-gray-800 hover:bg-gray-800/50 transition-colors"
        >
          <span class="text-gray-500 mr-2 flex-shrink-0 text-xs">{{ formatTimestamp(msg.timestamp) }}</span>

          <!-- 遥控报文 (0xFB)：红色，显示解析字段 -->
          <div v-if="msg.extra?.asdu_type === 0xFB && msg.extra?.signal" class="text-red-300 break-all flex flex-col gap-0.5">
            <div class="text-red-400 font-semibold">{{ msg.content }}</div>
            <div class="ml-4 text-xs space-y-0.5">
              <div><span class="text-gray-500">描述:</span> {{ msg.extra.signal.description }}</div>
              <div><span class="text-gray-500">路径:</span> {{ msg.extra.signal.path }}</div>
              <div>
                <span class="text-gray-500">状态:</span>
                <span :class="msg.extra.signal.state === 0x0A ? 'text-green-400' : 'text-orange-400'">
                  {{ msg.extra.signal.state_label }}
                </span>
              </div>
              <div><span class="text-gray-500">品质:</span> 0x{{ msg.extra.signal.quality?.toString(16).toUpperCase().padStart(2, '0') }}</div>
              <div><span class="text-gray-500">时间:</span> {{ msg.extra.signal.signal_ts_str }}</div>
            </div>
          </div>

          <!-- 遥控报文解析失败 -->
          <span v-else-if="msg.extra?.asdu_type === 0xFB" class="text-red-300 break-all">{{ msg.content }}</span>

          <!-- 其他报文：根据 frame_type 着色 -->
          <span v-else class="break-all text-xs" :class="msgColorClass(msg)">{{ msg.content }}</span>
        </div>
      </div>
    </div>

    <!-- 通讯配置模态框 -->
    <el-dialog v-model="configDialogVisible" title="通讯配置" width="420px" :close-on-click-modal="false" destroy-on-close>
      <el-form :model="configForm" label-width="90px" size="default">
        <el-form-item label="IP 地址">
          <el-select v-model="configForm.host" class="!w-full">
            <el-option label="R1 — 192.168.56.166" value="192.168.56.166" />
            <el-option label="R2 — 192.168.66.166" value="192.168.66.166" />
            <el-option label="R3 — 192.168.76.166" value="192.168.76.166" />
            <el-option label="R4 — 192.168.86.166" value="192.168.86.166" />
          </el-select>
        </el-form-item>
        <el-form-item label="端口">
          <el-input-number v-model="configForm.port" :min="1" :max="65535" class="!w-full" />
        </el-form-item>
        <el-form-item label="协议类型">
          <el-select v-model="configForm.protocol_type" class="!w-full">
            <el-option label="LRK-CAPTURE" value="lrkcapture" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="flex justify-between">
          <el-button @click="configDialogVisible = false">关闭</el-button>
          <el-button
            :type="connected ? 'danger' : 'primary'"
            :loading="connecting"
            :icon="connected ? Close : Link"
            @click="connected ? handleDisconnect() : handleConnect()"
          >
            {{ connected ? '断开连接' : '连接设备' }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Setting, Link, Close, Delete } from '@element-plus/icons-vue'
import { connectDevice, disconnectDevice, getStatus, getMessages, setRemoteOnly, clearMessages as clearBackendMessages } from '@/api/communication'

// ── 配置表单 ──
const configForm = ref({
  host: '192.168.86.166',   // 默认 R4
  port: 4042,
  protocol_type: 'lrkcapture',
  remoteOnly: true,          // 默认勾选
})

// ── 状态 ──
const connecting = ref(false)
const connected = ref(false)
const reconnecting = ref(false)
const statusMessage = ref('')
const sentCount = ref(0)
const recvCount = ref(0)
const configDialogVisible = ref(false)

const statusDotClass = computed(() => {
  if (connecting.value || reconnecting.value) return 'bg-yellow-400 animate-pulse'
  if (connected.value) return 'bg-green-500'
  return 'bg-gray-400'
})

const statusLabel = computed(() => {
  if (connecting.value) return '连接中...'
  if (connected.value) return '已连接'
  if (reconnecting.value) return '未连接...正在自动尝试重连'
  return '未连接'
})

const statusTextClass = computed(() => {
  if (connecting.value || reconnecting.value) return 'text-yellow-600'
  if (connected.value) return 'text-green-600'
  return 'text-gray-500'
})

// ── 报文日志 ──
const messages = ref([])
const autoScroll = ref(true)
const logContainer = ref(null)
let lastSince = 0
let pollTimer = null

function formatTimestamp(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${String(d.getMilliseconds()).padStart(3, '0')}`
}

async function clearMessages() {
  messages.value = []
  sentCount.value = 0
  recvCount.value = 0
  // 同步清空后端缓冲区
  if (connected.value) {
    clearBackendMessages({
      host: configForm.value.host,
      port: configForm.value.port,
      protocol_type: configForm.value.protocol_type,
    }).catch(() => {})
  }
}

function msgColorClass(msg) {
  const ft = msg.extra?.frame_type
  const at = msg.extra?.asdu_type
  if (ft === 'U') return 'text-blue-300'
  if (ft === 'I' && at === 0xAA) return 'text-white'
  if (ft === 'I' && at === 0xFB) return 'text-red-300'
  return 'text-yellow-300'
}

function scrollToBottom() {
  if (!autoScroll.value) return
  nextTick(() => {
    const el = logContainer.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

// ── 监听 remoteOnly 变化，同步到后端 ──
watch(() => configForm.value.remoteOnly, async (enabled) => {
  if (!connected.value) return
  try {
    await setRemoteOnly({
      host: configForm.value.host,
      port: configForm.value.port,
      protocol_type: configForm.value.protocol_type,
      enabled,
    })
  } catch {
    // 失败时回滚
    configForm.value.remoteOnly = !enabled
  }
})

// ── 连接 / 断开 ──
async function handleConnect() {
  connecting.value = true
  try {
    await connectDevice({
      host: configForm.value.host,
      port: configForm.value.port,
      protocol_type: configForm.value.protocol_type,
    })
    connected.value = true
    statusMessage.value = `已连接 ${configForm.value.host}:${configForm.value.port}`
    ElMessage.success('设备连接成功')
    // 连接成功后同步 remoteOnly 状态
    if (configForm.value.remoteOnly) {
      await setRemoteOnly({
        host: configForm.value.host,
        port: configForm.value.port,
        protocol_type: configForm.value.protocol_type,
        enabled: true,
      }).catch(() => {})
    }
    configDialogVisible.value = false
    startPolling()
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '连接失败'
    statusMessage.value = msg
    ElMessage.error(msg)
  } finally {
    connecting.value = false
  }
}

async function handleDisconnect() {
  connecting.value = true
  try {
    await disconnectDevice({
      host: configForm.value.host,
      port: configForm.value.port,
      protocol_type: configForm.value.protocol_type,
    })
    connected.value = false
    statusMessage.value = '已断开'
    ElMessage.success('设备已断开')
    stopPolling()
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '断开失败'
    ElMessage.error(msg)
  } finally {
    connecting.value = false
  }
}

// ── 轮询 ──
function startPolling() {
  lastSince = Date.now() / 1000
  stopPolling()
  pollTimer = setInterval(pollMessages, 800)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function pollMessages() {
  try {
    const newMsgs = await getMessages(lastSince)
    if (newMsgs && newMsgs.length > 0) {
      const maxTs = Math.max(...newMsgs.map(m => m.timestamp || 0))
      if (maxTs > lastSince) lastSince = maxTs

      messages.value.push(...newMsgs)

      for (const m of newMsgs) {
        if (m.direction === 'send') sentCount.value++
        else if (m.direction === 'recv') recvCount.value++
      }

      if (messages.value.length > 1000) {
        messages.value = messages.value.slice(-800)
      }

      scrollToBottom()
    }

    // 同步拉取状态
    try {
      const status = await getStatus()
      if (status && Object.keys(status).length > 0) {
        const firstKey = Object.keys(status)[0]
        const s = status[firstKey]
        if (s) {
          if (s.status === 'CONNECTED') {
            connected.value = true
            reconnecting.value = false
          } else {
            connected.value = false
            // CONNECTING 且非手动触发 → 自动重连中
            if (s.status === 'CONNECTING' && !connecting.value) {
              reconnecting.value = true
            } else if (s.status === 'ERROR' || s.status === 'DISCONNECTED') {
              // 后端状态消息中包含重连关键词则保留重连标识
              const msg = s.status_message || ''
              reconnecting.value = msg.includes('重连') || msg.includes('重试')
            }
          }
          statusMessage.value = s.status_message || ''
        }
      }
    } catch {
      // 状态查询静默失败
    }
  } catch {
    // 静默失败
  }
}

// ── 加载历史报文 ──
async function loadHistoricalMessages() {
  try {
    const allMsgs = await getMessages(0)
    if (allMsgs && allMsgs.length > 0) {
      messages.value = allMsgs
      const maxTs = Math.max(...allMsgs.map(m => m.timestamp || 0))
      if (maxTs > 0) lastSince = maxTs
      for (const m of allMsgs) {
        if (m.direction === 'send') sentCount.value++
        else if (m.direction === 'recv') recvCount.value++
      }
      scrollToBottom()
    }
  } catch {
    // 静默失败
  }
}

onMounted(async () => {
  try {
    const status = await getStatus()
    if (status && Object.keys(status).length > 0) {
      const firstKey = Object.keys(status)[0]
      const s = status[firstKey]
      if (s && s.status === 'CONNECTED') {
        connected.value = true
        statusMessage.value = s.status_message || ''
        configForm.value.remoteOnly = !!s.remote_only
        if (s.config) {
          configForm.value.host = s.config.host || '192.168.86.166'
          configForm.value.port = s.config.port || 4042
          configForm.value.protocol_type = s.config.protocol_type || 'lrkcapture'
        }
        await loadHistoricalMessages()
        startPolling()
      }
    }
  } catch {
    // 静默失败
  }
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.log-line {
  display: flex;
  align-items: flex-start;
  white-space: pre-wrap;
  word-break: break-all;
}

.log-container::-webkit-scrollbar {
  width: 6px;
}
.log-container::-webkit-scrollbar-track {
  background: #1f2937;
}
.log-container::-webkit-scrollbar-thumb {
  background: #4b5563;
  border-radius: 3px;
}
.log-container::-webkit-scrollbar-thumb:hover {
  background: #6b7280;
}
</style>
