<template>
  <div class="acceptance-page h-screen flex flex-col bg-gray-50">
    <!-- 顶部导航栏 -->
    <header class="bg-white shadow-sm px-6 py-3 flex items-center gap-4 flex-shrink-0">
      <el-button :icon="ArrowLeft" @click="$router.push('/')">返回</el-button>
      <h1 class="text-xl font-semibold text-gray-800">{{ projectName }} — 监控后台遥控画面验收</h1>
      <el-button
        class="ml-auto"
        :icon="collapsed ? DArrowLeft : DArrowRight"
        circle
        @click="collapsed = !collapsed"
        title="折叠/展开右侧面板"
      />
    </header>

    <!-- 主体：左右分栏 -->
    <div class="flex flex-1 p-4 gap-4 min-h-0 min-w-0">
      <!-- 左侧：遥控验收区域，折叠时撑满 -->
      <div
        class="bg-white rounded-lg shadow-sm flex flex-col min-h-0 min-w-0 transition-all duration-300"
        :style="{ width: collapsed ? '100%' : '75%', flexShrink: collapsed ? '1' : '0' }"
      >
        <RemoteAcceptancePanel :project-name="projectName" />
      </div>

      <!-- 右侧：视频画面 + 通讯管理 -->
      <transition name="slide-fade">
        <div v-if="!collapsed" class="min-w-0 flex flex-col gap-4 min-h-0" style="flex: 1;">
          <VideoConnection />
          <MessageComm />
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, DArrowRight, DArrowLeft } from '@element-plus/icons-vue'
import RemoteAcceptancePanel from '@/views/acceptance/RemoteAcceptancePanel.vue'
import VideoConnection from '@/views/acceptance/VideoConnection.vue'
import MessageComm from '@/views/acceptance/MessageComm.vue'

const route = useRoute()
const projectName = computed(() => route.params.name)

const collapsed = ref(false)
</script>

<style scoped>
.slide-fade-enter-active {
  transition: all 0.3s ease-out;
}
.slide-fade-leave-active {
  transition: all 0.25s ease-in;
}
.slide-fade-enter-from {
  transform: translateX(20px);
  opacity: 0;
}
.slide-fade-leave-to {
  transform: translateX(20px);
  opacity: 0;
}
</style>
