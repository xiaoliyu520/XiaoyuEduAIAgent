<template>
  <div class="resume-container">
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>上传简历</span>
          </template>
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".txt,.pdf,.doc,.docx"
            :on-change="handleFileChange"
          >
            <el-button type="primary">选择文件</el-button>
            <template #tip>
              <div class="upload-tip">支持 txt、pdf、doc、docx 格式</div>
            </template>
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
      </el-col>
      <el-col :span="12">
        <el-card v-if="report">
          <template #header>
            <span>审查报告</span>
          </template>
          <div class="report-content" v-html="renderMarkdown(report)"></div>
        </el-card>
        <el-card v-else>
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
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'
import api from '../utils/api'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import * as echarts from 'echarts'

const uploadRef = ref(null)
const selectedFile = ref(null)
const loading = ref(false)
const report = ref('')
const radarData = ref(null)
const radarRef = ref(null)

function handleFileChange(file) {
  selectedFile.value = file.raw
}

function renderMarkdown(text) {
  if (!text) return ''
  return marked.parse(text)
}

async function startReview() {
  if (!selectedFile.value) return
  loading.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    const uploadRes = await api.post('/agents/resume/upload', formData)
    const resumeId = uploadRes.data?.resume_id

    const reviewRes = await api.post('/agents/resume/review', { resume_id: resumeId })
    report.value = reviewRes.data

    try {
      const parsed = JSON.parse(reviewRes.data)
      if (parsed.radar_data) {
        radarData.value = parsed.radar_data
        nextTick(() => renderRadar(parsed.radar_data))
      }
    } catch {
      // not JSON, show as markdown
    }
    ElMessage.success('简历审查完成')
  } catch (e) {
    ElMessage.error('审查失败，请重试')
  } finally {
    loading.value = false
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
  max-width: 1200px;
  margin: 0 auto;
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
</style>
