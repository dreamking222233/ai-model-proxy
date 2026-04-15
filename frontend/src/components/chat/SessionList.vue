<template>
  <div class="session-list">
    <!-- New chat button -->
    <div class="new-chat-btn" @click="$emit('new-session')">
      <a-icon type="plus" />
      <span>新对话</span>
    </div>

    <!-- Sessions -->
    <div class="sessions-scroll">
      <div
        v-for="session in sessions"
        :key="session.id"
        class="session-item"
        :class="{ 'session-item--active': currentId === session.id }"
        @click="$emit('select', session.id)"
      >
        <a-icon type="message" class="session-icon" />
        <span class="session-title">{{ session.title || '新对话' }}</span>
        <span
          class="session-delete"
          @click.stop="$emit('delete', session.id)"
        >
          <a-icon type="delete" />
        </span>
      </div>

      <div v-if="sessions.length === 0" class="empty-tip">
        暂无对话记录
      </div>
    </div>

    <!-- Clear all -->
    <div
      v-if="sessions.length > 0"
      class="clear-all-btn"
      @click="handleClearAll"
    >
      <a-icon type="rest" />
      <span>清空所有对话</span>
    </div>
  </div>
</template>

<script>
export default {
  name: 'SessionList',
  props: {
    sessions: {
      type: Array,
      default: function () { return [] }
    },
    currentId: {
      type: String,
      default: ''
    }
  },
  methods: {
    handleClearAll: function () {
      var self = this
      this.$confirm({
        title: '确认清空',
        content: '确定要清空所有对话记录吗？此操作不可恢复。',
        okText: '清空',
        okType: 'danger',
        cancelText: '取消',
        onOk: function () {
          self.$emit('clear-all')
        }
      })
    }
  }
}
</script>

<style lang="less" scoped>
.session-list {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: transparent;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 16px;
  padding: 12px 20px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1));
  border: 1px solid rgba(102, 126, 234, 0.2);
  color: #667eea;
  cursor: pointer;
  font-size: 14px;
  font-weight: 700;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  flex-shrink: 0;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.02);

  &:hover {
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.15), rgba(118, 75, 162, 0.15));
    border-color: rgba(102, 126, 234, 0.3);
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.1);
  }

  .anticon { font-size: 16px; }
}

.sessions-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;

  &::-webkit-scrollbar { width: 3px; }
  &::-webkit-scrollbar-track { background: transparent; }
  &::-webkit-scrollbar-thumb { background: rgba(102, 126, 234, 0.1); border-radius: 10px; }
}

.session-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  margin-bottom: 8px;
  border-radius: 12px;
  cursor: pointer;
  color: #595959;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);

  &:hover {
    background: rgba(102, 126, 234, 0.06);
    color: #667eea;
    border-color: rgba(102, 126, 234, 0.15);
    .session-delete { opacity: 1; }
  }

  &--active {
    background: #fff;
    color: #1a1a2e;
    font-weight: 700;
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.04);
    border-color: rgba(102, 126, 234, 0.3);

    .session-icon { color: #667eea; }
    &::before {
      content: ''; position: absolute; left: 0; top: 12px; bottom: 12px; width: 4px;
      background: linear-gradient(180deg, #667eea, #764ba2);
      border-radius: 0 4px 4px 0;
    }
  }
}

.session-icon { font-size: 15px; flex-shrink: 0; color: #bfbfbf; }
.session-title { flex: 1; font-size: 13.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.session-delete {
  opacity: 0; flex-shrink: 0; font-size: 14px; color: #bfbfbf; padding: 4px; border-radius: 6px; transition: all 0.2s;
  &:hover { color: #ff6b6b; background: rgba(255, 107, 107, 0.1); }
}

.empty-tip {
  text-align: center; color: #bfbfbf; font-size: 13px; padding: 40px 0;
  font-weight: 500;
}

.clear-all-btn {
  display: flex; align-items: center; gap: 8px; margin: 12px; padding: 10px 16px;
  border-radius: 10px; color: #8c8c8c; cursor: pointer; font-size: 12px; font-weight: 600;
  transition: all 0.2s; flex-shrink: 0;
  background: rgba(0, 0, 0, 0.02);
  
  &:hover { background: rgba(255, 77, 79, 0.05); color: #ff4d4f; }
}
</style>
