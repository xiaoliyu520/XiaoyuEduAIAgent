<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <h2>🔧 管理后台</h2>
      </template>
      <el-form :model="form" @submit.prevent="handleLogin" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="管理员账号" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="密码" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleLogin" :loading="loading" style="width: 100%">
            登 录
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../utils/api'
import { ElMessage } from 'element-plus'

const router = useRouter()
const loading = ref(false)
const form = ref({ username: '', password: '' })

async function handleLogin() {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const res = await api.post('/auth/login', form.value)
    if (res.user?.role !== 'admin') {
      ElMessage.error('非管理员账号，请使用用户端登录')
      return
    }
    localStorage.setItem('admin_token', res.access_token)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (e) {
    const msg = e.message || ''
    if (msg.includes('禁用')) {
      ElMessage.error('该账户已被禁用')
    } else if (msg.includes('用户名或密码')) {
      ElMessage.error('用户名或密码错误')
    } else {
      ElMessage.error(msg || '登录失败')
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
}
.login-card {
  width: 400px;
  border-radius: 12px;
}
</style>
