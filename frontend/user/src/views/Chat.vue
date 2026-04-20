<template>
  <div class="chat-page">
    <div class="sidebar">
      <div class="sidebar-header">
        <el-button type="primary" @click="newConversation" style="width: 100%">
          <el-icon><Plus /></el-icon>
          新建对话
        </el-button>
      </div>
      <div class="conversation-list">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          :class="['conversation-item', { active: conversationId === conv.id }]"
          @click="selectConversation(conv)"
        >
          <div class="conv-title">{{ conv.title }}</div>
          <div class="conv-time">{{ formatTime(conv.created_at) }}</div>
          <el-button
            class="delete-btn"
            type="danger"
            size="small"
            text
            @click.stop="deleteConversation(conv.id)"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
    </div>
    <div class="chat-container">
      <div class="chat-header">
        <el-select
          v-model="selectedKbIds"
          placeholder="选择知识库(可多选)"
          multiple
          clearable
          collapse-tags
          collapse-tags-tooltip
          style="width: 280px"
        >
          <el-option
            v-for="kb in knowledgeBases"
            :key="kb.id"
            :label="kb.name"
            :value="kb.id"
          />
        </el-select>
        <span class="kb-hint">{{ selectedKbIds.length > 0 ? `已选 ${selectedKbIds.length} 个知识库` : '⚠️ 请选择知识库后开始对话' }}</span>
      </div>
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
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import api from '../utils/api'
import { chatStream } from '../utils/sse'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import { Plus, Delete } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

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
const knowledgeBases = ref([])
const selectedKbIds = ref([])
const conversations = ref([])

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

function formatTime(time) {
  if (!time) return ''
  const date = new Date(time)
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

async function loadConversations() {
  try {
    const res = await api.get('/chat/conversations')
    conversations.value = res.data || []
  } catch {
    // ignore
  }
}

async function newConversation() {
  try {
    const res = await api.post('/chat/conversations')
    conversations.value.unshift(res.data)
    conversationId.value = res.data.id
    messages.value = []
  } catch {
    // ignore
  }
}

function selectConversation(conv) {
  conversationId.value = conv.id
  messages.value = conv.messages || []
  scrollToBottom()
}

async function deleteConversation(id) {
  try {
    await api.delete(`/chat/conversations/${id}`)
    conversations.value = conversations.value.filter(c => c.id !== id)
    if (conversationId.value === id) {
      if (conversations.value.length > 0) {
        selectConversation(conversations.value[0])
      } else {
        conversationId.value = null
        messages.value = []
      }
    }
  } catch {
    // ignore
  }
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || streaming.value) return

  if (selectedKbIds.value.length === 0) {
    ElMessage.warning('请先选择至少一个知识库')
    return
  }

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  streaming.value = true
  streamContent.value = ''
  scrollToBottom()

  const requestData = {
    message: text,
    conversation_id: conversationId.value,
    agent_type: 'qa',
  }

  if (selectedKbIds.value.length > 0) {
    requestData.kb_ids = selectedKbIds.value
  }

  await chatStream(
    '/chat/stream',
    requestData,
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
      loadConversations()
    },
    (error) => {
      messages.value.push({ role: 'assistant', content: `❌ 出错了: ${error}` })
      streaming.value = false
      streamContent.value = ''
    }
  )
}

async function loadKnowledgeBases() {
  try {
    const res = await api.get('/knowledge/bases')
    knowledgeBases.value = res.data || []
  } catch {
    // ignore
  }
}

onMounted(() => {
  loadKnowledgeBases()
  loadConversations()
})
</script>

<style scoped>
.chat-page {
  display: flex;
  height: 100%;
  background: #f5f7fa;
}
.sidebar {
  width: 260px;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
}
.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #e4e7ed;
}
.conversation-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.conversation-item {
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  position: relative;
}
.conversation-item:hover {
  background: #f0f2f5;
}
.conversation-item.active {
  background: #ecf5ff;
}
.conv-title {
  font-size: 14px;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 24px;
}
.conv-time {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.delete-btn {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  opacity: 0;
}
.conversation-item:hover .delete-btn {
  opacity: 1;
}
.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  max-width: 900px;
  margin: 0 auto;
  background: #fff;
}
.chat-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  border-bottom: 1px solid #e4e7ed;
}
.kb-hint {
  color: #909399;
  font-size: 12px;
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
