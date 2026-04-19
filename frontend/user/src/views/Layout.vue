<template>
  <el-container class="layout-container">
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <h3>🐟 小鱼教育AI</h3>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        class="sidebar-menu"
        background-color="#1d1e2c"
        text-color="#a0a3bd"
        active-text-color="#409eff"
      >
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <span>智能问答</span>
        </el-menu-item>
        <el-menu-item index="/resume">
          <el-icon><Document /></el-icon>
          <span>简历审查</span>
        </el-menu-item>
        <el-menu-item index="/interview">
          <el-icon><Microphone /></el-icon>
          <span>模拟面试</span>
        </el-menu-item>
        <el-menu-item index="/code">
          <el-icon><Monitor /></el-icon>
          <span>代码检查</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="header-title">{{ currentTitle }}</span>
        <div class="header-right">
          <span class="username">{{ userStore.userInfo?.username }}</span>
          <el-button text @click="handleLogout">退出</el-button>
        </div>
      </el-header>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { ChatDotRound, Document, Microphone, Monitor } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const activeMenu = computed(() => route.path)

const titleMap = {
  '/chat': '智能问答',
  '/resume': '简历审查',
  '/interview': '模拟面试',
  '/code': '代码检查',
}

const currentTitle = computed(() => titleMap[route.path] || '小鱼教育AI助手')

onMounted(() => {
  if (!userStore.userInfo) {
    userStore.fetchUserInfo()
  }
})

function handleLogout() {
  userStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}
.sidebar {
  background-color: #1d1e2c;
  overflow-y: auto;
}
.logo {
  padding: 20px;
  text-align: center;
}
.logo h3 {
  color: #fff;
  margin: 0;
}
.sidebar-menu {
  border-right: none;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e4e7ed;
  background: #fff;
}
.header-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.username {
  color: #606266;
  font-size: 14px;
}
.main-content {
  background: #f5f7fa;
  overflow-y: auto;
}
</style>
