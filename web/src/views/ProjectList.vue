<template>
  <div class="project-page min-h-screen bg-gray-100">
    <!-- 顶部标题栏 -->
    <header class="bg-white shadow-sm px-6 py-5">
      <h1 class="text-2xl font-bold text-gray-800">工程列表</h1>
      <p class="text-gray-500 mt-1 text-sm">监控后台·遥控画面验收</p>
    </header>

    <!-- 操作栏 -->
    <div class="px-6 py-4 flex justify-between items-center">
      <el-input
        v-model="searchText"
        placeholder="搜索工程名称..."
        clearable
        class="!w-64"
        :prefix-icon="Search"
      />
      <el-button type="primary" :icon="Plus" @click="showCreateDialog">新建工程</el-button>
    </div>

    <!-- 工程卡片列表 -->
    <div class="px-6 pb-8">
      <el-row v-if="filteredProjects.length" :gutter="16">
        <el-col
          v-for="project in filteredProjects"
          :key="project.name"
          :xs="24"
          :sm="12"
          :md="8"
          :lg="6"
          class="mb-4"
        >
          <el-card
            shadow="hover"
            class="project-card cursor-pointer transition-all duration-200 hover:shadow-md hover:-translate-y-0.5"
            @click="enterProject(project.name)"
          >
            <template #header>
              <div class="flex justify-between items-center">
                <span class="font-semibold text-base truncate max-w-[70%]" :title="project.name">
                  📁 {{ project.name }}
                </span>
                <div class="flex gap-1 flex-shrink-0">
                  <el-button
                    text
                    size="small"
                    :icon="Edit"
                    @click.stop="showEditDialog(project)"
                  />
                  <el-button
                    text
                    size="small"
                    type="danger"
                    :icon="Delete"
                    @click.stop="confirmDelete(project)"
                  />
                </div>
              </div>
            </template>
            <p class="text-gray-600 text-sm min-h-[2.5rem] line-clamp-2">
              {{ project.description || '暂无描述' }}
            </p>
            <div class="text-gray-400 text-xs mt-2">
              创建时间：{{ project.created_time ? formatTime(project.created_time) : '未知' }}
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 空状态 -->
      <el-empty v-else description="暂无工程，点击右上角「新建工程」开始">
        <el-button type="primary" @click="showCreateDialog">新建工程</el-button>
      </el-empty>
    </div>

    <!-- 新建工程对话框 -->
    <el-dialog v-model="createVisible" title="新建工程" width="480px" :close-on-click-modal="false">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="80px">
        <el-form-item label="工程名称" prop="name">
          <el-input v-model="createForm.name" placeholder="请输入工程名称" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item label="工程描述" prop="description">
          <el-input
            v-model="createForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入工程描述（可选）"
            maxlength="512"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">确定</el-button>
      </template>
    </el-dialog>

    <!-- 编辑工程对话框 -->
    <el-dialog v-model="editVisible" title="编辑工程" width="480px" :close-on-click-modal="false">
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="80px">
        <el-form-item label="工程名称" prop="name">
          <el-input v-model="editForm.name" placeholder="请输入新工程名称" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item label="工程描述" prop="description">
          <el-input
            v-model="editForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入工程描述"
            maxlength="512"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Edit, Delete } from '@element-plus/icons-vue'
import { listProjects, createProject, renameProject, updateProject, deleteProject } from '@/api/project'

const router = useRouter()

// ── 列表状态 ──
const projects = ref([])
const searchText = ref('')
const filteredProjects = computed(() => {
  if (!searchText.value) return projects.value
  const kw = searchText.value.toLowerCase()
  return projects.value.filter((p) => p.name.toLowerCase().includes(kw))
})

// ── 创建表单 ──
const createVisible = ref(false)
const creating = ref(false)
const createFormRef = ref(null)
const createForm = ref({ name: '', description: '' })
const createRules = {
  name: [{ required: true, message: '请输入工程名称', trigger: 'blur' }],
}

function showCreateDialog() {
  createForm.value = { name: '', description: '' }
  createVisible.value = true
}

async function handleCreate() {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return
  creating.value = true
  try {
    await createProject(createForm.value)
    ElMessage.success('工程创建成功')
    createVisible.value = false
    await fetchProjects()
  } catch {
    // 错误已在拦截器处理
  } finally {
    creating.value = false
  }
}

// ── 编辑表单 ──
const editVisible = ref(false)
const saving = ref(false)
const editFormRef = ref(null)
const editingName = ref('')
const editForm = ref({ name: '', description: '' })
const editRules = {
  name: [{ required: true, message: '请输入工程名称', trigger: 'blur' }],
}

function showEditDialog(project) {
  editingName.value = project.name
  editForm.value = { name: project.name, description: project.description || '' }
  editVisible.value = true
}

async function handleEdit() {
  const valid = await editFormRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    // 先改名（如果名称变动）
    if (editForm.value.name !== editingName.value) {
      await renameProject(editingName.value, { new_name: editForm.value.name })
    }
    // 再更新描述
    await updateProject(editForm.value.name, { description: editForm.value.description })
    ElMessage.success('工程信息已更新')
    editVisible.value = false
    await fetchProjects()
  } catch {
    // 错误已在拦截器处理
  } finally {
    saving.value = false
  }
}

// ── 删除 ──
async function confirmDelete(project) {
  try {
    await ElMessageBox.confirm(
      `确定要删除工程「${project.name}」吗？该操作不可恢复！`,
      '删除确认',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' },
    )
    await deleteProject(project.name)
    ElMessage.success('工程已删除')
    await fetchProjects()
  } catch {
    // 取消或错误
  }
}

// ── 进入验收页 ──
function enterProject(name) {
  router.push(`/acceptance/${encodeURIComponent(name)}`)
}

// ── 数据加载 ──
async function fetchProjects() {
  try {
    projects.value = await listProjects()
  } catch {
    projects.value = []
  }
}

onMounted(() => {
  fetchProjects()
})

function formatTime(isoStr) {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  if (isNaN(d.getTime())) return isoStr
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
</script>

<style scoped>
.project-card :deep(.el-card__header) {
  padding: 12px 16px;
}
.project-card :deep(.el-card__body) {
  padding: 12px 16px;
}
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
