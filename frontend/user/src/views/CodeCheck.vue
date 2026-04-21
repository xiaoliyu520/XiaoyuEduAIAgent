<template>
  <div class="code-container">
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>代码输入</span>
              <el-select v-model="language" style="width: 150px" size="small">
                <el-option label="Python" value="python" />
                <el-option label="JavaScript" value="javascript" />
                <el-option label="Java" value="java" />
                <el-option label="C++" value="cpp" />
                <el-option label="Go" value="go" />
              </el-select>
            </div>
          </template>
          <el-input
            v-model="code"
            type="textarea"
            :rows="20"
            placeholder="在此输入代码..."
            style="font-family: 'Fira Code', monospace"
          />
          <el-button
            type="primary"
            @click="checkCode"
            :loading="loading"
            style="margin-top: 16px; width: 100%"
          >
            检查代码
          </el-button>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card v-if="result" class="result-card">
          <template #header>
            <span>检查结果</span>
          </template>
          <div class="result-content" v-html="renderMarkdown(result)"></div>
        </el-card>
        <el-card v-else class="empty-card">
          <el-empty description="输入代码并点击检查" />
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 20px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>检查历史</span>
          <el-button size="small" @click="loadHistory" :loading="historyLoading">
            刷新
          </el-button>
        </div>
      </template>
      <el-table :data="historyList" style="width: 100%" v-loading="historyLoading">
        <el-table-column prop="language" label="语言" width="100" />
        <el-table-column prop="code_preview" label="代码预览" min-width="300">
          <template #default="{ row }">
            <el-text truncated>{{ row.code_preview }}</el-text>
          </template>
        </el-table-column>
        <el-table-column prop="execution_status" label="执行状态" width="150">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.execution_status)" size="small">
              {{ row.execution_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewDetail(row.id)">
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="detailDialogVisible" title="检查详情" width="80%">
      <div v-if="detailLoading" style="text-align: center; padding: 40px">
        <el-icon class="is-loading" :size="40"><Loading /></el-icon>
      </div>
      <div v-else-if="detailData">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="语言">{{ detailData.language }}</el-descriptions-item>
          <el-descriptions-item label="执行状态">
            <el-tag :type="getStatusType(detailData.execution_status)">
              {{ detailData.execution_status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="检查时间" :span="2">
            {{ formatTime(detailData.created_at) }}
          </el-descriptions-item>
        </el-descriptions>
        
        <el-divider content-position="left">代码</el-divider>
        <pre class="code-block">{{ detailData.code }}</pre>
        
        <el-divider content-position="left">检查报告</el-divider>
        <div class="result-content" v-html="renderMarkdown(detailData.final_report)"></div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { marked } from 'marked'
import { useUserStore } from '../stores/user'

const code = ref('')
const language = ref('python')
const loading = ref(false)
const result = ref('')

const historyList = ref([])
const historyLoading = ref(false)

const detailDialogVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref(null)

const userStore = useUserStore()

function renderMarkdown(text) {
  if (!text) return ''
  return marked.parse(text)
}

function getStatusType(status) {
  if (status === 'Accepted' || status === 'Success') return 'success'
  if (status === 'Internal Error' || status === 'Execution Failed') return 'danger'
  if (status === 'Time Limit Exceeded' || status === 'Memory Limit Exceeded') return 'warning'
  return 'info'
}

function formatTime(isoString) {
  if (!isoString) return ''
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

async function checkCode() {
  if (!code.value.trim()) {
    ElMessage.warning('请输入代码')
    return
  }
  loading.value = true
  result.value = ''
  
  try {
    const response = await fetch('/api/v1/code/check', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${userStore.token}`,
      },
      body: JSON.stringify({
        code: code.value,
        language: language.value,
      }),
    })

    if (!response.ok) {
      throw new Error('请求失败')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const text = decoder.decode(value)
      const lines = text.split('\n')

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.content) {
              result.value += data.content
            }
            if (data.done) {
              ElMessage.success('代码检查完成')
              loadHistory()
            }
            if (data.error) {
              ElMessage.error(data.error)
            }
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
    }
  } catch (e) {
    ElMessage.error('检查失败，请重试')
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const response = await fetch('/api/v1/code/history', {
      headers: {
        'Authorization': `Bearer ${userStore.token}`,
      },
    })
    if (!response.ok) throw new Error('获取历史失败')
    const data = await response.json()
    historyList.value = data.data || []
  } catch (e) {
    ElMessage.error('获取历史记录失败')
  } finally {
    historyLoading.value = false
  }
}

async function viewDetail(id) {
  detailDialogVisible.value = true
  detailLoading.value = true
  detailData.value = null
  
  try {
    const response = await fetch(`/api/v1/code/history/${id}`, {
      headers: {
        'Authorization': `Bearer ${userStore.token}`,
      },
    })
    if (!response.ok) throw new Error('获取详情失败')
    const data = await response.json()
    detailData.value = data.data
  } catch (e) {
    ElMessage.error('获取详情失败')
    detailDialogVisible.value = false
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => {
  loadHistory()
})
</script>

<style scoped>
.code-container {
  max-width: 1200px;
  margin: 0 auto;
}
.result-card {
  min-height: calc(100vh - 180px);
}
.empty-card {
  min-height: calc(100vh - 180px);
  display: flex;
  align-items: center;
  justify-content: center;
}
.result-content {
  line-height: 1.8;
  font-size: 14px;
}
.result-content :deep(pre) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
}
.result-content :deep(code) {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
}
.code-block {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-wrap: break-word;
}
</style>
