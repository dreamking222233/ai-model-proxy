<template>
  <div class="cache-manage">
    <el-card class="box-card">
      <div slot="header" class="clearfix">
        <span>缓存管理</span>
      </div>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="全局统计" name="stats">
          <el-row :gutter="20">
            <el-col :span="6">
              <el-statistic title="总命中次数" :value="globalStats.total_hits" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="总未命中次数" :value="globalStats.total_misses" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="命中率" :value="globalStats.hit_rate" :precision="2" suffix="%" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="节省 Tokens" :value="globalStats.total_saved_tokens" />
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane label="用户缓存配置" name="users">
          <el-table :data="users" style="width: 100%">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="username" label="用户名" width="150" />
            <el-table-column label="缓存开关" width="120">
              <template slot-scope="scope">
                <el-switch
                  v-model="scope.row.cache_enabled"
                  :active-value="1"
                  :inactive-value="0"
                  @change="updateCacheConfig(scope.row)"
                />
              </template>
            </el-table-column>
            <el-table-column label="缓存计费" width="120">
              <template slot-scope="scope">
                <el-switch
                  v-model="scope.row.cache_billing_enabled"
                  :active-value="1"
                  :inactive-value="0"
                  @change="updateCacheConfig(scope.row)"
                />
              </template>
            </el-table-column>
            <el-table-column prop="cache_hit_count" label="命中次数" width="120" />
            <el-table-column prop="cache_saved_tokens" label="节省 Tokens" width="150" />
            <el-table-column label="操作" width="200">
              <template slot-scope="scope">
                <el-button size="mini" @click="viewUserStats(scope.row)">查看统计</el-button>
                <el-button size="mini" type="danger" @click="clearUserCache(scope.row)">清空缓存</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            @current-change="handlePageChange"
            :current-page="page"
            :page-size="pageSize"
            layout="total, prev, pager, next"
            :total="total"
            style="margin-top: 20px; text-align: right"
          />
        </el-tab-pane>

        <el-tab-pane label="缓存日志" name="logs">
          <el-table :data="logs" style="width: 100%">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="user_id" label="用户ID" width="100" />
            <el-table-column prop="model" label="模型" width="200" />
            <el-table-column prop="cache_status" label="状态" width="100">
              <template slot-scope="scope">
                <el-tag :type="scope.row.cache_status === 'HIT' ? 'success' : 'info'">
                  {{ scope.row.cache_status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="prompt_tokens" label="Prompt Tokens" width="150" />
            <el-table-column prop="completion_tokens" label="Completion Tokens" width="180" />
            <el-table-column prop="saved_tokens" label="节省 Tokens" width="150" />
            <el-table-column prop="created_at" label="时间" width="180" />
          </el-table>

          <el-pagination
            @current-change="handleLogPageChange"
            :current-page="logPage"
            :page-size="logPageSize"
            layout="total, prev, pager, next"
            :total="logTotal"
            style="margin-top: 20px; text-align: right"
          />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script>
import axios from '@/utils/request'

export default {
  name: 'CacheManage',
  data() {
    return {
      activeTab: 'stats',
      globalStats: {
        total_hits: 0,
        total_misses: 0,
        hit_rate: 0,
        total_saved_tokens: 0
      },
      users: [],
      page: 1,
      pageSize: 20,
      total: 0,
      logs: [],
      logPage: 1,
      logPageSize: 20,
      logTotal: 0
    }
  },
  mounted() {
    this.loadGlobalStats()
    this.loadUsers()
    this.loadLogs()
  },
  methods: {
    async loadGlobalStats() {
      try {
        const res = await axios.get('/api/admin/cache/stats/global')
        if (res.data.code === 0) {
          this.globalStats = res.data.data
        }
      } catch (error) {
        console.error('Failed to load global stats:', error)
      }
    },
    async loadUsers() {
      try {
        const res = await axios.get('/api/admin/users', {
          params: { page: this.page, page_size: this.pageSize }
        })
        if (res.data.code === 0) {
          this.users = res.data.data.items
          this.total = res.data.data.total
        }
      } catch (error) {
        this.$message.error('加载用户列表失败')
      }
    },
    async loadLogs() {
      try {
        const res = await axios.get('/api/admin/cache/logs', {
          params: { page: this.logPage, page_size: this.logPageSize }
        })
        if (res.data.code === 0) {
          this.logs = res.data.data.items
          this.logTotal = res.data.data.total
        }
      } catch (error) {
        console.error('Failed to load logs:', error)
      }
    },
    async updateCacheConfig(user) {
      try {
        const res = await axios.put(`/api/admin/cache/config/${user.id}`, {
          cache_enabled: user.cache_enabled,
          cache_billing_enabled: user.cache_billing_enabled
        })
        if (res.data.code === 0) {
          this.$message.success('更新成功')
        } else {
          this.$message.error(res.data.message || '更新失败')
          this.loadUsers()
        }
      } catch (error) {
        this.$message.error('更新失败')
        this.loadUsers()
      }
    },
    async clearUserCache(user) {
      try {
        await this.$confirm(`确定要清空用户 ${user.username} 的缓存吗？`, '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        const res = await axios.delete(`/api/admin/cache/clear/${user.id}`)
        if (res.data.code === 0) {
          this.$message.success('清空成功')
          this.loadUsers()
        } else {
          this.$message.error(res.data.message || '清空失败')
        }
      } catch (error) {
        if (error !== 'cancel') {
          this.$message.error('清空失败')
        }
      }
    },
    viewUserStats(user) {
      this.$router.push(`/admin/cache/stats/${user.id}`)
    },
    handlePageChange(page) {
      this.page = page
      this.loadUsers()
    },
    handleLogPageChange(page) {
      this.logPage = page
      this.loadLogs()
    }
  }
}
</script>

<style scoped>
.cache-manage {
  padding: 20px;
}
.clearfix:before,
.clearfix:after {
  display: table;
  content: "";
}
.clearfix:after {
  clear: both;
}
</style>
