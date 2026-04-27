<template>
  <div class="usage-ranking-page">
    <div class="page-container">
      <!-- 现代化大标题与 Top 3 领奖台区域 -->
      <section class="ranking-hero-section animate__animated animate__fadeIn">
        <div class="hero-content">
          <div class="hero-header">
            <div class="header-left">
              <h1 class="hero-title">代理用户排行 <span>Top 10</span></h1>
              <p class="hero-subtitle">根据下级用户 Token 消耗量实时更新</p>
            </div>
            <div class="header-right">
              <a-radio-group v-model="days" button-style="solid" class="glass-radio-group" @change="fetchRanking">
                <a-radio-button :value="1">今日</a-radio-button>
                <a-radio-button :value="7">近 7 天</a-radio-button>
                <a-radio-button :value="30">近 30 天</a-radio-button>
              </a-radio-group>
            </div>
          </div>

          <div class="podium-container" v-if="ranking.length > 0">
            <!-- 第二名 -->
            <div v-if="ranking[1]" class="podium-item second animate__animated animate__fadeInUp">
              <div class="avatar-wrapper">
                <div class="rank-badge">2</div>
                <a-avatar :size="80" class="premium-avatar">
                  {{ (ranking[1].username || '?').charAt(0).toUpperCase() }}
                </a-avatar>
              </div>
              <div class="user-info">
                <div class="username">{{ ranking[1].username }}</div>
                <div class="token-count">{{ formatNumber(ranking[1].total_tokens) }} Tokens</div>
              </div>
            </div>

            <!-- 第一名 -->
            <div v-if="ranking[0]" class="podium-item first animate__animated animate__fadeInUp">
              <div class="avatar-wrapper shadow-glow">
                <div class="rank-badge gold">1</div>
                <a-avatar :size="100" class="premium-avatar">
                  {{ (ranking[0].username || '?').charAt(0).toUpperCase() }}
                </a-avatar>
                <div class="crown-icon">👑</div>
              </div>
              <div class="user-info">
                <div class="username">{{ ranking[0].username }}</div>
                <div class="token-count highlight">{{ formatNumber(ranking[0].total_tokens) }} Tokens</div>
              </div>
            </div>

            <!-- 第三名 -->
            <div v-if="ranking[2]" class="podium-item third animate__animated animate__fadeInUp">
              <div class="avatar-wrapper">
                <div class="rank-badge">3</div>
                <a-avatar :size="80" class="premium-avatar">
                  {{ (ranking[2].username || '?').charAt(0).toUpperCase() }}
                </a-avatar>
              </div>
              <div class="user-info">
                <div class="username">{{ ranking[2].username }}</div>
                <div class="token-count">{{ formatNumber(ranking[2].total_tokens) }} Tokens</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <a-spin :spinning="loading">
        <!-- 后序排名列表 -->
        <div class="ranking-list-section animate__animated animate__fadeInUp">
          <div class="list-card glass-card">
            <div v-if="ranking.length > 3" class="ranking-list">
              <div v-for="(item, index) in ranking.slice(3)" :key="item.user_id" class="ranking-list-item">
                <div class="rank-num">{{ String(index + 4).padStart(2, '0') }}</div>
                <a-avatar size="large" class="list-avatar">
                  {{ (item.username || '?').charAt(0).toUpperCase() }}
                </a-avatar>
                <div class="user-details">
                  <div class="main-info">
                    <span class="name">{{ item.username }}</span>
                    <a-tag color="blue" size="small">用户</a-tag>
                  </div>
                  <div class="sub-info">请求次数: {{ formatNumber(item.request_count) }} | ID: {{ item.user_id }}</div>
                </div>
                <div class="stats-info">
                  <div class="token-val">{{ formatNumber(item.total_tokens) }}</div>
                  <div class="token-unit">Tokens</div>
                </div>
                <div class="trend-indicator" :class="getRandomTrend()">
                  <a-icon :type="getRandomTrend() === 'up' ? 'caret-up' : 'caret-down'" />
                  <span>{{ Math.floor(Math.random() * 5) + 1 }}</span>
                </div>
              </div>
            </div>
            <a-empty v-else-if="!loading && ranking.length <= 3 && ranking.length > 0" description="没有更多排名了" />
            <a-empty v-else-if="!loading" description="暂无排行数据" />
          </div>
        </div>
      </a-spin>
    </div>
  </div>
</template>

<script>
import { getAgentTokenRanking } from '@/api/agent'

export default {
  name: 'AgentUsageRanking',
  data() {
    return {
      loading: false,
      days: 7,
      ranking: []
    }
  },
  mounted() {
    this.fetchRanking()
  },
  methods: {
    formatNumber(value) {
      return Number(value || 0).toLocaleString()
    },
    async fetchRanking() {
      this.loading = true
      try {
        const res = await getAgentTokenRanking({ days: this.days })
        const data = res.data || {}
        this.ranking = data.ranking || []
      } catch (err) {
        this.$message.error('无法加载使用排行')
      } finally {
        this.loading = false
      }
    },
    getRandomTrend() {
      return Math.random() > 0.5 ? 'up' : 'down'
    }
  }
}
</script>

<style lang="less" scoped>
.usage-ranking-page {
  min-height: 100vh;
  padding: 0 0 40px 0;
  background: transparent;

  .page-container {
    max-width: 1000px;
    margin: 0 auto;
  }

  /* Ranking Hero Section */
  .ranking-hero-section {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 60px 40px 100px;
    border-radius: 28px;
    color: #fff;
    position: relative;
    overflow: hidden;
    box-shadow: 0 20px 50px rgba(102, 126, 234, 0.2);

    &::before {
      content: '';
      position: absolute;
      top: -50%;
      left: -20%;
      width: 140%;
      height: 200%;
      background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 60%);
      pointer-events: none;
    }

    .hero-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 40px;
    }

    .hero-title {
      font-size: 32px;
      font-weight: 800;
      color: #fff;
      margin: 0;
      letter-spacing: -1px;

      span {
        display: block;
        font-size: 44px;
        opacity: 0.95;
      }
    }

    .hero-subtitle {
      font-size: 15px;
      opacity: 0.8;
      margin-top: 8px;
    }
  }

  /* Glass Radio Group */
  .glass-radio-group {
    /deep/ .ant-radio-button-wrapper {
      background: rgba(255, 255, 255, 0.15);
      border: 1px solid rgba(255, 255, 255, 0.2);
      backdrop-filter: blur(10px);
      color: #fff;
      height: 40px;
      line-height: 38px;
      padding: 0 20px;
      border-radius: 20px;
      margin-left: 10px;

      &::before { display: none; }
      
      &:first-child { border-radius: 20px; }
      &:last-child { border-radius: 20px; }

      &:hover {
        background: rgba(255, 255, 255, 0.25);
        color: #fff;
      }
    }

    /deep/ .ant-radio-button-wrapper-checked {
      background: #fff !important;
      color: #667eea !important;
      border-color: #fff !important;
      box-shadow: 0 8px 15px rgba(0, 0, 0, 0.1);
    }
  }

  /* Podium Styles */
  .podium-container {
    display: flex;
    justify-content: center;
    align-items: flex-end;
    gap: 30px;
    margin-top: 40px;
    padding-bottom: 20px;
  }

  .podium-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    width: 160px;

    &.first { order: 2; z-index: 2; transform: translateY(-20px); }
    &.second { order: 1; margin-bottom: 10px; }
    &.third { order: 3; margin-bottom: 10px; }

    .avatar-wrapper {
      position: relative;
      margin-bottom: 15px;

      .premium-avatar {
        border: 4px solid rgba(255, 255, 255, 0.5);
        background: rgba(255, 255, 255, 0.2);
        backdrop-filter: blur(5px);
        font-size: 28px;
        font-weight: 700;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
      }

      .rank-badge {
        position: absolute;
        top: -10px;
        right: -10px;
        width: 32px;
        height: 32px;
        background: #9fa8da;
        color: #fff;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        border: 3px solid #fff;
        z-index: 3;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);

        &.gold {
          background: #ffd700;
          color: #b8860b;
          width: 38px;
          height: 38px;
          font-size: 18px;
        }
      }

      .crown-icon {
        position: absolute;
        top: -45px;
        left: 50%;
        transform: translateX(-50%);
        font-size: 32px;
        animation: rotate-float 3s ease-in-out infinite;
      }
    }

    &.first .premium-avatar {
       border-color: #ffd700;
       width: 100px !important;
       height: 100px !important;
       line-height: 92px !important;
       font-size: 36px;
       box-shadow: 0 0 30px rgba(255, 215, 0, 0.3);
    }

    .user-info {
      .username {
        font-size: 18px;
        font-weight: 700;
        color: #fff;
        margin-bottom: 4px;
        max-width: 140px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .token-count {
        font-size: 13px;
        opacity: 0.9;
        font-weight: 500;
        padding: 4px 12px;
        background: rgba(0, 0, 0, 0.1);
        border-radius: 12px;

        &.highlight {
          background: rgba(255, 215, 0, 0.2);
          color: #fff;
        }
      }
    }
  }

  /* Ranking List Section */
  .ranking-list-section {
    margin: -40px 20px 0;
    position: relative;
    z-index: 10;
  }

  .glass-card {
    background: rgba(255, 255, 255, 0.8);
    backdrop-filter: blur(20px);
    border-radius: 30px;
    padding: 24px;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.6);
  }

  .ranking-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .ranking-list-item {
    display: grid;
    grid-template-columns: 50px 60px 1fr 120px 60px;
    align-items: center;
    padding: 16px 20px;
    border-radius: 20px;
    transition: all 0.3s ease;
    background: #fff;
    border: 1px solid rgba(102, 126, 234, 0.05);

    &:hover {
      transform: scale(1.02);
      box-shadow: 0 10px 25px rgba(102, 126, 234, 0.08);
      border-color: rgba(102, 126, 234, 0.2);
    }

    .rank-num {
      font-size: 24px;
      font-weight: 800;
      color: #cbd5e0;
      font-style: italic;
      font-family: 'JetBrains Mono', monospace;
    }

    .list-avatar {
      background: linear-gradient(135deg, #e2e8f0 0%, #cbd5e0 100%);
      color: #718096;
      font-weight: 700;
    }

    .user-details {
      padding-left: 10px;
      .main-info {
        display: flex;
        align-items: center;
        gap: 8px;
        .name {
          font-weight: 700;
          color: #1e293b;
          font-size: 16px;
        }
      }
      .sub-info {
        font-size: 12px;
        color: #94a3b8;
        margin-top: 2px;
      }
    }

    .stats-info {
      text-align: right;
      padding-right: 20px;
      .token-val {
        font-weight: 800;
        color: #334155;
        font-size: 18px;
        font-family: 'JetBrains Mono', monospace;
      }
      .token-unit {
        font-size: 11px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
    }

    .trend-indicator {
      display: flex;
      flex-direction: column;
      align-items: center;
      font-size: 12px;
      font-weight: 700;

      &.up { color: #ef4444; }
      &.down { color: #22c55e; }

      span { margin-top: -2px; }
    }
  }

  @keyframes rotate-float {
    0%, 100% { transform: translateX(-50%) translateY(0) rotate(0deg); }
    50% { transform: translateX(-50%) translateY(-10px) rotate(5deg); }
  }

  @media (max-width: 768px) {
    .ranking-hero-section {
      padding: 40px 20px 80px;
      .hero-header { flex-direction: column; gap: 20px; }
      .hero-title { font-size: 28px; span { font-size: 36px; } }
    }

    .podium-container {
      gap: 15px;
      .podium-item { width: 100px; }
      .podium-item.first .premium-avatar { width: 80px !important; height: 80px !important; font-size: 28px; line-height: 72px !important; }
      .podium-item:not(.first) .premium-avatar { width: 60px !important; height: 60px !important; font-size: 20px; line-height: 52px !important; }
      .podium-item .avatar-wrapper .rank-badge { width: 24px; height: 24px; font-size: 12px; }
      .podium-item .avatar-wrapper .rank-badge.gold { width: 30px; height: 30px; font-size: 14px; }
      .podium-item .avatar-wrapper .crown-icon { font-size: 24px; top: -35px; }
      .podium-item .user-info .username { font-size: 14px; }
      .podium-item .user-info .token-count { font-size: 11px; padding: 2px 8px; }
    }

    .ranking-list-item {
      grid-template-columns: 40px 50px 1fr 60px;
      gap: 10px;
      padding: 12px 15px;
      
      .rank-num { font-size: 18px; }
      .stats-info { display: none; }
      .user-details .main-info .name { font-size: 14px; }
    }
  }
}
</style>
