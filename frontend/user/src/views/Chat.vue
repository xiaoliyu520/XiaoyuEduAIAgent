<template>
  <div class="chat-container">
    <div class="chat-messages" ref="messagesRef">
      <div
        v-for="(msg, index) in messages"
        :key="index"
        :class="['message-item', msg.role === 'user' ? 'message-user' : 'message-assistant']"
      >
        <div class="message-avatar">
          {{ msg.role === 'user' ? '👤' : '🤖' }}
        </div>
        <div class="message-content">
          <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
        </div>
      </div>
      <div v-if="streaming" class="message-item message-assistant">
        <div class="message-avatar">🤖</div>
        <div class="message-content">
          <div class="message-text" v-html="renderMarkdown(streamContent)"></div>
          <span class="typing-indicator">▊</span>
        </div>
      </div>
    </div>
    <div class="chat-input">
      <el-input
        v-model="inputText"
        placeholder="输入你的问题..."
        @keydown.enter="sendMessage"
        :disabled="streaming"
        size="large"
      >
        <template #append>
          <el-button @click="sendMessage" :loading="streaming" type="primary">
            发送
          </el-button>
        </template>
      </el-input>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import api from '../utils/api'
import { chatStream } from '../utils/sse'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'

marked.setOptions({
  highlight(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value
    }
    return hljs.highlightAuto(code).value
  },
})

const messages = ref([])
const inputText = ref('')
const streaming = ref(false)
const streamContent = ref('')
const messagesRef = ref(null)
const conversationId = ref(null)

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

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || streaming.value) return

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  streaming.value = true
  streamContent.value = ''
  scrollToBottom()

  await chatStream(
    '/chat/stream',
    {
      message: text,
      conversation_id: conversationId.value,
      agent_type: 'qa',
    },
    (chunk) => {
      streamContent.value += chunk
      scrollToBottom()
    },
    (done) => {
      if (done.conversation_id) {
        conversationId.value = done.conversation_id
      }
      messages.value.push({ role: 'assistant', content: streamContent.value })
      streaming.value = false
      streamContent.value = ''
      scrollToBottom()
    },
    (error) => {
      messages.value.push({ role: 'assistant', content: `❌ 出错了: ${error}` })
      streaming.value = false
      streamContent.value = ''
    }
  )
}

onMounted(() => {
  loadConversations()
})

async function loadConversations() {
  try {
    const res = await api.get('/chat/conversations')
    const data = res.data || []
    if (data.length > 0) {
      conversationId.value = data[0].id
      messages.value = data[0].messages || []
    }
  } catch {
    // ignore
  }
}
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 900px;
  margin: 0 auto;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
.message-item {
  display: flex;
  margin-bottom: 20px;
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
.message-text :deep(pre) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
}
.message-text :deep(code) {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
}
.typing-indicator {
  animation: blink 1s infinite;
  color: #409eff;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
.chat-input {
  padding: 16px 20px;
  border-top: 1px solid #e4e7ed;
}
</style>
