<template>
  <div class="announcement-manage-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">公告管理</h2>
        <p class="page-subtitle">编辑直营客户开屏公告，并发布面向全部用户的额外公告</p>
      </div>
      <a-button type="primary" @click="openCreateModal">
        <a-icon type="plus" />
        新建公告
      </a-button>
    </div>

    <a-row :gutter="24">
      <a-col :xs="24" :lg="10">
        <a-card class="panel-card" :bordered="false">
          <div slot="title" class="card-title">
            <a-icon type="pushpin" />
            直营固定开屏公告
          </div>
          <a-alert
            class="contact-gate-alert"
            type="info"
            show-icon
            message="联系方式展示门槛"
            description="微信和 QQ 仍在这里配置；直营用户需通过在线充值余额或购买套餐累计成功付款超过下方门槛后才会看到，未达标时用户端显示门槛提示。代理端联系方式逻辑不受影响。"
          />
          <a-form-model layout="vertical" :model="fixedForm">
            <a-form-model-item label="公告标题">
              <a-input v-model="fixedForm.announcement_title" placeholder="平台公告" />
            </a-form-model-item>
            <a-form-model-item label="公告内容">
              <a-textarea
                v-model="fixedForm.announcement_content"
                :auto-size="{ minRows: 8, maxRows: 14 }"
                placeholder="请输入用户登录后首先看到的公告内容"
              />
            </a-form-model-item>
            <a-row :gutter="12">
              <a-col :span="12">
                <a-form-model-item label="微信">
                  <a-input v-model="fixedForm.support_wechat" placeholder="微信联系方式" />
                </a-form-model-item>
              </a-col>
              <a-col :span="12">
                <a-form-model-item label="QQ">
                  <a-input v-model="fixedForm.support_qq" placeholder="QQ 联系方式" />
                </a-form-model-item>
              </a-col>
            </a-row>
            <a-form-model-item label="联系方式展示门槛（人民币）">
              <a-input-number
                v-model="fixedForm.support_contact_threshold_cny"
                :min="0"
                :step="1"
                :precision="2"
                style="width: 100%"
              />
            </a-form-model-item>
          </a-form-model>
          <a-button type="primary" block :loading="savingFixed" @click="saveFixedConfig">
            <a-icon type="save" />
            保存固定公告
          </a-button>
        </a-card>
      </a-col>

      <a-col :xs="24" :lg="14">
        <a-card class="panel-card" :bordered="false">
          <div slot="title" class="card-title">
            <a-icon type="notification" />
            额外公告
          </div>
          <div slot="extra" class="table-actions">
            <a-select v-model="filters.status" allowClear placeholder="全部状态" style="width: 130px" @change="handleFilterChange">
              <a-select-option value="draft">草稿</a-select-option>
              <a-select-option value="published">已发布</a-select-option>
              <a-select-option value="offline">已下线</a-select-option>
            </a-select>
            <a-button @click="fetchAnnouncements" :loading="loading">
              <a-icon type="reload" />
            </a-button>
          </div>

          <a-table
            :columns="columns"
            :data-source="list"
            :loading="loading"
            :pagination="pagination"
            row-key="id"
            :scroll="{ x: 900 }"
            @change="handleTableChange"
          >
            <template slot="titleCell" slot-scope="text, record">
              <div class="announcement-title">{{ record.title }}</div>
              <div class="announcement-preview">{{ record.content }}</div>
            </template>
            <template slot="status" slot-scope="text">
              <a-tag :color="statusColor(text)">{{ statusText(text) }}</a-tag>
            </template>
            <template slot="showPopup" slot-scope="text">
              <a-tag :color="text ? 'blue' : 'default'">{{ text ? '开屏弹出' : '仅公告中心' }}</a-tag>
            </template>
            <template slot="time" slot-scope="text">{{ text ? formatTime(text) : '-' }}</template>
            <template slot="action" slot-scope="text, record">
              <a-space>
                <a @click="openEditModal(record)">编辑</a>
                <a @click="toggleStatus(record)">{{ record.status === 'published' ? '下线' : '发布' }}</a>
                <a-popconfirm title="确认删除该公告？" @confirm="removeAnnouncement(record)">
                  <a class="danger-link">删除</a>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table>
        </a-card>
      </a-col>
    </a-row>

    <a-modal
      v-model="modalVisible"
      :title="editingId ? '编辑公告' : '新建公告'"
      :confirm-loading="savingAnnouncement"
      width="720px"
      @ok="submitAnnouncement"
      @cancel="modalVisible = false"
    >
      <a-form-model layout="vertical" :model="announcementForm">
        <a-form-model-item label="标题">
          <a-input v-model="announcementForm.title" placeholder="请输入公告标题" />
        </a-form-model-item>
        <a-form-model-item label="内容">
          <a-textarea
            v-model="announcementForm.content"
            :auto-size="{ minRows: 8, maxRows: 16 }"
            placeholder="请输入公告内容"
          />
        </a-form-model-item>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-model-item label="状态">
              <a-select v-model="announcementForm.status">
                <a-select-option value="draft">草稿</a-select-option>
                <a-select-option value="published">发布</a-select-option>
                <a-select-option value="offline">下线</a-select-option>
              </a-select>
            </a-form-model-item>
          </a-col>
          <a-col :span="8">
            <a-form-model-item label="排序">
              <a-input-number v-model="announcementForm.sort_order" :min="0" :step="1" style="width: 100%" />
            </a-form-model-item>
          </a-col>
          <a-col :span="8">
            <a-form-model-item label="登录开屏">
              <a-switch v-model="announcementForm.show_popup" checked-children="弹出" un-checked-children="不弹" />
            </a-form-model-item>
          </a-col>
        </a-row>
      </a-form-model>
    </a-modal>
  </div>
</template>

<script>
import {
  createAnnouncement,
  deleteAnnouncement,
  getAnnouncementConfig,
  listAnnouncements,
  updateAnnouncement,
  updateAnnouncementConfig,
  updateAnnouncementStatus
} from '@/api/system'

export default {
  name: 'AnnouncementManage',
  data() {
    return {
      loading: false,
      savingFixed: false,
      savingAnnouncement: false,
      modalVisible: false,
      editingId: null,
      filters: {
        status: undefined
      },
      fixedForm: {
        announcement_title: '',
        announcement_content: '',
        support_wechat: '',
        support_qq: '',
        support_contact_threshold_cny: 100
      },
      announcementForm: {
        title: '',
        content: '',
        status: 'draft',
        show_popup: true,
        sort_order: 0
      },
      list: [],
      pagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      columns: [
        { title: '公告', key: 'titleCell', width: 320, scopedSlots: { customRender: 'titleCell' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 100, scopedSlots: { customRender: 'status' } },
        { title: '开屏', dataIndex: 'show_popup', key: 'show_popup', width: 120, scopedSlots: { customRender: 'showPopup' } },
        { title: '排序', dataIndex: 'sort_order', key: 'sort_order', width: 80 },
        { title: '发布时间', dataIndex: 'published_at', key: 'published_at', width: 180, scopedSlots: { customRender: 'time' } },
        { title: '操作', key: 'action', width: 180, fixed: 'right', scopedSlots: { customRender: 'action' } }
      ]
    }
  },
  mounted() {
    this.fetchFixedConfig()
    this.fetchAnnouncements()
  },
  methods: {
    async fetchFixedConfig() {
      try {
        const res = await getAnnouncementConfig()
        const threshold = res.data && res.data.support_contact_threshold_cny !== undefined && res.data.support_contact_threshold_cny !== null
          ? Number(res.data.support_contact_threshold_cny)
          : 100
        this.fixedForm = {
          announcement_title: res.data?.announcement_title || '',
          announcement_content: res.data?.announcement_content || '',
          support_wechat: res.data?.support_wechat || '',
          support_qq: res.data?.support_qq || '',
          support_contact_threshold_cny: Number.isFinite(threshold) ? threshold : 100
        }
      } catch (e) {
        this.$message.error('固定公告读取失败')
      }
    },
    async saveFixedConfig() {
      this.savingFixed = true
      try {
        await updateAnnouncementConfig(this.fixedForm)
        this.$message.success('固定公告已保存')
      } finally {
        this.savingFixed = false
      }
    },
    async fetchAnnouncements() {
      this.loading = true
      try {
        const params = {
          page: this.pagination.current,
          page_size: this.pagination.pageSize
        }
        if (this.filters.status) params.status = this.filters.status
        const res = await listAnnouncements(params)
        const data = res.data || {}
        this.list = data.list || []
        this.pagination.total = data.total || 0
      } finally {
        this.loading = false
      }
    },
    handleFilterChange() {
      this.pagination.current = 1
      this.fetchAnnouncements()
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchAnnouncements()
    },
    openCreateModal() {
      this.editingId = null
      this.announcementForm = {
        title: '',
        content: '',
        status: 'draft',
        show_popup: true,
        sort_order: 0
      }
      this.modalVisible = true
    },
    openEditModal(record) {
      this.editingId = record.id
      this.announcementForm = {
        title: record.title,
        content: record.content,
        status: record.status,
        show_popup: Boolean(record.show_popup),
        sort_order: record.sort_order || 0
      }
      this.modalVisible = true
    },
    async submitAnnouncement() {
      this.savingAnnouncement = true
      try {
        if (this.editingId) {
          await updateAnnouncement(this.editingId, this.announcementForm)
        } else {
          await createAnnouncement(this.announcementForm)
        }
        this.$message.success('公告已保存')
        this.modalVisible = false
        this.fetchAnnouncements()
      } finally {
        this.savingAnnouncement = false
      }
    },
    async toggleStatus(record) {
      const status = record.status === 'published' ? 'offline' : 'published'
      await updateAnnouncementStatus(record.id, { status })
      this.$message.success(status === 'published' ? '公告已发布' : '公告已下线')
      this.fetchAnnouncements()
    },
    async removeAnnouncement(record) {
      await deleteAnnouncement(record.id)
      this.$message.success('公告已删除')
      this.fetchAnnouncements()
    },
    statusText(status) {
      return {
        draft: '草稿',
        published: '已发布',
        offline: '已下线'
      }[status] || status
    },
    statusColor(status) {
      return {
        draft: 'default',
        published: 'green',
        offline: 'orange'
      }[status] || 'default'
    },
    formatTime(value) {
      return String(value).replace('T', ' ').slice(0, 19)
    }
  }
}
</script>

<style lang="less" scoped>
.announcement-manage-page {
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 24px;
  }

  .page-title {
    margin: 0;
    font-size: 24px;
    font-weight: 700;
    color: #1f2937;
  }

  .page-subtitle {
    margin: 6px 0 0;
    color: #6b7280;
  }

  .panel-card {
    border-radius: 8px;
    box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
  }

  .card-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 700;
  }

  .contact-gate-alert {
    margin-bottom: 16px;
    border-radius: 8px;
  }

  .table-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .announcement-title {
    font-weight: 700;
    color: #111827;
    margin-bottom: 4px;
  }

  .announcement-preview {
    max-width: 280px;
    color: #6b7280;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .danger-link {
    color: #ff4d4f;
  }
}
</style>
