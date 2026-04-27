<template>
  <div class="system-manage-page">
    <!-- Header Section -->
    <div class="page-header animate__animated animate__fadeIn">
      <div class="header-left">
        <div class="header-icon-box">
          <a-icon type="setting" />
        </div>
        <div>
          <h1 class="page-title">系统配置</h1>
          <p class="page-subtitle">自定义您的代理站点名称、公告及客服联系方式</p>
        </div>
      </div>
      <div class="header-right">
        <a-button type="primary" class="save-btn-top" :loading="saving" @click="save">
          <a-icon type="save" /> 保存所有更改
        </a-button>
      </div>
    </div>

    <div class="content-container">
      <a-form-model :model="form" layout="vertical">
        <a-row :gutter="24">
          <!-- 左侧：基础信息 -->
          <a-col :xs="24" :lg="14">
            <a-card class="glass-card section-card" :bordered="false">
              <div slot="title" class="card-title">
                <a-icon type="info-circle" /> 站点基础信息
              </div>
              
              <a-row :gutter="16">
                <a-col :span="12">
                  <a-form-model-item label="站点名称">
                    <a-input v-model="form.site_title" placeholder="例如：极光 AI 代理" size="large">
                      <a-icon slot="prefix" type="global" style="color: rgba(0,0,0,.25)" />
                    </a-input>
                  </a-form-model-item>
                </a-col>
                <a-col :span="12">
                  <a-form-model-item label="站点副标题">
                    <a-input v-model="form.site_subtitle" placeholder="例如：最稳定的模型中转站" size="large" />
                  </a-form-model-item>
                </a-col>
              </a-row>

              <a-form-model-item label="统一 API 地址">
                <a-input :value="form.quickstart_api_base_url" disabled size="large" class="disabled-input">
                  <a-icon slot="prefix" type="link" style="color: rgba(0,0,0,.25)" />
                  <a-tooltip slot="suffix" title="当前代理端固定使用共享 API 地址，暂不支持修改">
                    <a-icon type="info-circle" style="color: rgba(0,0,0,.45)" />
                  </a-tooltip>
                </a-input>
                <div class="field-tip">该地址用于下级用户接入时配置 API Base URL</div>
              </a-form-model-item>

              <div class="divider"></div>

              <div class="switch-item">
                <div class="switch-info">
                  <div class="switch-title">开放注册</div>
                  <div class="switch-desc">开启后，访客可以直接在您的站点注册账号</div>
                </div>
                <a-switch v-model="allowRegisterBool" size="large" />
              </div>
            </a-card>

            <a-card class="glass-card section-card announcement-card" :bordered="false">
              <div slot="title" class="card-title">
                <a-icon type="notification" /> 平台公告设置
              </div>
              <a-form-model-item label="公告标题">
                <a-input v-model="form.announcement_title" placeholder="请输入醒目的公告标题" size="large" />
              </a-form-model-item>
              <a-form-model-item label="公告内容">
                <a-textarea 
                  v-model="form.announcement_content" 
                  placeholder="支持 HTML 或纯文本描述..." 
                  :rows="6" 
                  class="custom-textarea"
                />
              </a-form-model-item>
            </a-card>
          </a-col>

          <!-- 右侧：客服与支持 -->
          <a-col :xs="24" :lg="10">
            <a-card class="glass-card section-card support-card" :bordered="false">
              <div slot="title" class="card-title">
                <a-icon type="customer-service" /> 客服联系方式
              </div>
              <p class="section-desc">配置后将展示在前台帮助中心或页脚，方便用户联系您。</p>
              
              <a-form-model-item label="微信联系人">
                <a-input v-model="form.support_wechat" placeholder="微信号或昵称" size="large">
                  <a-icon slot="prefix" type="wechat" style="color: #07c160" />
                </a-input>
              </a-form-model-item>

              <a-form-model-item label="QQ 联系人">
                <a-input v-model="form.support_qq" placeholder="QQ 号码" size="large">
                  <a-icon slot="prefix" type="qq" style="color: #12b7f5" />
                </a-input>
              </a-form-model-item>

              <div class="support-preview">
                <div class="preview-tag">预览效果</div>
                <div class="preview-content">
                  <div v-if="form.support_wechat" class="p-item"><a-icon type="wechat" /> {{ form.support_wechat }}</div>
                  <div v-if="form.support_qq" class="p-item"><a-icon type="qq" /> {{ form.support_qq }}</div>
                  <div v-if="!form.support_wechat && !form.support_qq" class="p-empty">尚未配置联系方式</div>
                </div>
              </div>
            </a-card>

            <div class="info-tip-card">
              <a-icon type="bulb" />
              <div class="tip-content">
                <strong>温馨提示：</strong>
                所有的修改将在保存后立即生效。如果修改了站点名称，建议同步更新公告内容以保持品牌一致性。
              </div>
            </div>
          </a-col>
        </a-row>
      </a-form-model>
    </div>

    <!-- Pinned Save Action -->
    <div class="footer-actions">
      <div class="footer-inner">
        <span class="status-text" v-if="!saving">所有配置已就绪</span>
        <span class="status-text loading" v-else><a-icon type="loading" /> 正在同步至云端...</span>
        <a-button type="primary" size="large" :loading="saving" @click="save" class="final-save-btn">
          确认并保存配置
        </a-button>
      </div>
    </div>
  </div>
</template>

<script>
import { getAgentSiteConfig, updateAgentSiteConfig } from '@/api/agent'

export default {
  name: 'AgentSystemManage',
  data() {
    return {
      saving: false,
      form: {
        site_title: '',
        site_subtitle: '',
        quickstart_api_base_url: '',
        announcement_title: '',
        announcement_content: '',
        support_wechat: '',
        support_qq: '',
        allow_self_register: 1
      }
    }
  },
  computed: {
    allowRegisterBool: {
      get() {
        return this.form.allow_self_register === 1
      },
      set(val) {
        this.form.allow_self_register = val ? 1 : 0
      }
    }
  },
  mounted() {
    this.fetchConfig()
  },
  methods: {
    async fetchConfig() {
      const res = await getAgentSiteConfig()
      const data = res.data || {}
      this.form = {
        site_title: data.site_name || '',
        site_subtitle: data.site_subtitle || '',
        quickstart_api_base_url: data.quickstart_api_base_url || '',
        announcement_title: data.announcement_title || '',
        announcement_content: data.announcement_content || '',
        support_wechat: data.support_wechat || '',
        support_qq: data.support_qq || '',
        allow_self_register: data.allow_register ? 1 : 0
      }
    },
    async save() {
      this.saving = true
      try {
        const payload = {
          site_title: this.form.site_title,
          site_subtitle: this.form.site_subtitle,
          announcement_title: this.form.announcement_title,
          announcement_content: this.form.announcement_content,
          support_wechat: this.form.support_wechat,
          support_qq: this.form.support_qq,
          allow_self_register: this.form.allow_self_register
        }
        await updateAgentSiteConfig(payload)
        this.$message.success('系统配置已更新')
      } finally {
        this.saving = false
      }
    }
  }
}
</script>

<style lang="less" scoped>
.system-manage-page {
  padding-bottom: 100px;
  min-height: 100%;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding: 32px 40px;
    background: radial-gradient(circle at 10% 20%, rgba(255, 255, 255, 0.15), transparent 40%),
                linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 28px;
    color: #fff;
    box-shadow: 0 20px 50px rgba(102, 126, 234, 0.2);

    .header-left {
      display: flex;
      align-items: center;
      gap: 20px;
    }

    .header-icon-box {
      width: 60px;
      height: 60px;
      background: rgba(255, 255, 255, 0.2);
      backdrop-filter: blur(10px);
      border-radius: 18px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 30px;
      border: 1px solid rgba(255, 255, 255, 0.3);
    }

    .page-title {
      color: #fff;
      font-size: 28px;
      font-weight: 900;
      margin: 0;
      letter-spacing: -0.5px;
    }

    .page-subtitle {
      margin: 4px 0 0;
      color: rgba(255, 255, 255, 0.85);
      font-size: 14px;
    }

    .save-btn-top {
      height: 46px;
      padding: 0 24px;
      border-radius: 14px;
      background: #fff;
      border: none;
      color: #667eea;
      font-weight: 800;
      box-shadow: 0 10px 20px rgba(0,0,0,0.1);
      &:hover {
        transform: translateY(-2px);
        background: #f8fafc;
        color: #764ba2;
      }
    }
  }

  .content-container {
    max-width: 1200px;
  }

  .glass-card {
    background: rgba(255, 255, 255, 0.7);
    backdrop-filter: blur(20px);
    border-radius: 24px;
    border: 1px solid rgba(255, 255, 255, 0.6);
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.04);
    margin-bottom: 24px;

    /deep/ .ant-card-head {
      border-bottom: 1px solid rgba(102, 126, 234, 0.05);
      padding: 0 28px;
      height: 64px;
      display: flex;
      align-items: center;
      .ant-card-head-title {
        font-size: 18px;
        font-weight: 800;
        color: #1e293b;
        display: flex;
        align-items: center;
        gap: 10px;
        i { color: #667eea; font-size: 20px; }
      }
    }

    /deep/ .ant-card-body {
      padding: 28px;
    }
  }

  /deep/ .ant-form-item-label > label {
    font-weight: 700;
    color: #64748b;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .custom-textarea {
    border-radius: 16px;
    padding: 12px 16px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    &:focus {
      background: #fff;
      border-color: #667eea;
      box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.1);
    }
  }

  .disabled-input {
    background: #f1f5f9;
    border-color: #e2e8f0;
    color: #64748b;
  }

  .field-tip {
    margin-top: 8px;
    color: #94a3b8;
    font-size: 12px;
    display: flex;
    align-items: center;
    gap: 6px;
    &::before { content: '•'; color: #667eea; font-weight: bold; }
  }

  .divider {
    height: 1px;
    background: rgba(102, 126, 234, 0.08);
    margin: 24px 0;
  }

  .switch-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    background: rgba(102, 126, 234, 0.04);
    border-radius: 18px;
    border: 1px solid rgba(102, 126, 234, 0.05);

    .switch-title {
      font-weight: 800;
      color: #1e293b;
      font-size: 15px;
    }
    .switch-desc {
      color: #94a3b8;
      font-size: 12px;
      margin-top: 2px;
    }
  }

  .section-desc {
    color: #94a3b8;
    font-size: 13px;
    margin-bottom: 24px;
  }

  .support-preview {
    margin-top: 24px;
    padding: 20px;
    background: #f8fafc;
    border: 1px dashed #cbd5e0;
    border-radius: 20px;
    position: relative;

    .preview-tag {
      position: absolute;
      top: -10px;
      left: 20px;
      background: #64748b;
      color: #fff;
      font-size: 10px;
      padding: 2px 10px;
      border-radius: 10px;
      font-weight: 700;
    }

    .preview-content {
      .p-item {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 8px;
        color: #475569;
        font-weight: 600;
        &:last-child { margin-bottom: 0; }
        i { font-size: 16px; }
      }
      .p-empty {
        color: #cbd5e0;
        font-style: italic;
        text-align: center;
        font-size: 13px;
      }
    }
  }

  .info-tip-card {
    display: flex;
    gap: 16px;
    padding: 24px;
    background: rgba(102, 126, 234, 0.08);
    border-radius: 24px;
    border: 1px solid rgba(102, 126, 234, 0.1);
    i { color: #667eea; font-size: 24px; margin-top: 2px; }
    .tip-content {
      color: #4b5563;
      font-size: 13px;
      line-height: 1.6;
      strong { color: #1e293b; display: block; margin-bottom: 4px; }
    }
  }

  .footer-actions {
    position: fixed;
    bottom: 0;
    right: 0;
    width: calc(100% - 280px); // Assuming sidebar is 280px
    padding: 20px 40px;
    background: rgba(255, 255, 255, 0.8);
    backdrop-filter: blur(20px);
    border-top: 1px solid rgba(102, 126, 234, 0.1);
    z-index: 100;

    .footer-inner {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .status-text {
      color: #94a3b8;
      font-weight: 600;
      font-size: 14px;
      &.loading { color: #667eea; }
    }

    .final-save-btn {
      height: 50px;
      padding: 0 40px;
      border-radius: 16px;
      font-weight: 800;
      font-size: 16px;
      box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border: none;
      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 15px 30px rgba(102, 126, 234, 0.4);
      }
    }
  }
}

@media (max-width: 992px) {
  .system-manage-page .footer-actions {
    width: 100%;
  }
}
</style>
