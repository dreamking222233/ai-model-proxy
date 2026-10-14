<template>
  <div class="usage-ranking-page">
    <div class="page-container">
      <!-- 现代化大标题与 Top 3 领奖台区域 -->
      <section class="ranking-hero-section">
        <!-- 梦幻背景流光与水晶皇冠装饰 -->
        <div class="hero-bg-decorations">
          <div class="glow-orb glow-orb-1"></div>
          <div class="glow-orb glow-orb-2"></div>

          <!-- 水晶皇冠与轨道装饰 -->
          <div class="crystal-crown-container">
            <svg class="crystal-crown-svg" viewBox="0 0 220 180" fill="none" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="crystalFacet1" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stop-color="rgba(255, 255, 255, 0.75)"/>
                  <stop offset="100%" stop-color="rgba(216, 180, 254, 0.25)"/>
                </linearGradient>
                <linearGradient id="crystalFacet2" x1="1" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="rgba(238, 242, 255, 0.65)"/>
                  <stop offset="100%" stop-color="rgba(192, 132, 252, 0.2)"/>
                </linearGradient>
                <linearGradient id="crystalFacet3" x1="0" y1="1" x2="1" y2="0">
                  <stop offset="0%" stop-color="rgba(255, 255, 255, 0.9)"/>
                  <stop offset="100%" stop-color="rgba(168, 85, 247, 0.35)"/>
                </linearGradient>
                <linearGradient id="orbitGrad" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stop-color="rgba(255, 255, 255, 0.8)"/>
                  <stop offset="50%" stop-color="rgba(216, 180, 254, 0.5)"/>
                  <stop offset="100%" stop-color="rgba(255, 255, 255, 0.1)"/>
                </linearGradient>
              </defs>

              <!-- 发光轨道椭圆环 -->
              <g transform="rotate(-15 110 90)">
                <ellipse cx="110" cy="95" rx="80" ry="24" stroke="url(#orbitGrad)" stroke-width="2" fill="none" stroke-dasharray="6 4"/>
                <ellipse cx="110" cy="95" rx="96" ry="30" stroke="rgba(255, 255, 255, 0.2)" stroke-width="1.2" fill="none"/>
                <!-- 轨道发光星子 -->
                <circle cx="28" cy="92" r="3.5" fill="#ffffff" />
                <circle cx="188" cy="102" r="4.5" fill="#ffffff" />
                <circle cx="140" cy="120" r="2.5" fill="#f3e8ff"/>
                <circle cx="75" cy="74" r="3" fill="#ffffff"/>
              </g>

              <!-- 水晶皇冠多棱镜身 -->
              <g class="crystal-body">
                <polygon points="60,110 38,55 75,75 110,32 145,75 182,55 160,110" fill="url(#crystalFacet1)" stroke="rgba(255,255,255,0.7)" stroke-width="1.5"/>
                <polygon points="110,32 75,75 110,95" fill="url(#crystalFacet2)" stroke="rgba(255,255,255,0.8)" stroke-width="1"/>
                <polygon points="110,32 145,75 110,95" fill="url(#crystalFacet3)" stroke="rgba(255,255,255,0.8)" stroke-width="1"/>
                <polygon points="38,55 75,75 60,110" fill="url(#crystalFacet2)" stroke="rgba(255,255,255,0.6)" stroke-width="1"/>
                <polygon points="182,55 145,75 160,110" fill="url(#crystalFacet1)" stroke="rgba(255,255,255,0.6)" stroke-width="1"/>
                <polygon points="75,75 110,95 145,75 110,110" fill="url(#crystalFacet3)" stroke="rgba(255,255,255,0.9)" stroke-width="1.2"/>
                <polygon points="60,110 110,110 110,95 75,75" fill="url(#crystalFacet1)"/>
                <polygon points="160,110 110,110 110,95 145,75" fill="url(#crystalFacet2)"/>

                <!-- 底部水晶基座弧带 -->
                <path d="M56 112 C75 125, 145 125, 164 112 L160 119 C142 131, 78 131, 60 119 Z" fill="url(#crystalFacet3)" stroke="rgba(255,255,255,0.8)" stroke-width="1"/>

                <!-- 顶端水晶晶球 -->
                <circle cx="38" cy="55" r="4" fill="#ffffff" />
                <circle cx="75" cy="75" r="3" fill="#f5d0fe"/>
                <circle cx="110" cy="32" r="5.5" fill="#ffffff" />
                <circle cx="145" cy="75" r="3" fill="#f5d0fe"/>
                <circle cx="182" cy="55" r="4" fill="#ffffff" />
              </g>
            </svg>
            <div class="crystal-slogan">SHOP MORE EXCITING TOMORROW</div>
          </div>
        </div>

        <div class="hero-content">
          <!-- 头部信息栏 -->
          <div class="hero-header">
            <div class="header-left">
              <!-- 顶部微标 -->
              <div class="mini-brand">
                <svg class="brand-crown-icon" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M5 16L3 5L8.5 10L12 4L15.5 10L21 5L19 16H5M19 19C19 19.6 18.6 20 18 20H6C5.4 20 5 19.6 5 19V18H19V19Z"/>
                </svg>
                <span>消费创造精彩</span>
              </div>
              <h1 class="hero-title">{{ rankingTitle }} <span class="top10-highlight">Top 10</span></h1>
              <p class="hero-subtitle">按{{ rankingRangeLabel }}美元消费实时更新</p>

              <!-- 实时更新提示胶囊 -->
              <div class="live-status-capsule" @click="handleManualRefresh" :title="'点击手动刷新'">
                <span class="live-dot"></span>
                <span class="live-text">数据每分钟更新一次</span>
                <a-icon type="sync" :spin="loading" class="refresh-indicator" />
              </div>
            </div>

            <!-- 右侧时间切换按钮组 -->
            <div class="header-right">
              <div class="glass-pill-switcher">
                <button
                  type="button"
                  class="pill-switcher-item"
                  :class="{ active: days === 1 }"
                  @click="handleTimeChange(1)"
                >
                  今日
                </button>
                <button
                  type="button"
                  class="pill-switcher-item"
                  :class="{ active: days === 7 }"
                  @click="handleTimeChange(7)"
                >
                  近 7 天
                </button>
                <button
                  type="button"
                  class="pill-switcher-item"
                  :class="{ active: days === 30 }"
                  @click="handleTimeChange(30)"
                >
                  近 30 天
                </button>
              </div>
            </div>
          </div>

          <!-- Top 3 领奖台区域 -->
          <div class="podium-container" v-if="ranking.length > 0">
            <!-- 第二名 (左侧 - 亚军) -->
            <div
              v-if="ranking[1]"
              class="podium-card-wrapper rank-2"
              @click="showDetail(ranking[1], 2)"
              title="点击查看消费明细"
            >
              <!-- 银色皇冠 -->
              <div class="crown-box">
                <svg class="crown-svg silver" viewBox="0 0 80 56" fill="none">
                  <defs>
                    <linearGradient id="silverCrown" x1="0" y1="0" x2="1" y2="1">
                      <stop offset="0%" stop-color="#ffffff"/>
                      <stop offset="35%" stop-color="#cbd5e1"/>
                      <stop offset="70%" stop-color="#94a3b8"/>
                      <stop offset="100%" stop-color="#64748b"/>
                    </linearGradient>
                    <linearGradient id="silverBadge" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stop-color="#f8fafc"/>
                      <stop offset="100%" stop-color="#94a3b8"/>
                    </linearGradient>
                  </defs>
                  <path d="M12 44L6 18L24 28L40 8L56 28L74 18L68 44H12Z" fill="url(#silverCrown)" />
                  <path d="M10 44C10 44 24 49 40 49C56 49 70 44 70 44L68 49C68 49 55 54 40 54C25 54 12 49 12 49L10 44Z" fill="#475569"/>
                  <path d="M10 42C10 42 24 46 40 46C56 46 70 42 70 42L69 45C69 45 55 49 40 49C25 49 11 45 11 45L10 42Z" fill="#e2e8f0"/>
                  <circle cx="6" cy="18" r="3.5" fill="#f8fafc"/>
                  <circle cx="24" cy="27" r="3.5" fill="#f8fafc"/>
                  <circle cx="40" cy="8" r="4.5" fill="#ffffff"/>
                  <circle cx="56" cy="27" r="3.5" fill="#f8fafc"/>
                  <circle cx="74" cy="18" r="3.5" fill="#f8fafc"/>
                  <circle cx="40" cy="36" r="10" fill="url(#silverBadge)" stroke="#64748b" stroke-width="1.5"/>
                  <text x="40" y="41" text-anchor="middle" fill="#334155" font-size="13" font-weight="900" font-family="system-ui, sans-serif">2</text>
                </svg>
              </div>

              <!-- 玻璃拟态立柱卡片 -->
              <div class="podium-glass-card silver-glass">
                <div class="avatar-holder silver-holder">
                  <a-avatar v-if="ranking[1].avatar" :src="ranking[1].avatar" :size="64" />
                  <div v-else class="inner-avatar-letter">
                    {{ (ranking[1].username || '?').charAt(0).toUpperCase() }}
                  </div>
                </div>
                <div class="user-display-name" :title="ranking[1].username">{{ ranking[1].username }}</div>
                <div class="cost-capsule silver-cost">
                  ${{ formatCurrency(ranking[1].total_cost) }}
                </div>
                <div class="cost-label">{{ rankingRangeLabel }}消费金额</div>
              </div>
            </div>

            <!-- 若无第2名显示虚位以待 -->
            <div v-else-if="ranking[0]" class="podium-card-wrapper rank-2 is-placeholder">
              <div class="crown-box placeholder-crown">
                <svg class="crown-svg silver opacity-50" viewBox="0 0 80 56" fill="none">
                  <path d="M12 44L6 18L24 28L40 8L56 28L74 18L68 44H12Z" fill="rgba(255,255,255,0.4)" />
                  <circle cx="40" cy="36" r="10" fill="rgba(255,255,255,0.5)"/>
                  <text x="40" y="41" text-anchor="middle" fill="#94a3b8" font-size="13" font-weight="900">2</text>
                </svg>
              </div>
              <div class="podium-glass-card silver-glass placeholder-glass">
                <div class="avatar-holder silver-holder placeholder-avatar">
                  <div class="inner-avatar-letter opacity-70">2</div>
                </div>
                <div class="user-display-name placeholder-name">虚位以待</div>
                <div class="cost-capsule silver-cost placeholder-cost">$0.00</div>
                <div class="cost-label">待冲击</div>
              </div>
            </div>

            <!-- 第一名 (居中 - 冠军) -->
            <div
              v-if="ranking[0]"
              class="podium-card-wrapper rank-1"
              @click="showDetail(ranking[0], 1)"
              title="点击查看消费明细"
            >
              <!-- 金色大皇冠 -->
              <div class="crown-box gold-crown-box">
                <svg class="crown-svg gold" viewBox="0 0 84 60" fill="none">
                  <defs>
                    <linearGradient id="goldCrown" x1="0" y1="0" x2="1" y2="1">
                      <stop offset="0%" stop-color="#fff275"/>
                      <stop offset="35%" stop-color="#fbbf24"/>
                      <stop offset="70%" stop-color="#f59e0b"/>
                      <stop offset="100%" stop-color="#d97706"/>
                    </linearGradient>
                    <linearGradient id="goldBadge" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stop-color="#fffdf0"/>
                      <stop offset="100%" stop-color="#f59e0b"/>
                    </linearGradient>
                  </defs>
                  <path d="M12 46L6 18L25 29L42 7L59 29L78 18L72 46H12Z" fill="url(#goldCrown)" />
                  <path d="M10 46C10 46 25 51 42 51C59 51 74 46 74 46L72 52C72 52 58 57 42 57C26 57 12 52 12 52L10 46Z" fill="#b45309"/>
                  <path d="M10 44C10 44 25 48 42 48C59 48 74 44 74 44L73 47C73 47 58 51 42 51C26 51 11 47 11 47L10 44Z" fill="#fef08a"/>
                  <circle cx="6" cy="18" r="4" fill="#fef08a"/>
                  <circle cx="25" cy="28" r="4" fill="#fef08a"/>
                  <circle cx="42" cy="7" r="5" fill="#fffbeb"/>
                  <circle cx="59" cy="28" r="4" fill="#fef08a"/>
                  <circle cx="78" cy="18" r="4" fill="#fef08a"/>
                  <circle cx="42" cy="38" r="11" fill="url(#goldBadge)" stroke="#d97706" stroke-width="1.8"/>
                  <text x="42" y="43" text-anchor="middle" fill="#78350f" font-size="14" font-weight="900" font-family="system-ui, sans-serif">1</text>
                </svg>
              </div>

              <!-- 冠军高光玻璃立柱卡片 -->
              <div class="podium-glass-card gold-glass">
                <div class="avatar-holder gold-holder">
                  <a-avatar v-if="ranking[0].avatar" :src="ranking[0].avatar" :size="74" />
                  <div v-else class="inner-avatar-letter gold-letter">
                    1
                  </div>
                </div>
                <div class="user-display-name gold-name" :title="ranking[0].username">{{ ranking[0].username }}</div>
                <div class="cost-capsule gold-cost">
                  ${{ formatCurrency(ranking[0].total_cost) }}
                </div>
                <div class="cost-label">{{ rankingRangeLabel }}消费金额</div>
              </div>
            </div>

            <!-- 第三名 (右侧 - 季军) -->
            <div
              v-if="ranking[2]"
              class="podium-card-wrapper rank-3"
              @click="showDetail(ranking[2], 3)"
              title="点击查看消费明细"
            >
              <!-- 玫瑰金/古铜皇冠 -->
              <div class="crown-box">
                <svg class="crown-svg bronze" viewBox="0 0 80 56" fill="none">
                  <defs>
                    <linearGradient id="bronzeCrown" x1="0" y1="0" x2="1" y2="1">
                      <stop offset="0%" stop-color="#fed7aa"/>
                      <stop offset="35%" stop-color="#fb923c"/>
                      <stop offset="70%" stop-color="#ea580c"/>
                      <stop offset="100%" stop-color="#9a3412"/>
                    </linearGradient>
                    <linearGradient id="bronzeBadge" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stop-color="#ffedd5"/>
                      <stop offset="100%" stop-color="#ea580c"/>
                    </linearGradient>
                  </defs>
                  <path d="M12 44L6 18L24 28L40 8L56 28L74 18L68 44H12Z" fill="url(#bronzeCrown)" />
                  <path d="M10 44C10 44 24 49 40 49C56 49 70 44 70 44L68 49C68 49 55 54 40 54C25 54 12 49 12 49L10 44Z" fill="#7c2d12"/>
                  <path d="M10 42C10 42 24 46 40 46C56 46 70 42 70 42L69 45C69 45 55 49 40 49C25 49 11 45 11 45L10 42Z" fill="#ffedd5"/>
                  <circle cx="6" cy="18" r="3.5" fill="#ffedd5"/>
                  <circle cx="24" cy="27" r="3.5" fill="#ffedd5"/>
                  <circle cx="40" cy="8" r="4.5" fill="#fff7ed"/>
                  <circle cx="56" cy="27" r="3.5" fill="#ffedd5"/>
                  <circle cx="74" cy="18" r="3.5" fill="#ffedd5"/>
                  <circle cx="40" cy="36" r="10" fill="url(#bronzeBadge)" stroke="#c2410c" stroke-width="1.5"/>
                  <text x="40" y="41" text-anchor="middle" fill="#7c2d12" font-size="13" font-weight="900" font-family="system-ui, sans-serif">3</text>
                </svg>
              </div>

              <!-- 玻璃拟态立柱卡片 -->
              <div class="podium-glass-card bronze-glass">
                <div class="avatar-holder bronze-holder">
                  <a-avatar v-if="ranking[2].avatar" :src="ranking[2].avatar" :size="64" />
                  <div v-else class="inner-avatar-letter">
                    {{ (ranking[2].username || '?').charAt(0).toUpperCase() }}
                  </div>
                </div>
                <div class="user-display-name" :title="ranking[2].username">{{ ranking[2].username }}</div>
                <div class="cost-capsule bronze-cost">
                  ${{ formatCurrency(ranking[2].total_cost) }}
                </div>
                <div class="cost-label">{{ rankingRangeLabel }}消费金额</div>
              </div>
            </div>

            <!-- 若无第3名显示虚位以待 -->
            <div v-else-if="ranking[0]" class="podium-card-wrapper rank-3 is-placeholder">
              <div class="crown-box placeholder-crown">
                <svg class="crown-svg bronze opacity-50" viewBox="0 0 80 56" fill="none">
                  <path d="M12 44L6 18L24 28L40 8L56 28L74 18L68 44H12Z" fill="rgba(255,255,255,0.4)" />
                  <circle cx="40" cy="36" r="10" fill="rgba(255,255,255,0.5)"/>
                  <text x="40" y="41" text-anchor="middle" fill="#94a3b8" font-size="13" font-weight="900">3</text>
                </svg>
              </div>
              <div class="podium-glass-card bronze-glass placeholder-glass">
                <div class="avatar-holder bronze-holder placeholder-avatar">
                  <div class="inner-avatar-letter opacity-70">3</div>
                </div>
                <div class="user-display-name placeholder-name">虚位以待</div>
                <div class="cost-capsule bronze-cost placeholder-cost">$0.00</div>
                <div class="cost-label">待冲击</div>
              </div>
            </div>
          </div>

          <!-- 完全无数据占位 -->
          <div v-else-if="!loading" class="podium-empty-box">
            <p>暂无排行数据</p>
          </div>
        </div>
      </section>

      <!-- 下半部分：排行榜 4 - 10 列表区域 -->
      <a-spin :spinning="loading">
        <section class="ranking-board-section">
          <div class="ranking-board-card">
            <!-- 列表表头 -->
            <div class="board-table-header">
              <div class="col-head-rank">
                <svg class="bar-chart-icon" viewBox="0 0 24 24" fill="none">
                  <path d="M4 19h16v2H4v-2zM7 10h3v7H7v-7zm5-6h3v13h-3V4zm5 3h3v10h-3V7z" fill="currentColor"/>
                </svg>
                <span>排行榜 4 - 10</span>
              </div>
              <div class="col-head-user">用户</div>
              <div class="col-head-cost">{{ rankingRangeLabel }}消费（USD）</div>
            </div>

            <!-- 列表行 (4 - 10) -->
            <div class="board-table-body" v-if="ranking.length > 3">
              <div
                v-for="(item, index) in ranking.slice(3, 10)"
                :key="item.user_id || index"
                class="board-row-item"
                @click="showDetail(item, index + 4)"
              >
                <!-- 序号 04, 05... -->
                <div class="row-rank-num">
                  {{ String(index + 4).padStart(2, '0') }}
                </div>

                <!-- 头像 -->
                <div class="row-avatar">
                  <a-avatar v-if="item.avatar" :src="item.avatar" :size="42" />
                  <div v-else class="letter-avatar-circle">
                    {{ (item.username || '?').charAt(0).toUpperCase() }}
                  </div>
                </div>

                <!-- 用户基本信息 -->
                <div class="row-user-details">
                  <div class="user-line-top">
                    <span class="user-name-text" :title="item.username">{{ item.username }}</span>
                    <span class="role-pill" :class="item.role === 'admin' ? 'role-admin' : 'role-user'">
                      {{ item.role === 'admin' ? '管理员' : '用户' }}
                    </span>
                  </div>
                  <div class="user-line-sub">
                    请求次数: {{ formatNumber(item.request_count) }}
                  </div>
                </div>

                <!-- 消费金额 -->
                <div class="row-cost-val">
                  ${{ formatCurrency(item.total_cost) }}
                </div>

                <!-- 箭头 -->
                <div class="row-arrow">
                  <a-icon type="right" />
                </div>
              </div>
            </div>

            <!-- 若无 4 - 10 名数据 -->
            <div v-else-if="!loading" class="board-no-data">
              <a-empty description="暂无 4 - 10 名排行数据" />
            </div>

            <!-- 底部激励横幅 Banner -->
            <div class="cheer-banner">
              <div class="banner-left">
                <div class="trophy-circle">
                  <svg class="trophy-svg" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M19 5h-2V3H7v2H5c-1.1 0-2 .9-2 2v1c0 2.55 1.92 4.63 4.39 4.94A5.01 5.01 0 0 0 11 15.9V19H7v2h10v-2h-4v-3.1c1.87-.41 3.32-1.89 3.61-3.96C19.08 11.63 21 9.55 21 8V7c0-1.1-.9-2-2-2zM5 8V7h2v3.82C5.84 10.4 5 9.3 5 8zm14 0c0 1.3-.84 2.4-2 2.82V7h2v1z"/>
                  </svg>
                </div>
                <div class="banner-info">
                  <div class="banner-title">感谢每一位用户的支持</div>
                  <div class="banner-subtitle">你的每一次消费，都在让社区变得更好</div>
                </div>
              </div>
              <div class="banner-right">
                <button type="button" class="cheer-action-btn" @click="handleCheerAction">
                  <span class="btn-up-icon">↗</span>
                  <span class="btn-text">继续加油，冲击榜单！</span>
                  <a-icon type="right" class="btn-right-icon" />
                </button>
              </div>
            </div>
          </div>
        </section>
      </a-spin>

      <!-- 用户详情弹窗 Modal -->
      <a-modal
        v-model="detailModalVisible"
        :title="null"
        :footer="null"
        width="440px"
        centered
        :maskClosable="true"
        wrapClassName="ranking-detail-modal"
      >
        <div class="detail-modal-body" v-if="selectedUser">
          <div class="detail-top-card">
            <div class="detail-rank-badge" :class="'rank-badge-' + selectedUserRank">
              第 {{ selectedUserRank }} 名
            </div>
            <div class="detail-avatar-box">
              <a-avatar v-if="selectedUser.avatar" :src="selectedUser.avatar" :size="64" />
              <div v-else class="detail-letter-avatar">
                {{ (selectedUser.username || '?').charAt(0).toUpperCase() }}
              </div>
            </div>
            <div class="detail-username">{{ selectedUser.username }}</div>
            <div class="detail-role-tag">
              <span :class="selectedUser.role === 'admin' ? 'tag-admin' : 'tag-user'">
                {{ selectedUser.role === 'admin' ? '平台管理员' : '普通用户' }}
              </span>
            </div>
          </div>

          <div class="detail-metrics-grid">
            <div class="metric-card">
              <div class="metric-label">{{ rankingRangeLabel }}消费金额</div>
              <div class="metric-value highlight">${{ formatCurrency(selectedUser.total_cost) }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">调用请求次数</div>
              <div class="metric-value">{{ formatNumber(selectedUser.request_count) }} 次</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">消耗 Tokens</div>
              <div class="metric-value">{{ formatNumber(selectedUser.total_tokens) }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">最近调用时间</div>
              <div class="metric-value small">{{ formatTime(selectedUser.last_used_at) }}</div>
            </div>
          </div>

          <!-- 管理员快捷操作 -->
          <div class="detail-admin-actions" v-if="isAdminRoute">
            <a-button type="primary" block @click="navigateToUserLogs">
              查看该用户调用日志
            </a-button>
          </div>
        </div>
      </a-modal>
    </div>
  </div>
</template>

<script>
import { getTokenRanking } from '@/api/user'

export default {
  name: 'UsageRanking',
  data() {
    return {
      loading: false,
      days: 1,
      ranking: [],
      rankingRequestSeq: 0,
      refreshTimer: null,
      detailModalVisible: false,
      selectedUser: null,
      selectedUserRank: 1
    }
  },
  computed: {
    isAdminRoute() {
      return this.$route && this.$route.path && this.$route.path.startsWith('/admin')
    },
    rankingRangeLabel() {
      const labels = {
        1: '今日',
        7: '近 7 天',
        30: '近 30 天'
      }
      return labels[this.days] || `近 ${this.days} 天`
    },
    rankingTitle() {
      return `${this.rankingRangeLabel}排行榜`
    }
  },
  mounted() {
    this.fetchRanking()
    // 每 60 秒静默更新一次排行榜数据
    this.refreshTimer = setInterval(() => {
      this.fetchRanking(false)
    }, 60000)
  },
  beforeDestroy() {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer)
      this.refreshTimer = null
    }
  },
  methods: {
    formatNumber(value) {
      return Number(value || 0).toLocaleString()
    },
    formatCurrency(value) {
      const amount = Number(value || 0)
      if (!Number.isFinite(amount)) return '0.00'
      if (amount >= 100) return amount.toFixed(2)
      if (amount >= 0.001) return amount.toFixed(3)
      return amount.toFixed(4)
    },
    formatTime(timeStr) {
      if (!timeStr) return '无记录'
      try {
        const date = new Date(timeStr)
        if (isNaN(date.getTime())) return timeStr
        const month = String(date.getMonth() + 1).padStart(2, '0')
        const day = String(date.getDate()).padStart(2, '0')
        const hours = String(date.getHours()).padStart(2, '0')
        const minutes = String(date.getMinutes()).padStart(2, '0')
        return `${month}-${day} ${hours}:${minutes}`
      } catch (e) {
        return timeStr
      }
    },
    handleTimeChange(val) {
      if (this.days === val) return
      this.days = val
      this.fetchRanking(true)
    },
    handleManualRefresh() {
      this.fetchRanking(true)
      this.$message.success('已刷新实时排行数据')
    },
    showDetail(user, rank) {
      this.selectedUser = user
      this.selectedUserRank = rank
      this.detailModalVisible = true
    },
    navigateToUserLogs() {
      this.detailModalVisible = false
      if (this.selectedUser && this.selectedUser.user_id) {
        this.$router.push({
          path: '/admin/logs',
          query: { userId: this.selectedUser.user_id }
        }).catch(() => {})
      }
    },
    handleCheerAction() {
      if (this.isAdminRoute) {
        this.$message.info('当前为管理员视角，实时排行榜已就绪')
        this.fetchRanking(true)
      } else {
        // 普通用户跳转至充值中心提升消费
        this.$router.push('/user/recharge').catch(() => {
          this.$router.push('/user/redemption').catch(() => {})
        })
      }
    },
    async fetchRanking(showSpinner = true) {
      const requestSeq = ++this.rankingRequestSeq
      const requestedDays = this.days
      if (showSpinner) {
        this.loading = true
      }
      try {
        const res = await getTokenRanking({ days: requestedDays, limit: 10 })
        if (requestSeq !== this.rankingRequestSeq || requestedDays !== this.days) return
        const data = res.data || {}
        this.ranking = data.ranking || []
      } catch (err) {
        if (requestSeq === this.rankingRequestSeq && showSpinner) {
          this.$message.error('无法加载使用排行')
        }
      } finally {
        if (requestSeq === this.rankingRequestSeq) {
          this.loading = false
        }
      }
    }
  }
}
</script>

<style lang="less" scoped>
.usage-ranking-page {
  min-height: calc(100vh - 64px);
  margin: -24px -24px -24px -24px;
  background: #f4f6fc;
  padding: 0 0 60px 0;
  overflow-x: hidden;

  .page-container {
    max-width: 780px;
    margin: 0 auto;
    padding: 0 16px;
  }

  /* 顶部 Hero 区域 */
  .ranking-hero-section {
    position: relative;
    border-radius: 0 0 36px 36px;
    background: linear-gradient(155deg, #4f78fe 0%, #635bf7 40%, #8956ee 75%, #9d4ded 100%);
    color: #fff;
    padding: 36px 28px 64px 28px;
    overflow: hidden;
    box-shadow: 0 16px 40px rgba(99, 91, 247, 0.22);

    .hero-bg-decorations {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      pointer-events: none;
      overflow: hidden;

      .glow-orb {
        position: absolute;
        border-radius: 50%;
        filter: blur(50px);
        opacity: 0.35;

        &-1 {
          top: -30px;
          left: -40px;
          width: 240px;
          height: 240px;
          background: rgba(255, 255, 255, 0.4);
        }

        &-2 {
          top: 60px;
          right: -30px;
          width: 260px;
          height: 260px;
          background: rgba(192, 132, 252, 0.5);
        }
      }

      .crystal-crown-container {
        position: absolute;
        top: 20px;
        right: 14px;
        width: 190px;
        display: flex;
        flex-direction: column;
        align-items: center;
        opacity: 0.88;

        .crystal-crown-svg {
          width: 100%;
          height: auto;
          filter: drop-shadow(0 8px 20px rgba(168, 85, 247, 0.35));
        }

        .crystal-slogan {
          font-size: 8px;
          font-weight: 700;
          color: rgba(255, 255, 255, 0.6);
          letter-spacing: 2px;
          text-align: center;
          margin-top: -6px;
          width: 120px;
          line-height: 1.3;
          text-transform: uppercase;
        }
      }
    }

    .hero-content {
      position: relative;
      z-index: 2;
    }

    /* 头部排版 */
    .hero-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 24px;
    }

    .header-left {
      .mini-brand {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        font-weight: 600;
        color: rgba(255, 255, 255, 0.95);
        margin-bottom: 8px;
        letter-spacing: 0.5px;

        .brand-crown-icon {
          width: 16px;
          height: 16px;
          fill: #ffffff;
        }
      }

      .hero-title {
        font-size: 32px;
        font-weight: 800;
        color: #ffffff;
        margin: 0;
        line-height: 1.15;
        letter-spacing: -0.5px;

        .top10-highlight {
          display: block;
          font-size: 36px;
          font-weight: 900;
          letter-spacing: -0.5px;
          margin-top: 2px;
        }
      }

      .hero-subtitle {
        font-size: 13px;
        color: rgba(255, 255, 255, 0.78);
        margin: 8px 0 12px 0;
      }

      /* 实时呼吸状态胶囊 */
      .live-status-capsule {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        background: rgba(255, 255, 255, 0.16);
        backdrop-filter: blur(8px);
        padding: 4px 12px;
        border-radius: 20px;
        cursor: pointer;
        transition: all 0.25s ease;
        border: 1px solid rgba(255, 255, 255, 0.2);

        &:hover {
          background: rgba(255, 255, 255, 0.26);
          transform: translateY(-1px);
        }

        .live-dot {
          width: 7px;
          height: 7px;
          background: #10b981;
          border-radius: 50%;
          box-shadow: 0 0 8px #10b981;
          animation: pulseGlow 1.8s infinite;
        }

        .live-text {
          font-size: 11px;
          color: rgba(255, 255, 255, 0.95);
          font-weight: 500;
        }

        .refresh-indicator {
          font-size: 11px;
          color: rgba(255, 255, 255, 0.75);
        }
      }
    }

    /* 右侧胶囊时间切换 */
    .header-right {
      .glass-pill-switcher {
        display: inline-flex;
        background: rgba(255, 255, 255, 0.18);
        backdrop-filter: blur(12px);
        padding: 3px;
        border-radius: 24px;
        border: 1px solid rgba(255, 255, 255, 0.22);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);

        .pill-switcher-item {
          border: none;
          background: transparent;
          color: rgba(255, 255, 255, 0.9);
          font-size: 13px;
          font-weight: 600;
          padding: 6px 14px;
          border-radius: 20px;
          cursor: pointer;
          transition: all 0.25s ease;
          outline: none;

          &:hover:not(.active) {
            color: #ffffff;
            background: rgba(255, 255, 255, 0.12);
          }

          &.active {
            background: #ffffff;
            color: #5551f3;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
          }
        }
      }
    }

    /* 领奖台区域 (Podium) */
    .podium-container {
      display: flex;
      justify-content: center;
      align-items: flex-end;
      gap: 16px;
      margin-top: 36px;
      padding: 0 4px;
    }

    .podium-empty-box {
      text-align: center;
      padding: 40px 0;
      color: rgba(255, 255, 255, 0.8);
      font-size: 14px;
    }

    .podium-card-wrapper {
      display: flex;
      flex-direction: column;
      align-items: center;
      cursor: pointer;
      transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);

      &:hover {
        transform: translateY(-6px);
      }

      &.is-placeholder {
        cursor: default;
        opacity: 0.8;
        &:hover {
          transform: none;
        }
      }

      &.rank-2 {
        order: 1;
        flex: 1;
        max-width: 220px;
      }

      &.rank-1 {
        order: 2;
        flex: 1.18;
        max-width: 250px;
        z-index: 3;
        transform: translateY(-16px);

        &:hover {
          transform: translateY(-22px);
        }
      }

      &.rank-3 {
        order: 3;
        flex: 1;
        max-width: 220px;
      }

      /* 皇冠盒子 */
      .crown-box {
        margin-bottom: -18px;
        z-index: 4;
        filter: drop-shadow(0 4px 10px rgba(0, 0, 0, 0.12));

        .crown-svg {
          width: 56px;
          height: auto;
          display: block;
        }

        &.gold-crown-box {
          margin-bottom: -22px;
          .crown-svg {
            width: 68px;
            filter: drop-shadow(0 6px 14px rgba(245, 158, 11, 0.4));
          }
        }
      }

      /* 玻璃拟态卡片本体 */
      .podium-glass-card {
        width: 100%;
        background: rgba(255, 255, 255, 0.92);
        backdrop-filter: blur(16px);
        border-radius: 22px;
        padding: 30px 10px 16px 10px;
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        box-shadow: 0 14px 30px rgba(85, 81, 243, 0.16), 0 2px 6px rgba(0, 0, 0, 0.04);
        border: 1.5px solid rgba(255, 255, 255, 0.95);
        position: relative;

        &.gold-glass {
          padding-top: 36px;
          padding-bottom: 20px;
          border-radius: 24px;
          background: rgba(255, 255, 255, 0.96);
          box-shadow: 0 18px 40px rgba(85, 81, 243, 0.22), 0 0 25px rgba(251, 191, 36, 0.35);
          border: 2px solid rgba(255, 255, 255, 1);

          &::after {
            content: '';
            position: absolute;
            bottom: -10px;
            left: 10%;
            width: 80%;
            height: 14px;
            background: radial-gradient(ellipse at center, rgba(255, 255, 255, 0.6) 0%, transparent 75%);
            pointer-events: none;
          }
        }

        .avatar-holder {
          width: 58px;
          height: 58px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          margin-bottom: 8px;
          border: 3px solid #ffffff;
          box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);

          &.silver-holder {
            background: linear-gradient(135deg, #a5b4fc 0%, #818cf8 100%);
            box-shadow: 0 6px 16px rgba(129, 140, 248, 0.35);
          }

          &.gold-holder {
            width: 72px;
            height: 72px;
            background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%);
            box-shadow: 0 8px 22px rgba(217, 119, 6, 0.4);
            border-width: 3.5px;
          }

          &.bronze-holder {
            background: linear-gradient(135deg, #fdba74 0%, #ea580c 100%);
            box-shadow: 0 6px 16px rgba(234, 88, 12, 0.35);
          }

          .inner-avatar-letter {
            font-size: 24px;
            font-weight: 800;
            color: #ffffff;
            line-height: 1;

            &.gold-letter {
              font-size: 32px;
            }
          }
        }

        .user-display-name {
          font-size: 14px;
          font-weight: 700;
          color: #1e293b;
          max-width: 100%;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          margin-bottom: 6px;
          line-height: 1.3;

          &.gold-name {
            font-size: 15px;
            font-weight: 800;
          }
        }

        /* 消费金额胶囊 */
        .cost-capsule {
          border-radius: 14px;
          padding: 3px 10px;
          font-size: 15px;
          font-weight: 800;
          letter-spacing: -0.2px;
          margin-bottom: 4px;
          white-space: nowrap;

          &.silver-cost {
            background: #eef2ff;
            color: #4338ca;
          }

          &.gold-cost {
            background: #fef3c7;
            color: #b45309;
            font-size: 18px;
            padding: 4px 14px;
          }

          &.bronze-cost {
            background: #ffedd5;
            color: #c2410c;
          }
        }

        .cost-label {
          font-size: 11px;
          color: #94a3b8;
          font-weight: 500;
          transform: scale(0.95);
        }
      }
    }
  }

  /* 下半部分：4-10名列表卡片 */
  .ranking-board-section {
    position: relative;
    z-index: 5;
    margin-top: -28px;
    padding: 0 8px;
  }

  .ranking-board-card {
    background: #ffffff;
    border-radius: 28px;
    box-shadow: 0 10px 35px rgba(60, 50, 150, 0.05), 0 2px 10px rgba(0, 0, 0, 0.02);
    padding: 24px 24px 20px 24px;
    border: 1px solid rgba(226, 232, 240, 0.7);

    /* 列表表头 */
    .board-table-header {
      display: flex;
      align-items: center;
      padding: 0 8px 16px 8px;
      border-bottom: 1px solid #f1f5f9;

      .col-head-rank {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 15px;
        font-weight: 800;
        color: #1e293b;
        flex: 1.1;

        .bar-chart-icon {
          width: 18px;
          height: 18px;
          color: #5551f3;
        }
      }

      .col-head-user {
        flex: 1.5;
        font-size: 12px;
        color: #94a3b8;
        font-weight: 500;
        padding-left: 12px;
      }

      .col-head-cost {
        flex: 1.4;
        text-align: right;
        font-size: 12px;
        color: #94a3b8;
        font-weight: 500;
        padding-right: 18px;
      }
    }

    /* 列表项 */
    .board-table-body {
      display: flex;
      flex-direction: column;
    }

    .board-row-item {
      display: flex;
      align-items: center;
      padding: 14px 8px;
      border-bottom: 1px solid #f8fafc;
      cursor: pointer;
      transition: all 0.2s ease;
      border-radius: 14px;

      &:hover {
        background: #f8faff;
        transform: translateX(2px);

        .row-arrow {
          color: #5551f3;
          transform: translateX(2px);
        }
      }

      .row-rank-num {
        width: 32px;
        font-size: 16px;
        font-weight: 800;
        color: #94a3b8;
        font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
      }

      .row-avatar {
        width: 44px;
        display: flex;
        align-items: center;

        .letter-avatar-circle {
          width: 38px;
          height: 38px;
          border-radius: 50%;
          background: #e2e8f0;
          color: #64748b;
          font-weight: 700;
          font-size: 15px;
          display: flex;
          align-items: center;
          justify-content: center;
        }
      }

      .row-user-details {
        flex: 1;
        padding: 0 12px;
        min-width: 0;

        .user-line-top {
          display: flex;
          align-items: center;
          gap: 6px;

          .user-name-text {
            font-size: 15px;
            font-weight: 700;
            color: #0f172a;
            max-width: 160px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          .role-pill {
            font-size: 11px;
            font-weight: 600;
            padding: 1px 6px;
            border-radius: 4px;
            line-height: 1.4;

            &.role-user {
              background: #e0f2fe;
              color: #0284c7;
            }

            &.role-admin {
              background: #f3e8ff;
              color: #9333ea;
            }
          }
        }

        .user-line-sub {
          font-size: 12px;
          color: #94a3b8;
          margin-top: 2px;
        }
      }

      .row-cost-val {
        font-size: 16px;
        font-weight: 800;
        color: #0f172a;
        font-family: 'SF Pro Text', -apple-system, BlinkMacSystemFont, sans-serif;
        text-align: right;
        padding-right: 12px;
      }

      .row-arrow {
        font-size: 13px;
        color: #cbd5e1;
        transition: all 0.2s ease;
      }
    }

    .board-no-data {
      padding: 40px 0;
      text-align: center;
    }

    /* 底部激励 Banner */
    .cheer-banner {
      margin-top: 24px;
      background: linear-gradient(135deg, #f8f9ff 0%, #f1f3fe 100%);
      border: 1px solid #e2e8f0;
      border-radius: 18px;
      padding: 16px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;

      .banner-left {
        display: flex;
        align-items: center;
        gap: 12px;

        .trophy-circle {
          width: 44px;
          height: 44px;
          border-radius: 50%;
          background: #5551f3;
          color: #ffffff;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          box-shadow: 0 4px 12px rgba(85, 81, 243, 0.3);

          .trophy-svg {
            width: 22px;
            height: 22px;
          }
        }

        .banner-info {
          .banner-title {
            font-size: 14px;
            font-weight: 800;
            color: #1e293b;
          }

          .banner-subtitle {
            font-size: 12px;
            color: #64748b;
            margin-top: 2px;
          }
        }
      }

      .banner-right {
        flex-shrink: 0;

        .cheer-action-btn {
          border: none;
          background: #ffffff;
          color: #5551f3;
          border: 1px solid #d5d3f8;
          border-radius: 20px;
          padding: 8px 16px;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          font-size: 13px;
          font-weight: 700;
          cursor: pointer;
          transition: all 0.25s ease;
          box-shadow: 0 2px 8px rgba(85, 81, 243, 0.08);

          &:hover {
            background: #5551f3;
            color: #ffffff;
            border-color: #5551f3;
            transform: translateY(-1px);
            box-shadow: 0 4px 14px rgba(85, 81, 243, 0.25);
          }

          .btn-up-icon {
            font-size: 14px;
            font-weight: 800;
          }

          .btn-right-icon {
            font-size: 11px;
          }
        }
      }
    }
  }

  /* 呼吸动画 */
  @keyframes pulseGlow {
    0% {
      transform: scale(0.95);
      box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
    }
    70% {
      transform: scale(1.1);
      box-shadow: 0 0 0 6px rgba(16, 185, 129, 0);
    }
    100% {
      transform: scale(0.95);
      box-shadow: 0 0 0 0 rgba(16, 185, 129, 0);
    }
  }

  /* 移动端与小屏幕自适应 */
  @media (max-width: 640px) {
    .ranking-hero-section {
      padding: 28px 16px 56px 16px;

      .hero-header {
        flex-direction: column;
        gap: 16px;
      }

      .hero-bg-decorations .crystal-crown-container {
        width: 140px;
        top: 10px;
        right: 0;
        opacity: 0.65;
      }

      .podium-container {
        gap: 6px;

        .podium-card-wrapper {
          .crown-box .crown-svg { width: 44px; }
          .crown-box.gold-crown-box .crown-svg { width: 54px; }

          .podium-glass-card {
            padding: 22px 4px 12px 4px;
            border-radius: 16px;

            .avatar-holder {
              width: 48px;
              height: 48px;
              .inner-avatar-letter { font-size: 18px; }
              &.gold-holder {
                width: 58px;
                height: 58px;
                .inner-avatar-letter.gold-letter { font-size: 24px; }
              }
            }

            .user-display-name {
              font-size: 12px;
              &.gold-name { font-size: 13px; }
            }

            .cost-capsule {
              font-size: 13px;
              padding: 2px 6px;
              &.gold-cost { font-size: 15px; padding: 3px 8px; }
            }

            .cost-label {
              font-size: 10px;
            }
          }
        }
      }
    }

    .ranking-board-card {
      padding: 18px 14px 16px 14px;

      .cheer-banner {
        flex-direction: column;
        align-items: flex-start;
        gap: 12px;

        .banner-right {
          width: 100%;
          .cheer-action-btn {
            width: 100%;
            justify-content: center;
          }
        }
      }
    }
  }
}
</style>

<style lang="less">
/* 全局弹窗样式覆盖 */
.ranking-detail-modal {
  .ant-modal-content {
    border-radius: 24px;
    overflow: hidden;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
  }

  .ant-modal-close {
    top: 14px;
    right: 14px;
  }

  .detail-modal-body {
    padding: 12px 6px;

    .detail-top-card {
      text-align: center;
      padding-bottom: 20px;
      border-bottom: 1px solid #f1f5f9;
      position: relative;

      .detail-rank-badge {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 800;
        margin-bottom: 12px;

        &.rank-badge-1 {
          background: #fef3c7;
          color: #b45309;
        }
        &.rank-badge-2 {
          background: #eef2ff;
          color: #4338ca;
        }
        &.rank-badge-3 {
          background: #ffedd5;
          color: #c2410c;
        }
        &:not(.rank-badge-1):not(.rank-badge-2):not(.rank-badge-3) {
          background: #f1f5f9;
          color: #64748b;
        }
      }

      .detail-avatar-box {
        display: flex;
        justify-content: center;
        margin-bottom: 10px;

        .detail-letter-avatar {
          width: 64px;
          height: 64px;
          border-radius: 50%;
          background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
          color: #fff;
          font-size: 26px;
          font-weight: 800;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 8px 20px rgba(99, 102, 241, 0.25);
        }
      }

      .detail-username {
        font-size: 18px;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 6px;
      }

      .detail-role-tag {
        span {
          font-size: 11px;
          font-weight: 600;
          padding: 2px 8px;
          border-radius: 4px;

          &.tag-user {
            background: #e0f2fe;
            color: #0284c7;
          }
          &.tag-admin {
            background: #f3e8ff;
            color: #9333ea;
          }
        }
      }
    }

    .detail-metrics-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      padding: 20px 0;

      .metric-card {
        background: #f8fafc;
        border-radius: 14px;
        padding: 12px;
        text-align: center;
        border: 1px solid #f1f5f9;

        .metric-label {
          font-size: 12px;
          color: #64748b;
          margin-bottom: 4px;
        }

        .metric-value {
          font-size: 16px;
          font-weight: 800;
          color: #0f172a;

          &.highlight {
            color: #5551f3;
            font-size: 18px;
          }

          &.small {
            font-size: 13px;
            font-weight: 600;
            color: #475569;
          }
        }
      }
    }

    .detail-admin-actions {
      margin-top: 8px;
    }
  }
}
</style>
