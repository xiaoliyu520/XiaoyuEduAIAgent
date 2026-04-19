<template>
  <div class="gaps-container">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>知识缺口管理</span>
          <el-radio-group v-model="statusFilter" @change="loadGaps">
            <el-radio-button value="open">待处理</el-radio-button>
            <el-radio-button value="in_progress">处理中</el-radio-button>
            <el-radio-button value="resolved">已解决</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <el-table :data="gaps" stripe>
        <el-table-column label="序号" width="80">
          <template #default="{ $index }">
            {{ $index + 1 }}
          </template>
        </el-table-column>
        <el-table-column prop="question" label="问题" min-width="300" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button
              v-if="row.status !== 'resolved'"
              size="small"
              type="primary"
              @click="showResolveDialog(row)"
            >
              补录
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="resolveDialogVisible" title="补录知识" width="500px">
      <el-form :model="resolveForm" label-position="top">
        <el-form-item label="问题">
          <el-input :model-value="resolveForm.question" disabled type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="答案">
          <el-input v-model="resolveForm.answer" type="textarea" :rows="6" placeholder="请输入答案" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resolveDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="resolveGap" :loading="resolveLoading">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../utils/api'
import { ElMessage } from 'element-plus'

const gaps = ref([])
const statusFilter = ref('open')
const resolveDialogVisible = ref(false)
const resolveLoading = ref(false)
const resolveForm = ref({ id: null, question: '', answer: '' })

async function loadGaps() {
  try {
    const res = await api.get('/knowledge/gaps', { params: { status: statusFilter.value } })
    gaps.value = res.data || []
  } catch {
    ElMessage.error('加载知识缺口失败')
  }
}

function statusTagType(status) {
  const map = { open: 'danger', in_progress: 'warning', resolved: 'success' }
  return map[status] || 'info'
}

function statusLabel(status) {
  const map = { open: '待处理', in_progress: '处理中', resolved: '已解决' }
  return map[status] || status
}

function showResolveDialog(gap) {
  resolveForm.value = { id: gap.id, question: gap.question, answer: '' }
  resolveDialogVisible.value = true
}

async function resolveGap() {
  if (!resolveForm.value.answer.trim()) {
    ElMessage.warning('请输入答案')
    return
  }
  resolveLoading.value = true
  try {
    await api.put(`/knowledge/gaps/${resolveForm.value.id}/resolve`, {
      answer: resolveForm.value.answer,
    })
    resolveDialogVisible.value = false
    gaps.value = gaps.value.filter(g => g.id !== resolveForm.value.id)
    ElMessage.success('补录成功')
  } catch (e) {
    ElMessage.error(e.message || '补录失败')
  } finally {
    resolveLoading.value = false
  }
}

onMounted(loadGaps)
</script>

<style scoped>
.gaps-container {
  max-width: 1000px;
  margin: 0 auto;
}
</style>
