<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <h2 class="login-title">🐟 小鱼教育AI助手</h2>
      </template>
      
      <el-tabs v-model="activeTab" class="login-tabs">
        <el-tab-pane label="登录" name="login">
          <el-form :model="loginForm" @submit.prevent="handleLogin" label-position="top">
            <el-form-item label="用户名">
              <el-input v-model="loginForm.username" placeholder="请输入用户名" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="loginForm.password" type="password" placeholder="请输入密码" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleLogin" :loading="loading" style="width: 100%">
                登 录
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
        
        <el-tab-pane label="注册" name="register">
          <el-form :model="registerForm" @submit.prevent="handleRegister" label-position="top">
            <el-form-item label="用户名">
              <el-input v-model="registerForm.username" placeholder="请输入用户名" />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="registerForm.email" placeholder="请输入邮箱" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="registerForm.password" type="password" placeholder="请输入密码" show-password />
            </el-form-item>
            <el-form-item label="确认密码">
              <el-input v-model="registerForm.confirmPassword" type="password" placeholder="请再次输入密码" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="success" @click="handleRegister" :loading="loading" style="width: 100%">
                注 册
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { ElMessage } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const activeTab = ref('login')

const loginForm = ref({ username: '', password: '' })
const registerForm = ref({ username: '', email: '', password: '', confirmPassword: '' })

async function handleLogin() {
  if (!loginForm.value.username || !loginForm.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await userStore.login(loginForm.value.username, loginForm.value.password)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (e) {
    const msg = e.message || ''
    if (msg.includes('禁用')) {
      ElMessage.error('该账户已被禁用，请联系管理员')
    } else if (msg.includes('用户名或密码')) {
      ElMessage.error('用户名或密码错误')
    } else {
      ElMessage.error(msg || '登录失败')
    }
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  if (!registerForm.value.username || !registerForm.value.email || !registerForm.value.password) {
    ElMessage.warning('请填写完整信息')
    return
  }
  if (registerForm.value.password !== registerForm.value.confirmPassword) {
    ElMessage.warning('两次密码输入不一致')
    return
  }
  if (registerForm.value.password.length < 6) {
    ElMessage.warning('密码长度至少6位')
    return
  }
  loading.value = true
  try {
    await userStore.register(
      registerForm.value.username,
      registerForm.value.email,
      registerForm.value.password
    )
    ElMessage.success('注册成功，已自动登录')
    router.push('/')
  } catch (e) {
    const msg = e.message || ''
    if (msg.includes('用户名已存在')) {
      ElMessage.error('用户名已被使用')
    } else if (msg.includes('邮箱已存在')) {
      ElMessage.error('邮箱已被注册')
    } else {
      ElMessage.error(msg || '注册失败')
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
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.login-card {
  width: 400px;
  border-radius: 12px;
}
.login-title {
  text-align: center;
  margin: 0;
  color: #303133;
}
.login-tabs {
  margin-top: 10px;
}
</style>
