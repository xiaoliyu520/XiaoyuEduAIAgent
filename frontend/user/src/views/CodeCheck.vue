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
        <el-card v-if="result">
          <template #header>
            <span>检查结果</span>
          </template>
          <div class="result-content" v-html="renderMarkdown(result)"></div>
        </el-card>
        <el-card v-else>
          <el-empty description="输入代码并点击检查" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import { useUserStore } from '../stores/user'

const code = ref('')
const language = ref('python')
const loading = ref(false)
const result = ref('')

const userStore = useUserStore()

function renderMarkdown(text) {
  if (!text) return ''
  return marked.parse(text)
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
</script>

<style scoped>
.code-container {
  max-width: 1200px;
  margin: 0 auto;
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
</style>
