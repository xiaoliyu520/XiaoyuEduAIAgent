<template>
  <div class="knowledge-container">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>知识库管理</span>
          <el-button type="primary" @click="showCreateDialog">创建知识库</el-button>
        </div>
      </template>
      <el-table :data="knowledgeBases" stripe>
        <el-table-column label="序号" width="80">
          <template #default="{ $index }">
            {{ $index + 1 }}
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="doc_count" label="文档数" width="100" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '活跃' : row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="showUploadDialog(row)">
              上传文档
            </el-button>
            <el-button size="small" type="success" @click="manageDocuments(row)">
              管理文档
            </el-button>
            <el-button size="small" type="danger" @click="deleteKB(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createDialogVisible" title="创建知识库" width="400px">
      <el-form :model="createForm" label-position="top">
        <el-form-item label="名称">
          <el-input v-model="createForm.name" placeholder="请输入知识库名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" placeholder="请输入知识库描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="createKB" :loading="createLoading">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="uploadDialogVisible" title="上传文档" width="400px">
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        accept=".txt,.pdf,.doc,.docx,.md"
        :on-change="handleFileChange"
      >
        <el-button type="primary">选择文件</el-button>
        <template #tip>
          <div class="upload-tip">支持 txt、pdf、doc、docx、md 格式</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="uploadDoc" :loading="uploadLoading">上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const knowledgeBases = ref([])
const createDialogVisible = ref(false)
const createLoading = ref(false)
const createForm = ref({ name: '', description: '' })

const uploadDialogVisible = ref(false)
const uploadLoading = ref(false)
const selectedKB = ref(null)
const selectedFile = ref(null)
const uploadRef = ref(null)

async function loadKBs() {
  try {
    const res = await api.get('/knowledge/bases')
    knowledgeBases.value = res.data || []
  } catch {
    ElMessage.error('加载知识库失败')
  }
}

function showCreateDialog() {
  createForm.value = { name: '', description: '' }
  createDialogVisible.value = true
}

async function createKB() {
  createLoading.value = true
  try {
    const res = await api.post('/knowledge/bases', { ...createForm.value, tenant_id: 'default' })
    createDialogVisible.value = false
    knowledgeBases.value.push(res.data)
    ElMessage.success('创建成功')
  } catch (e) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    createLoading.value = false
  }
}

async function deleteKB(row) {
  try {
    await ElMessageBox.confirm('确定删除该知识库？', '确认', { type: 'warning' })
    await api.delete(`/knowledge/bases/${row.id}`)
    knowledgeBases.value = knowledgeBases.value.filter(kb => kb.id !== row.id)
    ElMessage.success('删除成功')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.message || '删除失败')
    }
  }
}

function showUploadDialog(kb) {
  selectedKB.value = kb
  selectedFile.value = null
  uploadDialogVisible.value = true
}

function manageDocuments(kb) {
  router.push({ path: '/documents', query: { kb_id: kb.id } })
}

function handleFileChange(file) {
  selectedFile.value = file.raw
}

async function uploadDoc() {
  if (!selectedFile.value || !selectedKB.value) return
  uploadLoading.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    await api.post(`/knowledge/bases/${selectedKB.value.id}/upload`, formData)
    uploadDialogVisible.value = false
    await loadKBs()
    ElMessage.success('上传成功')
  } catch (e) {
    ElMessage.error(e.message || '上传失败')
  } finally {
    uploadLoading.value = false
  }
}

onMounted(loadKBs)
</script>

<style scoped>
.knowledge-container {
  max-width: 1000px;
  margin: 0 auto;
}
.upload-tip {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}
</style>
