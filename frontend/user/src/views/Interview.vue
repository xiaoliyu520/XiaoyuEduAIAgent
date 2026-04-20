<template>
  <div class="interview-container">
    <div v-if="!interviewStarted" class="interview-start">
      <el-card>
        <template #header>
          <span>开始模拟面试</span>
        </template>
        <el-form :model="form" label-position="top">
          <el-form-item label="选择简历（可选）">
            <el-select v-model="form.resume_id" placeholder="选择已上传的简历" clearable>
              <el-option
                v-for="r in resumes"
                :key="r.id"
                :label="`简历 #${r.id}`"
                :value="r.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="重点关注领域（可选）">
            <el-select v-model="form.focus_areas" multiple placeholder="选择关注领域">
              <el-option label="Java" value="java" />
              <el-option label="Python" value="python" />
              <el-option label="前端" value="frontend" />
              <el-option label="数据库" value="database" />
              <el-option label="系统设计" value="system_design" />
            </el-select>
          </el-form-item>
          <el-button type="primary" @click="startInterview" :loading="loading" style="width: 100%">
            开始面试
          </el-button>
        </el-form>
      </el-card>
    </div>

    <div v-else class="interview-chat">
      <div class="stage-indicator">
        <el-steps :active="stageIndex" align-center>
          <el-step title="自我介绍" />
          <el-step title="技术问题" />
          <el-step title="项目经验" />
          <el-step title="面试报告" />
        </el-steps>
      </div>
      <div class="chat-messages" ref="messagesRef">
        <div
          v-for="(msg, index) in messages"
          :key="index"
          :class="['message-item', msg.role === 'user' ? 'message-user' : 'message-assistant']"
        >
          <div class="message-avatar">{{ msg.role === 'user' ? '👤' : '🎯' }}</div>
          <div class="message-content">
            <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
          </div>
        </div>
      </div>
      <div class="chat-input" v-if="currentStage !== 'REPORT'">
        <el-input
          v-model="inputText"
          placeholder="输入你的回答..."
          @keydown.enter="sendResponse"
          :disabled="loading"
          size="large"
        >
          <template #append>
            <el-button @click="sendResponse" :loading="loading" type="primary">发送</el-button>
          </template>
        </el-input>
      </div>
      <div class="report-section" v-if="currentStage === 'REPORT' && reportData">
        <el-card>
          <template #header><span>面试报告</span></template>
          <div ref="radarRef" style="height: 400px"></div>
          <div class="report-content" v-html="renderMarkdown(reportData.report_content || '')"></div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import api from '../utils/api'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import * as echarts from 'echarts'

const loading = ref(false)
const interviewStarted = ref(false)
const conversationId = ref(null)
const currentStage = ref('INTRO')
const messages = ref([])
const inputText = ref('')
const messagesRef = ref(null)
const reportData = ref(null)
const radarRef = ref(null)
const resumes = ref([])

const form = ref({
  resume_id: null,
  focus_areas: [],
})

const stageIndex = computed(() => {
  const map = { INTRO: 0, TECH: 1, PROJECT: 2, REPORT: 3 }
  return map[currentStage.value] || 0
})

function renderMarkdown(text) {
  if (!text) return ''
  return marked.parse(text)
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

async function startInterview() {
  loading.value = true
  try {
    const res = await api.post('/interview/start', form.value)
    conversationId.value = res.data?.conversation_id
    currentStage.value = res.data?.stage
    messages.value.push({ role: 'assistant', content: res.data?.message })
    interviewStarted.value = true
    scrollToBottom()
  } catch (e) {
    ElMessage.error('启动面试失败')
  } finally {
    loading.value = false
  }
}

async function sendResponse() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  loading.value = true
  scrollToBottom()

  try {
    const res = await api.post('/interview/respond', {
      conversation_id: conversationId.value,
      message: text,
    })
    currentStage.value = res.data?.stage
    messages.value.push({ role: 'assistant', content: res.data?.message })

    if (res.data?.report) {
      reportData.value = res.data.report
      nextTick(() => renderRadar(res.data.report.radar_data))
    }
    scrollToBottom()
  } catch (e) {
    ElMessage.error('发送失败')
  } finally {
    loading.value = false
  }
}

function renderRadar(data) {
  if (!radarRef.value || !data) return
  const chart = echarts.init(radarRef.value)
  chart.setOption({
    radar: {
      indicator: data.indicators.map((name) => ({ name, max: 100 })),
    },
    series: [
      {
        type: 'radar',
        data: [{ value: data.values, name: '面试评估', areaStyle: { opacity: 0.3 } }],
      },
    ],
  })
}

onMounted(async () => {
  try {
    // Load resumes if available
  } catch {
    // ignore
  }
})
</script>

<style scoped>
.interview-container {
  max-width: 900px;
  margin: 0 auto;
}
.interview-start {
  padding: 20px;
}
.interview-chat {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 140px);
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}
.stage-indicator {
  padding: 16px 20px;
  border-bottom: 1px solid #e4e7ed;
}
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
.message-item {
  display: flex;
  margin-bottom: 16px;
  gap: 12px;
}
.message-user {
  flex-direction: row-reverse;
}
.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}
.message-content {
  max-width: 70%;
}
.message-text {
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  font-size: 14px;
}
.message-user .message-text {
  background: #409eff;
  color: #fff;
  border-top-right-radius: 4px;
}
.message-assistant .message-text {
  background: #f4f4f5;
  color: #303133;
  border-top-left-radius: 4px;
}
.chat-input {
  padding: 16px 20px;
  border-top: 1px solid #e4e7ed;
}
.report-section {
  padding: 20px;
  overflow-y: auto;
}
.report-content {
  line-height: 1.8;
  margin-top: 16px;
}
</style>
