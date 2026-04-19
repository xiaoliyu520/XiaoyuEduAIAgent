<template>
  <el-container class="layout-container">
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <h3>🔧 管理后台</h3>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#1d1e2c"
        text-color="#a0a3bd"
        active-text-color="#409eff"
      >
        <el-menu-item index="/users">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
        <el-menu-item index="/knowledge">
          <el-icon><Folder /></el-icon>
          <span>知识库管理</span>
        </el-menu-item>
        <el-menu-item index="/gaps">
          <el-icon><Warning /></el-icon>
          <span>知识缺口</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="header-title">小鱼教育AI管理后台</span>
        <el-button text @click="handleLogout">退出登录</el-button>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { User, Folder, Warning } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const activeMenu = computed(() => route.path)

function handleLogout() {
  localStorage.removeItem('admin_token')
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
}
</style>
