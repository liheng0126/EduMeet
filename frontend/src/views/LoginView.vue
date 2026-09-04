<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2 style="text-align:center;margin:8px 0 20px;">EduMeet · 教育智能体平台</h2>
      <el-tabs v-model="tab">
        <el-tab-pane label="登录" name="login">
          <el-form @keyup.enter="doLogin">
            <el-form-item><el-input v-model="form.username" placeholder="用户名" /></el-form-item>
            <el-form-item><el-input v-model="form.password" type="password" placeholder="密码" show-password /></el-form-item>
            <el-button type="primary" style="width:100%" :loading="loading" @click="doLogin">登 录</el-button>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="注册" name="register">
          <el-form @keyup.enter="doRegister">
            <el-form-item><el-input v-model="form.username" placeholder="用户名（≥3位）" /></el-form-item>
            <el-form-item><el-input v-model="form.nickname" placeholder="昵称（可选）" /></el-form-item>
            <el-form-item><el-input v-model="form.password" type="password" placeholder="密码（≥6位）" show-password /></el-form-item>
            <el-button type="success" style="width:100%" :loading="loading" @click="doRegister">注册并登录</el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login, register } from '../api'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const tab = ref('login')
const loading = ref(false)
const form = ref({ username: '', password: '', nickname: '' })

async function submit(fn: () => Promise<any>, tip: string) {
  loading.value = true
  try {
    const data = await fn()
    auth.setAuth(data.token, data.user)
    ElMessage.success(tip)
    router.push('/')
  } finally { loading.value = false }
}
const doLogin = () => {
  if (!form.value.username || !form.value.password) return ElMessage.warning('请输入用户名和密码')
  return submit(() => login({ username: form.value.username, password: form.value.password }), '登录成功')
}
const doRegister = () => {
  if (form.value.username.length < 3 || form.value.password.length < 6)
    return ElMessage.warning('用户名≥3位、密码≥6位')
  return submit(() => register({ ...form.value }), '注册成功')
}
</script>

<style scoped>
.login-wrap { height: 100%; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(120deg, #1e3a8a, #2563eb 55%, #7c3aed); }
.login-card { width: 380px; border-radius: 14px; }
</style>
