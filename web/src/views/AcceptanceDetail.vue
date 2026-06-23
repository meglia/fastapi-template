<template>
  <div class="acceptance-page h-screen flex flex-col bg-gray-50">
    <!-- 顶部导航栏 -->
    <header class="bg-white shadow-sm px-6 py-3 flex items-center gap-4 flex-shrink-0">
      <el-button :icon="ArrowLeft" @click="$router.push('/')">返回</el-button>
      <h1 class="text-xl font-semibold text-gray-800">{{ projectName }} — 验收</h1>
    </header>

    <!-- 主体：左右分栏 -->
    <div class="flex flex-1 p-4 gap-4 min-h-0">
      <!-- 左侧：遥控验收区域 3/4 -->
      <div class="flex-[3] bg-white rounded-lg shadow-sm flex flex-col min-h-0">
        <!-- 顶行：导入点表按钮 -->
        <div class="flex items-center gap-3 px-4 py-3 border-b border-gray-200 flex-shrink-0">
          <h2 class="text-lg font-semibold text-gray-800">遥控验收</h2>
          <el-button type="primary">导入点表</el-button>
        </div>
        <!-- 遥控验收内容区域 -->
        <div class="flex-1 p-4 overflow-auto">
          <el-empty description="遥控验收功能开发中" />
        </div>
      </div>

      <!-- 右侧：1/4，上下两半 -->
      <div class="flex-1 flex flex-col gap-4 min-h-0">
        <!-- 上半部：视频画面区域 -->
        <div class="flex-1 bg-white rounded-lg shadow-sm flex flex-col min-h-0">
          <div class="px-4 py-3 border-b border-gray-200 flex-shrink-0">
            <h2 class="text-base font-semibold text-gray-800">视频画面</h2>
          </div>
          <div class="flex-1 p-4 overflow-auto flex items-center justify-center">
            <el-empty description="视频连接功能开发中" :image-size="80" />
          </div>
        </div>

        <!-- 下半部：报文日志区域 -->
        <div class="flex-1 bg-white rounded-lg shadow-sm flex flex-col min-h-0">
          <div class="px-4 py-3 border-b border-gray-200 flex-shrink-0">
            <h2 class="text-base font-semibold text-gray-800">报文日志</h2>
          </div>
          <div class="flex-1 p-4 overflow-auto">
            <el-empty description="报文通讯功能开发中" :image-size="80" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'

const route = useRoute()
const projectName = ref(route.params.name)
</script>
