<template>
  <div class="model-group-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">模型分组</h2>
        <p class="page-subtitle">按模型系列管理路由分组、默认组和分组倍率</p>
      </div>
      <div class="page-actions">
        <a-button @click="fetchGroups" :loading="loading"><a-icon type="reload" />刷新</a-button>
        <a-button type="primary" @click="openCreate"><a-icon type="plus" />新增分组</a-button>
      </div>
    </div>

    <a-card :bordered="false" class="group-card">
      <div class="filter-bar">
        <a-select v-model="filters.model_series" allow-clear placeholder="全部模型系列" style="width: 180px" @change="fetchGroups">
          <a-select-option v-for="item in seriesOptions" :key="item.value" :value="item.value">{{ item.label }}</a-select-option>
        </a-select>
        <a-select v-model="filters.enabled" allow-clear placeholder="全部状态" style="width: 140px" @change="fetchGroups">
          <a-select-option :value="1">启用</a-select-option>
          <a-select-option :value="0">禁用</a-select-option>
        </a-select>
      </div>
      <a-table
        :columns="columns"
        :data-source="groups"
        :loading="loading"
        row-key="id"
        :pagination="false"
        :scroll="{ x: 980 }"
      >
        <template slot="series" slot-scope="text">
          <a-tag :color="getSeriesColor(text)">{{ getSeriesLabel(text) }}</a-tag>
        </template>
        <template slot="multiplier" slot-scope="text">
          <strong class="multiplier">x{{ formatMultiplier(text) }}</strong>
        </template>
        <template slot="default" slot-scope="text, record">
          <a-tag v-if="record.is_default" color="gold">默认组</a-tag>
          <span v-else class="muted">否</span>
        </template>
        <template slot="enabled" slot-scope="text">
          <a-tag :color="text ? 'green' : 'red'">{{ text ? '启用' : '禁用' }}</a-tag>
        </template>
        <template slot="action" slot-scope="text, record">
          <a-space>
            <a @click="openEdit(record)">编辑</a>
            <a v-if="!record.is_default && record.enabled" @click="makeDefault(record)">设为默认</a>
            <a-popconfirm title="确定删除该分组吗？" ok-text="确定" cancel-text="取消" @confirm="removeGroup(record)">
              <a class="danger-link">删除</a>
            </a-popconfirm>
          </a-space>
        </template>
      </a-table>
      <a-empty v-if="!loading && groups.length === 0" description="暂无模型分组" />
    </a-card>

    <a-modal
      :title="editingId ? '编辑模型分组' : '新增模型分组'"
      :visible="modalVisible"
      :confirm-loading="saving"
      @ok="submit"
      @cancel="modalVisible = false"
    >
      <a-form-model layout="vertical">
        <a-form-model-item label="模型系列">
          <a-select v-model="form.model_series" :disabled="Boolean(editingId)" placeholder="选择模型系列">
            <a-select-option v-for="item in seriesOptions" :key="item.value" :value="item.value">{{ item.label }}</a-select-option>
          </a-select>
        </a-form-model-item>
        <a-form-model-item label="分组编码">
          <a-input v-model="form.code" :disabled="Boolean(editingId)" placeholder="例如 budget 或 standard" />
        </a-form-model-item>
        <a-form-model-item label="分组名称">
          <a-input v-model="form.name" placeholder="例如 特惠分组" />
        </a-form-model-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-model-item label="分组倍率">
              <a-input-number v-model="form.multiplier" :min="0.001" :max="100" :step="0.1" :precision="3" style="width: 100%" />
            </a-form-model-item>
          </a-col>
          <a-col :span="12">
            <a-form-model-item label="排序">
              <a-input-number v-model="form.sort_order" :min="0" :max="9999" style="width: 100%" />
            </a-form-model-item>
          </a-col>
        </a-row>
        <a-form-model-item label="启用">
          <a-switch v-model="form.enabled" checked-children="启用" un-checked-children="禁用" />
        </a-form-model-item>
        <a-form-model-item label="说明">
          <a-textarea v-model="form.description" :rows="3" placeholder="可选" />
        </a-form-model-item>
      </a-form-model>
    </a-modal>
  </div>
</template>

<script>
import {
  listModelGroups,
  createModelGroup,
  updateModelGroup,
  setDefaultModelGroup,
  deleteModelGroup
} from '@/api/modelGroup'
import { MODEL_SERIES_OPTIONS, getModelSeriesLabel, getModelSeriesColor } from '@/constants/modelSeries'

export default {
  name: 'ModelGroupManage',
  data() {
    return {
      loading: false,
      saving: false,
      groups: [],
      filters: { model_series: undefined, enabled: undefined },
      modalVisible: false,
      editingId: null,
      form: this.defaultForm(),
      seriesOptions: MODEL_SERIES_OPTIONS,
      columns: [
        { title: '名称', dataIndex: 'name', key: 'name', width: 180 },
        { title: '编码', dataIndex: 'code', key: 'code', width: 160 },
        { title: '系列', dataIndex: 'model_series', key: 'series', width: 130, scopedSlots: { customRender: 'series' } },
        { title: '倍率', dataIndex: 'multiplier', key: 'multiplier', width: 100, scopedSlots: { customRender: 'multiplier' } },
        { title: '默认', dataIndex: 'is_default', key: 'default', width: 90, scopedSlots: { customRender: 'default' } },
        { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 90, scopedSlots: { customRender: 'enabled' } },
        { title: '说明', dataIndex: 'description', key: 'description', ellipsis: true },
        { title: '操作', key: 'action', width: 220, fixed: 'right', scopedSlots: { customRender: 'action' } }
      ]
    }
  },
  mounted() {
    this.fetchGroups()
  },
  methods: {
    defaultForm() {
      return {
        model_series: 'other',
        code: '',
        name: '',
        multiplier: 1,
        sort_order: 100,
        enabled: true,
        description: ''
      }
    },
    async fetchGroups() {
      this.loading = true
      try {
        const res = await listModelGroups({
          model_series: this.filters.model_series,
          include_disabled: true
        })
        const data = res.data || []
        const list = Array.isArray(data) ? data : (data.list || [])
        this.groups = this.filters.enabled == null
          ? list
          : list.filter(item => Number(item.enabled) === Number(this.filters.enabled))
      } finally {
        this.loading = false
      }
    },
    openCreate() {
      this.editingId = null
      this.form = this.defaultForm()
      this.modalVisible = true
    },
    openEdit(record) {
      this.editingId = record.id
      this.form = {
        model_series: record.model_series || 'other',
        code: record.code || '',
        name: record.name || '',
        multiplier: Number(record.multiplier || 1),
        sort_order: Number(record.sort_order || 100),
        enabled: Boolean(record.enabled),
        description: record.description || ''
      }
      this.modalVisible = true
    },
    async submit() {
      if (!this.form.model_series || !this.form.code || !this.form.name) {
        this.$message.warning('请填写模型系列、分组编码和名称')
        return
      }
      this.saving = true
      try {
        const payload = { ...this.form, multiplier: Number(this.form.multiplier || 1), sort_order: Number(this.form.sort_order || 100), enabled: this.form.enabled ? 1 : 0 }
        if (this.editingId) await updateModelGroup(this.editingId, payload)
        else await createModelGroup(payload)
        this.$message.success('模型分组已保存')
        this.modalVisible = false
        await this.fetchGroups()
      } finally {
        this.saving = false
      }
    },
    async makeDefault(record) {
      await setDefaultModelGroup(record.id)
      this.$message.success('默认分组已更新')
      this.fetchGroups()
    },
    async removeGroup(record) {
      await deleteModelGroup(record.id)
      this.$message.success('模型分组已删除')
      this.fetchGroups()
    },
    getSeriesLabel(value) {
      return getModelSeriesLabel(value)
    },
    getSeriesColor(value) {
      return getModelSeriesColor(value)
    },
    formatMultiplier(value) {
      const num = Number(value || 1)
      return Number.isInteger(num) ? String(num) : num.toFixed(3).replace(/0+$/, '').replace(/\.$/, '')
    }
  }
}
</script>

<style lang="less" scoped>
.model-group-page { padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-title { margin: 0; font-weight: 700; }
.page-subtitle { margin: 6px 0 0; color: #64748b; }
.page-actions { display: flex; gap: 8px; }
.group-card { margin-bottom: 16px; }
.filter-bar { display: flex; gap: 10px; margin-bottom: 16px; }
.multiplier { color: #0f766e; }
.muted { color: #94a3b8; }
.danger-link { color: #f5222d; }
@media (max-width: 768px) {
  .model-group-page { padding: 16px; }
  .page-header { align-items: flex-start; gap: 12px; flex-direction: column; }
  .filter-bar { flex-wrap: wrap; }
}
</style>
