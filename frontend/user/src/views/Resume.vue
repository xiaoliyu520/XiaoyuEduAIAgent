<template>
  <div class="resume-container">
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card class="upload-card">
          <template #header>
            <span>上传简历</span>
          </template>
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".txt,.pdf,.doc,.docx,.jpg,.jpeg,.png,.gif,.bmp,.webp"
            :on-change="handleFileChange"
            drag
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">拖拽或点击上传</div>
          </el-upload>
          <el-button
            type="success"
            @click="startReview"
            :loading="loading"
            :disabled="!selectedFile"
            style="margin-top: 16px; width: 100%"
          >
            开始审查
          </el-button>
        </el-card>

        <el-card class="history-card" style="margin-top: 16px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span>历史记录</span>
              <el-button type="primary" link size="small" @click="loadHistory">
                刷新
              </el-button>
            </div>
          </template>
          <div v-if="historyLoading" style="text-align: center; padding: 20px;">
            <el-icon class="is-loading"><loading /></el-icon>
          </div>
          <div v-else-if="historyList.length === 0" style="text-align: center; color: #909399; padding: 20px;">
            暂无历史记录
          </div>
          <div v-else class="history-list">
            <div 
              v-for="item in historyList" 
              :key="item.id" 
              class="history-item"
              :class="{ active: currentResumeId === item.id }"
              @click="viewHistory(item)"
            >
              <div class="history-name">
                <el-icon><document /></el-icon>
                <span>{{ getFileName(item.file_path) }}</span>
              </div>
              <div class="history-meta">
                <span>{{ formatDate(item.created_at) }}</span>
                <el-tag v-if="item.has_review" type="success" size="small">已审查</el-tag>
                <el-tag v-else type="info" size="small">未审查</el-tag>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="18">
        <el-card v-if="report" class="report-card">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span>审查报告</span>
              <el-button v-if="currentResumeId" type="primary" link size="small" @click="startReviewById">
                重新审查
              </el-button>
            </div>
          </template>
          <div class="report-content" v-html="renderMarkdown(report)"></div>
        </el-card>
        <el-card v-else class="empty-card">
          <el-empty description="请上传简历开始审查" />
        </el-card>
      </el-col>
    </el-row>
    <el-row :gutter="20" style="margin-top: 20px" v-if="radarData">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>能力雷达图</span>
          </template>
          <div ref="radarRef" style="height: 400px"></div>
          <div class="radar-data">
            <el-descriptions :column="3" border>
              <el-descriptions-item 
                v-for="(indicator, index) in radarData.indicators" 
                :key="indicator"
                :label="indicator"
              >
                <el-progress 
                  :percentage="radarData.values[index]" 
                  :color="getProgressColor(radarData.values[index])"
                />
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import api from '../utils/api'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import * as echarts from 'echarts'
import { UploadFilled, Document, Loading } from '@element-plus/icons-vue'

const uploadRef = ref(null)
const selectedFile = ref(null)
const loading = ref(false)
const report = ref('')
const radarData = ref(null)
const radarRef = ref(null)
const historyList = ref([])
const historyLoading = ref(false)
const currentResumeId = ref(null)

onMounted(() => {
  loadHistory()
})

function handleFileChange(file) {
  selectedFile.value = file.raw
}

function renderMarkdown(text) {
  if (!text) return ''
  return marked.parse(text)
}

function getProgressColor(value) {
  if (value >= 80) return '#67c23a'
  if (value >= 60) return '#e6a23c'
  return '#f56c6c'
}

function getFileName(path) {
  if (!path) return '未知文件'
  return path.split('/').pop()
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await api.get('/resume/list')
    historyList.value = res || []
  } catch (e) {
    console.error('加载历史记录失败:', e)
  } finally {
    historyLoading.value = false
  }
}

async function viewHistory(item) {
  if (!item.has_review) {
    ElMessage.warning('该简历尚未审查')
    return
  }
  
  currentResumeId.value = item.id
  report.value = ''
  radarData.value = null
  
  try {
    const res = await api.get(`/resume/${item.id}`)
    if (res.error) {
      ElMessage.error('加载失败')
      return
    }
    report.value = res.review_result || ''
    if (res.radar_data && res.radar_data.indicators) {
      radarData.value = res.radar_data
      nextTick(() => renderRadar(res.radar_data))
    }
  } catch (e) {
    ElMessage.error('加载历史记录失败')
  }
}

async function startReview() {
  if (!selectedFile.value) return
  loading.value = true
  report.value = ''
  radarData.value = null
  currentResumeId.value = null
  
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    const uploadRes = await api.post('/resume/upload', formData)
    const resumeId = uploadRes.data?.resume_id

    await streamReview(resumeId)
    loadHistory()
    ElMessage.success('简历审查完成')
  } catch (e) {
    ElMessage.error('审查失败，请重试')
  } finally {
    loading.value = false
  }
}

async function startReviewById() {
  if (!currentResumeId.value) return
  loading.value = true
  report.value = ''
  radarData.value = null
  
  try {
    await streamReview(currentResumeId.value)
    loadHistory()
    ElMessage.success('简历审查完成')
  } catch (e) {
    ElMessage.error('审查失败，请重试')
  } finally {
    loading.value = false
  }
}

async function streamReview(resumeId) {
  const token = localStorage.getItem('token')
  
  const response = await fetch('/api/v1/resume/review/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ resume_id: resumeId }),
  })

  if (!response.ok) {
    throw new Error('请求失败')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6))
          
          if (data.error) {
            throw new Error(data.error)
          }
          
          if (data.done) {
            if (data.report?.radar_data) {
              radarData.value = data.report.radar_data
              nextTick(() => renderRadar(data.report.radar_data))
            }
          } else if (data.content) {
            if (data.content.includes('RADAR_JSON:')) {
              return
            }
            report.value += data.content
          }
        } catch (e) {
          if (e.message !== 'Unexpected end of JSON input') {
            console.error('Parse error:', e)
          }
        }
      }
    }
  }
}

function renderRadar(data) {
  if (!radarRef.value) return
  const chart = echarts.init(radarRef.value)
  chart.setOption({
    radar: {
      indicator: data.indicators.map((name) => ({ name, max: 100 })),
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: data.values,
            name: '能力评估',
            areaStyle: { opacity: 0.3 },
          },
        ],
      },
    ],
  })
}
</script>

<style scoped>
.resume-container {
  max-width: 1400px;
  margin: 0 auto;
}
.upload-card {
  min-height: 200px;
}
.history-card {
  max-height: calc(100vh - 200px);
}
.report-card {
  min-height: calc(100vh - 180px);
}
.empty-card {
  min-height: calc(100vh - 180px);
  display: flex;
  align-items: center;
  justify-content: center;
}
.history-list {
  max-height: calc(100vh - 320px);
  overflow-y: auto;
}
.history-item {
  padding: 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
  border-bottom: 1px solid #ebeef5;
}
.history-item:last-child {
  border-bottom: none;
}
.history-item:hover {
  background-color: #f5f7fa;
}
.history-item.active {
  background-color: #ecf5ff;
}
.history-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #303133;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.history-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #909399;
}
.upload-tip {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}
.report-content {
  line-height: 1.8;
  font-size: 14px;
}
.report-content :deep(pre) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
}
.report-content :deep(h3) {
  margin-top: 16px;
  color: #303133;
}
.report-content :deep(ul) {
  padding-left: 20px;
}
.report-content :deep(li) {
  margin-bottom: 8px;
}
.radar-data {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #ebeef5;
}
</style>
