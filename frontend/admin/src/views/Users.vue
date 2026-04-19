<template>
  <div class="users-container">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>用户管理</span>
          <el-button type="primary" @click="showAddDialog">添加用户</el-button>
        </div>
      </template>
      <el-table :data="users" stripe>
        <el-table-column label="序号" width="80">
          <template #default="{ $index }">
            {{ $index + 1 }}
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="email" label="邮箱" />
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'">
              {{ row.role === 'admin' ? '管理员' : '用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'warning'">
              {{ row.is_active ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button
              size="small"
              :type="row.is_active ? 'warning' : 'success'"
              @click="toggleActive(row)"
              :disabled="row.role === 'admin'"
            >
              {{ row.is_active ? '禁用' : '启用' }}
            </el-button>
            <el-button
              size="small"
              type="danger"
              @click="deleteUser(row)"
              :disabled="row.role === 'admin'"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="addDialogVisible" title="添加用户" width="400px">
      <el-form :model="addForm" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="addForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="addForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="addForm.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="addUser" :loading="addLoading">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const users = ref([])
const addDialogVisible = ref(false)
const addLoading = ref(false)
const addForm = ref({ username: '', email: '', password: '' })

async function loadUsers() {
  try {
    const res = await api.get('/auth/users')
    users.value = res.data?.items || []
  } catch {
    ElMessage.error('加载用户列表失败')
  }
}

async function toggleActive(user) {
  if (user.role === 'admin') {
    ElMessage.warning('不能禁用管理员账号')
    return
  }
  try {
    await api.put(`/auth/users/${user.id}/toggle-active`)
    user.is_active = !user.is_active
    ElMessage.success(user.is_active ? '已启用' : '已禁用')
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  }
}

async function deleteUser(user) {
  if (user.role === 'admin') {
    ElMessage.warning('不能删除管理员账号')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定要删除用户 "${user.username}" 吗？此操作不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    await api.delete(`/auth/users/${user.id}`)
    users.value = users.value.filter(u => u.id !== user.id)
    ElMessage.success('删除成功')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.message || '删除失败')
    }
  }
}

function showAddDialog() {
  addForm.value = { username: '', email: '', password: '' }
  addDialogVisible.value = true
}

async function addUser() {
  addLoading.value = true
  try {
    const res = await api.post('/auth/register', addForm.value)
    addDialogVisible.value = false
    users.value.push(res.user)
    ElMessage.success('添加用户成功')
  } catch (e) {
    ElMessage.error(e.message || '添加用户失败')
  } finally {
    addLoading.value = false
  }
}

onMounted(loadUsers)
</script>

<style scoped>
.users-container {
  max-width: 1000px;
  margin: 0 auto;
}
</style>
