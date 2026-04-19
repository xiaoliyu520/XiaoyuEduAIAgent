import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../utils/api'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref(null)

  async function login(username, password) {
    const res = await api.post('/auth/login', { username, password })
    token.value = res.access_token
    userInfo.value = res.user
    localStorage.setItem('token', res.access_token)
    return res
  }

  async function register(username, email, password) {
    const res = await api.post('/auth/register', { 
      username, 
      email, 
      password,
      role: 'user'
    })
    token.value = res.access_token
    userInfo.value = res.user
    localStorage.setItem('token', res.access_token)
    return res
  }

  async function fetchUserInfo() {
    const res = await api.get('/auth/me')
    userInfo.value = res
    return res
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
  }

  return { token, userInfo, login, register, fetchUserInfo, logout }
})
