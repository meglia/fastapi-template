<template>
  <el-dialog
    :model-value="modelValue"
    title="导入验收表"
    width="720px"
    :close-on-click-modal="false"
    @closed="resetDialog"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <!-- 步骤 1：上传文件 -->
    <div class="mb-6">
      <div class="text-sm font-medium text-gray-700 mb-2">1. 选择 Excel 文件</div>
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        accept=".xls,.xlsx"
        drag
        :on-change="handleFileChange"
        :on-remove="handleFileRemove"
        :file-list="fileList"
      >
        <el-icon class="el-icon--upload text-3xl text-gray-400 mb-2"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          将 Excel 文件拖到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="text-xs text-gray-400 mt-1">支持 .xls / .xlsx 格式</div>
        </template>
      </el-upload>
    </div>

    <!-- 步骤 2：字段映射 -->
    <div v-if="uploadResult" class="mb-6">
      <div class="text-sm font-medium text-gray-700 mb-2">2. 字段映射</div>
      <div class="grid grid-cols-3 gap-4">
        <el-form-item label="工作簿" label-position="top">
          <el-select v-model="mapping.workbook" placeholder="选择工作簿" class="w-full" @change="onWorkbookChange">
            <el-option
              v-for="wb in uploadResult.workbooks"
              :key="wb.name"
              :label="wb.name"
              :value="wb.name"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="点号列" label-position="top">
          <el-select v-model="mapping.point_column" placeholder="选择点号列" class="w-full" filterable>
            <el-option
              v-for="col in currentColumns"
              :key="col"
              :label="col"
              :value="col"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="描述列" label-position="top">
          <el-select v-model="mapping.desc_column" placeholder="选择描述列" class="w-full" filterable>
            <el-option
              v-for="col in currentColumns"
              :key="col"
              :label="col"
              :value="col"
            />
          </el-select>
        </el-form-item>
      </div>
      <div class="flex justify-end mt-2">
        <el-button type="primary" :loading="previewing" :disabled="!canPreview" @click="handlePreview">
          预览数据
        </el-button>
      </div>
    </div>

    <!-- 步骤 3：数据预览 -->
    <div v-if="previewData" class="mb-4">
      <div class="text-sm font-medium text-gray-700 mb-2">
        3. 数据预览
        <span class="text-gray-400 font-normal ml-2">共 {{ previewData.total_count }} 条记录</span>
      </div>
      <el-table :data="previewData.rows.slice(0, 10)" border stripe size="small" max-height="300">
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column prop="point_number" label="点号" min-width="150" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
      </el-table>
      <div v-if="previewData.total_count > 10" class="text-xs text-gray-400 text-center mt-1">
        仅显示前 10 条
      </div>
    </div>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="!previewData" @click="handleSave">
        保存
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { uploadAcceptance, previewAcceptance, saveAcceptance } from '@/api/acceptance'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  projectName: { type: String, required: true },
})

const emit = defineEmits(['update:modelValue', 'saved'])

// ── 对话框状态 ──
const uploadRef = ref(null)
const fileList = ref([])
const uploading = ref(false)
const uploadResult = ref(null)
const previewing = ref(false)
const previewData = ref(null)
const saving = ref(false)

// ── 字段映射 ──
const mapping = ref({
  workbook: '',
  point_column: '',
  desc_column: '',
})

const currentColumns = computed(() => {
  if (!uploadResult.value || !mapping.value.workbook) return []
  const wb = uploadResult.value.workbooks.find(w => w.name === mapping.value.workbook)
  return wb ? wb.columns : []
})

const canPreview = computed(() => {
  return mapping.value.workbook && mapping.value.point_column && mapping.value.desc_column
})

// 对话框打开时重置
watch(() => props.modelValue, (val) => {
  if (val) resetDialog()
})

function resetDialog() {
  fileList.value = []
  uploadResult.value = null
  previewData.value = null
  mapping.value = { workbook: '', point_column: '', desc_column: '' }
  uploading.value = false
  previewing.value = false
  saving.value = false
}

// ── 文件变更 ──
async function handleFileChange(file) {
  fileList.value = [file]
  uploading.value = true
  uploadResult.value = null
  previewData.value = null
  mapping.value = { workbook: '', point_column: '', desc_column: '' }

  try {
    const result = await uploadAcceptance(props.projectName, file.raw)
    uploadResult.value = result
    if (result.workbooks.length > 0) {
      mapping.value.workbook = result.workbooks[0].name
    }
    ElMessage.success(`文件解析成功，共 ${result.workbooks.length} 个工作簿`)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || err?.message || '文件上传失败')
    fileList.value = []
  } finally {
    uploading.value = false
  }
}

function handleFileRemove() {
  fileList.value = []
  uploadResult.value = null
  previewData.value = null
  mapping.value = { workbook: '', point_column: '', desc_column: '' }
}

function onWorkbookChange() {
  mapping.value.point_column = ''
  mapping.value.desc_column = ''
  previewData.value = null
}

// ── 预览 ──
async function handlePreview() {
  if (!canPreview.value) return
  previewing.value = true
  previewData.value = null
  try {
    const result = await previewAcceptance(props.projectName, {
      workbook: mapping.value.workbook,
      point_column: mapping.value.point_column,
      desc_column: mapping.value.desc_column,
    })
    previewData.value = result
    ElMessage.success(`预览成功，共 ${result.total_count} 条记录`)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '预览失败')
  } finally {
    previewing.value = false
  }
}

// ── 保存 ──
async function handleSave() {
  if (!previewData.value) return
  saving.value = true
  try {
    await saveAcceptance(props.projectName, {
      workbook: mapping.value.workbook,
      point_column: mapping.value.point_column,
      desc_column: mapping.value.desc_column,
    })
    ElMessage.success('验收表保存成功')
    emit('update:modelValue', false)
    emit('saved', {
      rows: previewData.value.rows,
      fileName: uploadResult.value?.file_name || '',
    })
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>
