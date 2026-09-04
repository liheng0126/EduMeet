import { defineStore } from 'pinia'

interface UserInfo { id: number; username: string; nickname: string }

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('edumeet_token') || '',
    user: JSON.parse(localStorage.getItem('edumeet_user') || 'null') as UserInfo | null,
  }),
  actions: {
    setAuth(token: string, user: UserInfo) {
      this.token = token
      this.user = user
      localStorage.setItem('edumeet_token', token)
      localStorage.setItem('edumeet_user', JSON.stringify(user))
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('edumeet_token')
      localStorage.removeItem('edumeet_user')
      if (location.pathname !== '/login') location.href = '/login'
    },
  },
})
