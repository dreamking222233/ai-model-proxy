import Vue from 'vue'
import Vuex from 'vuex'
import { login as loginApi, register as registerApi, logout as logoutApi } from '@/api/auth'
import { getToken, setToken, getUser, setUser, clearSiteClientCache } from '@/utils/auth'

Vue.use(Vuex)

export default new Vuex.Store({
  state: {
    token: getToken() || '',
    user: getUser() || {
      id: null,
      username: '',
      email: '',
      role: '',
      avatar: ''
    }
  },

  mutations: {
    SET_TOKEN(state, token) {
      state.token = token
      setToken(token)
    },

    SET_USER(state, user) {
      state.user = user
      setUser(user)
    },

    LOGOUT(state) {
      state.token = ''
      state.user = {
        id: null,
        username: '',
        email: '',
        role: '',
        avatar: ''
      }
      clearSiteClientCache()
    }
  },

  actions: {
    async login({ commit }, { username, password }) {
      const res = await loginApi(username, password)
      const { token, user } = res.data
      commit('SET_TOKEN', token)
      commit('SET_USER', user)
      return res
    },

    async register(_, { username, email, password, email_code, invite_code }) {
      const res = await registerApi(username, email, password, email_code, invite_code)
      return res
    },

    async logout({ commit }) {
      try {
        await logoutApi()
      } catch (e) {
        // 本地退出必须继续执行，服务端撤销失败时依赖 token 过期或账号级版本失效。
      }
      commit('LOGOUT')
    }
  },

  getters: {
    isLoggedIn: state => !!state.token,
    isAdmin: state => state.user && state.user.role === 'admin',
    isAgent: state => state.user && state.user.role === 'agent',
    currentUser: state => state.user
  }
})
