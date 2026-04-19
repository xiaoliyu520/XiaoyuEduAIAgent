<template>
  <div class="documents-container">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <div style="display: flex; align-items: center; gap: 16px">
            <el-button text @click="goBack">
              <el-icon><ArrowLeft /></el-icon>
              返回
            </el-button>
            <span>{{ kbInfo?.name || '文档管理' }}</span>
          </div>
          <el-button type="primary" @click="showUploadDialog">
            <el-icon><Upload /></el-icon>
            上传文档
          </el-button>
        </div>
      </template>

      <div class="filter-bar">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索文档名称"
          style="width: 200px"
          clearable
          @clear="loadDocuments"
          @keyup.enter="loadDocuments"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select v-model="filterStatus" placeholder="文档状态" clearable style="width: 120px" @change="loadDocuments">
          <el-option label="活跃" value="active" />
          <el-option label="归档" value="archived" />
        </el-select>
        <el-button @click="loadDocuments">刷新</el-button>
      </div>

      <el-table :data="documents" stripe v-loading="loading">
        <el-table-column label="序号" width="70">
          <template #default="{ $index }">
            {{ (page - 1) * pageSize + $index + 1 }}
          </template>
        </el-table-column>
        <el-table-column prop="title" label="文档名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="file_type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag size="small">{{ row.file_type?.toUpperCase() }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="file_size" label="大小" width="100">
          <template #default="{ row }">
            {{ formatFileSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="文本块" width="80" />
        <el-table-column prop="version" label="版本" width="70">
          <template #default="{ row }">
            <el-tag type="info" size="small">v{{ row.version }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '活跃' : '归档' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="160">
          <template #default="{ row }">
            {{ formatTime(row.updated_at || row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="showVersions(row)">版本</el-button>
            <el-button
              size="small"
              :type="row.status === 'active' ? 'warning' : 'success'"
              @click="toggleStatus(row)"
            >
              {{ row.status === 'active' ? '归档' : '激活' }}
            </el-button>
            <el-button size="small" type="danger" @click="deleteDoc(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadDocuments"
          @current-change="loadDocuments"
        />
      </div>
    </el-card>

    <el-dialog v-model="uploadDialogVisible" title="上传文档" width="450px">
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        accept=".txt,.pdf,.doc,.docx,.md"
        :on-change="handleFileChange"
        drag
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽文件到此处或 <em>点击上传</em></div>
        <template #tip>
          <div class="upload-tip">支持 txt、pdf、doc、docx、md 格式，相同文件名将自动进行增量更新</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="uploadDoc" :loading="uploadLoading">上传</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="versionsDialogVisible" title="版本历史" width="600px">
      <el-table :data="versions" stripe>
        <el-table-column prop="version" label="版本" width="80">
          <template #default="{ row }">
            <el-tag type="info">v{{ row.version }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="change_type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="row.change_type === 'created' ? 'success' : 'warning'" size="small">
              {{ row.change_type === 'created' ? '新建' : '更新' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="文本块数" width="100" />
        <el-table-column prop="change_summary" label="变更说明" min-width="150" />
        <el-table-column prop="created_at" label="时间" width="160">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Upload, Search, UploadFilled } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const kbId = ref(route.query.kb_id)
const kbInfo = ref(null)
const documents = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const searchKeyword = ref('')
const filterStatus = ref('')

const uploadDialogVisible = ref(false)
const uploadLoading = ref(false)
const selectedFile = ref(null)
const uploadRef = ref(null)

const versionsDialogVisible = ref(false)
const versions = ref([])
const selectedDoc = ref(null)

async function loadKBInfo() {
  try {
    const res = await api.get('/knowledge/bases')
    const kbs = res.data || []
    kbInfo.value = kbs.find(kb => kb.id === parseInt(kbId.value))
  } catch {
    console.error('加载知识库信息失败')
  }
}

async function loadDocuments() {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (searchKeyword.value) {
      params.keyword = searchKeyword.value
    }
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    const res = await api.get(`/knowledge/bases/${kbId.value}/documents`, { params })
    documents.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch {
    ElMessage.error('加载文档列表失败')
  } finally {
    loading.value = false
  }
}

function goBack() {
  router.push('/knowledge')
}

function showUploadDialog() {
  selectedFile.value = null
  uploadDialogVisible.value = true
}

function handleFileChange(file) {
  selectedFile.value = file.raw
}

async function uploadDoc() {
  if (!selectedFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  uploadLoading.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    const res = await api.post(`/knowledge/bases/${kbId.value}/upload`, formData)
    uploadDialogVisible.value = false
    await loadDocuments()
    if (res.data?.unchanged) {
      ElMessage.info('文档内容未变化，无需更新')
    } else if (res.data?.is_new) {
      ElMessage.success(`上传成功，共 ${res.data?.chunks || 0} 个文本块`)
    } else {
      ElMessage.success(`更新成功，${res.data?.change_summary || ''}`)
    }
  } catch (e) {
    ElMessage.error(e.message || '上传失败')
  } finally {
    uploadLoading.value = false
  }
}

async function showVersions(doc) {
  selectedDoc.value = doc
  try {
    const res = await api.get(`/knowledge/documents/${doc.id}/versions`)
    versions.value = res.data || []
    versionsDialogVisible.value = true
  } catch {
    ElMessage.error('加载版本历史失败')
  }
}

async function toggleStatus(doc) {
  const newStatus = doc.status === 'active' ? 'archived' : 'active'
  const action = newStatus === 'archived' ? '归档' : '激活'
  try {
    await ElMessageBox.confirm(`确定要${action}该文档吗？`, '确认', { type: 'warning' })
    await api.put(`/knowledge/documents/${doc.id}/status?status=${newStatus}`)
    doc.status = newStatus
    ElMessage.success(`${action}成功`)
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.message || `${action}失败`)
    }
  }
}

async function deleteDoc(doc) {
  try {
    await ElMessageBox.confirm('确定删除该文档？此操作不可恢复。', '确认删除', { type: 'warning' })
    await api.delete(`/knowledge/documents/${doc.id}`)
    documents.value = documents.value.filter(d => d.id !== doc.id)
    total.value -= 1
    ElMessage.success('删除成功')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.message || '删除失败')
    }
  }
}

function formatFileSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatTime(time) {
  if (!time) return '-'
  const date = new Date(time)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(() => {
  loadKBInfo()
  loadDocuments()
})
</script>

<style scoped>
.documents-container {
  max-width: 1200px;
  margin: 0 auto;
}
.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.pagination-wrapper {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.upload-tip {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}
</style>
