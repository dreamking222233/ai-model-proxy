import Vue from 'vue'
import Vuex from 'vuex'
import { login as loginApi, register as registerApi } from '@/api/auth'
import { getToken, setToken, removeToken, getUser, setUser, removeUser } from '@/utils/auth'

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
      removeToken()
      removeUser()
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

    async register({ commit }, { username, email, password }) {
      const res = await registerApi(username, email, password)
      return res
    },

    logout({ commit }) {
      commit('LOGOUT')
    }
  },

  getters: {
    isLoggedIn: state => !!state.token,
    isAdmin: state => state.user && state.user.role === 'admin',
    currentUser: state => state.user
  }
})
