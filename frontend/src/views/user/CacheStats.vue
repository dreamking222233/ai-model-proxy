<template>
  <div class="cache-stats-page">
    <div class="page-container">
      <!-- Header Section -->
      <section class="page-header-section animate__animated animate__fadeIn">
        <div class="header-glass">
          <div class="header-left">
            <div class="header-badge">OPTIMIZATION</div>
            <h1 class="page-title">缓存<span>效能</span>统计</h1>
            <p class="page-desc">实时监控 Prompt 缓存命中情况，直观展示资源节省与效率提升。</p>
          </div>
          <div class="header-right">
            <a-button type="danger" ghost class="clear-btn" @click="clearCache">
              <a-icon type="delete" /> 清空个人缓存
            </a-button>
          </div>
        </div>
      </section>

      <!-- Stats Grid -->
      <div class="stats-grid">
        <div class="stat-glass-card animate__animated animate__fadeInUp" style="animation-delay: 0.1s">
          <div class="stat-icon hit"><a-icon type="thunderbolt" /></div>
          <div class="stat-content">
            <div class="label">缓存命中次数</div>
            <div class="value">{{ stats.hit_count }} <small>次</small></div>
          </div>
        </div>
        <div class="stat-glass-card animate__animated animate__fadeInUp" style="animation-delay: 0.2s">
          <div class="stat-icon miss"><a-icon type="close-circle" /></div>
          <div class="stat-content">
            <div class="label">未命中次数</div>
            <div class="value">{{ stats.miss_count }} <small>次</small></div>
          </div>
        </div>
        <div class="stat-glass-card animate__animated animate__fadeInUp" style="animation-delay: 0.3s">
          <div class="stat-icon rate"><a-icon type="dashboard" /></div>
          <div class="stat-content">
            <div class="label">综合命中率</div>
            <div class="value">{{ stats.hit_rate.toFixed(2) }} <small>%</small></div>
            <a-progress :percent="stats.hit_rate" size="small" :show-info="false" stroke-color="#667eea" class="mini-progress" />
          </div>
        </div>
      </div>

      <!-- Detail Cards -->
      <div class="detail-row">
        <div class="glass-card resource-card animate__animated animate__fadeInUp" style="animation-delay: 0.4s">
          <div class="card-header">
            <h3><a-icon type="rocket" /> 资源节省概览</h3>
          </div>
          <div class="resource-stats">
            <div class="res-item">
              <div class="res-label">节省总 Tokens</div>
              <div class="res-value">{{ formatNumber(stats.saved_tokens) }}</div>
            </div>
            <div class="res-divider"></div>
            <div class="res-item">
              <div class="res-label">节省预估费用</div>
              <div class="res-value text-green">${{ stats.saved_cost.toFixed(6) }}</div>
            </div>
          </div>
        </div>

        <div class="glass-card config-card animate__animated animate__fadeInUp" style="animation-delay: 0.5s">
          <div class="card-header">
            <h3><a-icon type="setting" /> 缓存策略配置</h3>
          </div>
          <div class="config-form">
            <div class="config-item">
              <div class="c-info">
                <div class="c-title">全局缓存开关</div>
                <div class="c-desc">启用后将自动复用重复的 Prompt 片段</div>
              </div>
              <a-switch :checked="config.cache_enabled === 1" disabled />
            </div>
            <div class="config-item">
              <div class="c-info">
                <div class="c-title">缓存核销计费</div>
                <div class="c-desc">缓存命中部分的 Token 计费权重</div>
              </div>
              <a-switch :checked="config.cache_billing_enabled === 1" disabled />
            </div>
            <div class="admin-notice">
              <a-icon type="info-circle" /> 策略由管理员统一管控，暂不支持个人修改。
            </div>
          </div>
        </div>
      </div>
    </div>
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
        await this.$confirm({
          title: '确定要清空缓存吗？',
          content: '该操作将移除您名下的所有 Prompt 缓存分段，下次请求将重新构建。',
          okText: '确定',
          okType: 'danger',
          cancelText: '取消',
        })
        const res = await axios.delete('/api/user/cache/clear')
        if (res.data.code === 0) {
          this.$message.success('清空成功')
          this.loadStats()
        }
      } catch (error) {
        if (error !== 'cancel') {
          this.$message.error('操作取消')
        }
      }
    },
    formatNumber(n) {
      return Number(n || 0).toLocaleString()
    }
  }
}
</script>

<style lang="less" scoped>
@import url('https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css');

.cache-stats-page {
  position: relative;
  min-height: calc(100vh - 100px);
  padding: 40px 20px;
  background: transparent;

  .page-container {
    max-width: 1200px;
    margin: 0 auto;
    position: relative;
    z-index: 1;
  }

  /* ===== Page Header ===== */
  .page-header-section {
    margin-bottom: 32px;
    .header-glass {
      background: rgba(255, 255, 255, 0.7);
      backdrop-filter: blur(20px);
      border-radius: 24px;
      padding: 32px 40px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border: 1px solid rgba(255, 255, 255, 0.6);
      box-shadow: 0 10px 40px rgba(0,0,0,0.03);

      .header-badge {
        display: inline-block; padding: 2px 12px; background: rgba(102, 126, 234, 0.1); color: #667eea;
        border-radius: 20px; font-size: 11px; font-weight: 800; letter-spacing: 1px; margin-bottom: 12px;
      }
      .page-title {
        font-size: 32px; font-weight: 800; color: #1a1a2e; margin-bottom: 8px;
        span { background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
      }
      .page-desc { font-size: 14px; color: #8c8c8c; margin: 0; }
    }
  }

  .clear-btn { border-radius: 10px; font-weight: 600; }

  /* ===== Stats Grid ===== */
  .stats-grid {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; margin-bottom: 32px;
  }
  .stat-glass-card {
    background: rgba(255, 255, 255, 0.82); backdrop-filter: blur(15px); border-radius: 24px; padding: 24px;
    border: 1px solid rgba(255, 255, 255, 0.6); display: flex; align-items: center; gap: 20px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.02); transition: all 0.3s;
    &:hover { transform: translateY(-5px); background: #fff; }

    .stat-icon {
      width: 56px; height: 56px; border-radius: 16px; display: flex; align-items: center; justify-content: center; font-size: 24px;
      &.hit { background: rgba(102, 126, 234, 0.1); color: #667eea; }
      &.miss { background: rgba(245, 34, 45, 0.1); color: #f5222d; }
      &.rate { background: rgba(54, 207, 201, 0.1); color: #36cfc9; }
    }

    .stat-content {
      flex: 1;
      .label { font-size: 13px; color: #8c8c8c; font-weight: 600; margin-bottom: 4px; }
      .value { font-size: 26px; font-weight: 800; color: #1a1a2e; font-family: 'MonoLisa', monospace; small { font-size: 14px; font-weight: 500; font-family: var(--font-family); margin-left: 4px; color: #bfbfbf; } }
      .mini-progress { margin-top: 8px; }
    }
  }

  /* ===== Details ===== */
  .detail-row { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
  .glass-card {
    background: rgba(255, 255, 255, 0.75); backdrop-filter: blur(20px); border-radius: 28px; padding: 32px;
    border: 1px solid rgba(255, 255, 255, 0.6);
    
    .card-header { margin-bottom: 24px; h3 { font-size: 18px; font-weight: 800; color: #1a1a2e; margin: 0; display: flex; align-items: center; gap: 10px; } }
  }

  .resource-stats {
    display: flex; align-items: center; justify-content: space-around; padding: 20px 0;
    .res-item { text-align: center; }
    .res-label { font-size: 14px; color: #8c8c8c; margin-bottom: 12px; font-weight: 600; }
    .res-value { font-size: 32px; font-weight: 800; color: #1a1a2e; font-family: 'MonoLisa', monospace; }
    .text-green { color: #52c41a; }
    .res-divider { width: 1px; height: 60px; background: #f0f0f0; }
  }

  .config-form {
    display: flex; flex-direction: column; gap: 20px;
    .config-item {
      display: flex; justify-content: space-between; align-items: center;
      padding-bottom: 16px; border-bottom: 1px solid #f8f8f8;
      .c-title { font-size: 15px; font-weight: 700; color: #2d3748; margin-bottom: 2px; }
      .c-desc { font-size: 12px; color: #a0aec0; }
    }
    .admin-notice {
      margin-top: 10px; padding: 12px 16px; background: #f5f7ff; border-radius: 12px;
      color: #667eea; font-size: 12px; font-weight: 600;
    }
  }

  @media (max-width: 900px) {
    .stats-grid, .detail-row { grid-template-columns: 1fr; }
  }
}
</style>
