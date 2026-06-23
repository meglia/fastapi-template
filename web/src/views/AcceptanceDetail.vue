<template>
  <div class="acceptance-page min-h-screen bg-gray-50">
    <!-- 顶部导航栏 -->
    <header class="bg-white shadow-sm px-6 py-4 flex items-center gap-4">
      <el-button :icon="ArrowLeft" @click="$router.push('/')">返回</el-button>
      <h1 class="text-xl font-semibold text-gray-800">{{ projectName }} — 验收</h1>
    </header>

    <!-- Tab 容器 -->
    <div class="px-6 py-4">
      <el-tabs v-model="activeTab" type="border-card" class="bg-white rounded-lg shadow-sm">
        <el-tab-pane label="遥控验收" name="remote">
          <RemoteAcceptance />
        </el-tab-pane>
        <el-tab-pane label="点表管理" name="point">
          <PointTable />
        </el-tab-pane>
        <el-tab-pane label="视频连接" name="video">
          <VideoConnection />
        </el-tab-pane>
        <el-tab-pane label="报文通讯" name="message">
          <MessageComm />
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import RemoteAcceptance from './tabs/RemoteAcceptance.vue'
import PointTable from './tabs/PointTable.vue'
import VideoConnection from './tabs/VideoConnection.vue'
import MessageComm from './tabs/MessageComm.vue'

const route = useRoute()
const projectName = ref(route.params.name)
const activeTab = ref('remote')
</script>
