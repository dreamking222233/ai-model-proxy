<template>
  <div class="cache-stats">
    <el-card class="box-card">
      <div slot="header" class="clearfix">
        <span>缓存统计</span>
      </div>

      <el-row :gutter="20" style="margin-bottom: 20px">
        <el-col :span="6">
          <el-statistic title="缓存命中次数" :value="stats.hit_count" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="缓存未命中次数" :value="stats.miss_count" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="命中率" :value="stats.hit_rate" :precision="2" suffix="%" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="节省 Tokens" :value="stats.saved_tokens" />
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-statistic title="节省费用" :value="stats.saved_cost" :precision="6" prefix="$" />
        </el-col>
        <el-col :span="12">
          <el-button type="danger" @click="clearCache">清空我的缓存</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card class="box-card" style="margin-top: 20px">
      <div slot="header" class="clearfix">
        <span>缓存配置</span>
      </div>

      <el-form label-width="120px">
        <el-form-item label="缓存开关">
          <el-switch
            v-model="config.cache_enabled"
            :active-value="1"
            :inactive-value="0"
            disabled
          />
          <span style="margin-left: 10px; color: #999">（由管理员控制）</span>
        </el-form-item>
        <el-form-item label="缓存计费">
          <el-switch
            v-model="config.cache_billing_enabled"
            :active-value="1"
            :inactive-value="0"
            disabled
          />
          <span style="margin-left: 10px; color: #999">（由管理员控制）</span>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script>
import axios from '@/utils/request'

export default {
  name: 'CacheStats',
  data() {
    return {
      stats: {
        hit_count: 0,
        miss_count: 0,
        hit_rate: 0,
        saved_tokens: 0,
        saved_cost: 0
      },
      config: {
        cache_enabled: 1,
        cache_billing_enabled: 0
      }
    }
  },
  mounted() {
    this.loadStats()
    this.loadConfig()
  },
  methods: {
    async loadStats() {
      try {
        const res = await axios.get('/api/user/cache/stats')
        if (res.data.code === 0) {
          this.stats = res.data.data
        }
      } catch (error) {
        console.error('Failed to load stats:', error)
      }
    },
    async loadConfig() {
      try {
        const res = await axios.get('/api/user/cache/config')
        if (res.data.code === 0) {
          this.config = res.data.data
        }
      } catch (error) {
        console.error('Failed to load config:', error)
      }
    },
    async clearCache() {
      try {
        await this.$confirm('确定要清空缓存吗？', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        const res = await axios.delete('/api/user/cache/clear')
        if (res.data.code === 0) {
          this.$message.success('清空成功')
          this.loadStats()
        } else {
          this.$message.error(res.data.message || '清空失败')
        }
      } catch (error) {
        if (error !== 'cancel') {
          this.$message.error('清空失败')
        }
      }
    }
  }
}
</script>

<style scoped>
.cache-stats {
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
