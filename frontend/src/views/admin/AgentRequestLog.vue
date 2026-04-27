<template>
  <div class="page">
    <div class="toolbar">
      <a-input-number v-model="filters.agent_id" :min="1" placeholder="代理ID" />
      <a-input v-model="filters.model" placeholder="模型" style="width: 180px" />
      <a-button type="primary" @click="fetchList">查询</a-button>
    </div>
    <a-table :columns="columns" :data-source="list" :loading="loading" row-key="id" :pagination="pagination" @change="handleTableChange" />
  </div>
</template>

<script>
import { listRequestLogs } from '@/api/system'

export default {
  name: 'AdminAgentRequestLog',
  data() {
    return {
      loading: false,
      list: [],
      filters: { agent_id: undefined, model: '' },
      pagination: { current: 1, pageSize: 20, total: 0 },
      columns: [
        { title: '代理ID', dataIndex: 'agent_id', key: 'agent_id' },
        { title: '用户', dataIndex: 'username', key: 'username' },
        { title: '请求模型', dataIndex: 'requested_model', key: 'requested_model' },
        { title: '实际模型', dataIndex: 'actual_model', key: 'actual_model' },
        { title: '状态', dataIndex: 'status', key: 'status' },
        { title: '总Token', dataIndex: 'total_tokens', key: 'total_tokens' },
        { title: '时间', dataIndex: 'created_at', key: 'created_at' }
      ]
    }
  },
  mounted() {
    this.fetchList()
  },
  methods: {
    async fetchList() {
      this.loading = true
      try {
        const res = await listRequestLogs({
          page: this.pagination.current,
          page_size: this.pagination.pageSize,
          agent_id: this.filters.agent_id || undefined,
          model: this.filters.model || undefined
        })
        const data = res.data || {}
        this.list = data.list || []
        this.pagination.total = data.total || 0
      } finally {
        this.loading = false
      }
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchList()
    }
  }
}
</script>

<style lang="less" scoped>
.page { background: #fff; padding: 20px; border-radius: 16px; }
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; }
</style>
