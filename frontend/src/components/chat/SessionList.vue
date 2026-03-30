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
  background: #1a1a2e;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px;
  padding: 10px 16px;
  border-radius: 10px;
  border: 1px dashed rgba(102, 126, 234, 0.3);
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  font-size: 14px;
  transition: all 0.25s ease;
  flex-shrink: 0;

  &:hover {
    background: rgba(102, 126, 234, 0.1);
    border-color: rgba(102, 126, 234, 0.5);
    color: #fff;
  }

  .anticon {
    font-size: 14px;
  }
}

.sessions-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;

  &::-webkit-scrollbar {
    width: 3px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  &::-webkit-scrollbar-thumb {
    background: rgba(102, 126, 234, 0.2);
    border-radius: 3px;
  }
}

.session-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  margin: 2px 4px;
  border-radius: 8px;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.55);
  transition: all 0.2s ease;
  position: relative;
  border: 1px solid transparent;

  &:hover {
    background: rgba(102, 126, 234, 0.08);
    color: rgba(255, 255, 255, 0.85);

    .session-delete {
      opacity: 1;
    }
  }

  &--active {
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.15), rgba(118, 75, 162, 0.1));
    color: #fff;
    border-color: rgba(102, 126, 234, 0.2);

    .session-icon {
      color: #a8b8ff;
    }
  }
}

.session-icon {
  font-size: 14px;
  flex-shrink: 0;
  color: rgba(255, 255, 255, 0.35);
}

.session-title {
  flex: 1;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-delete {
  opacity: 0;
  flex-shrink: 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s ease;

  &:hover {
    color: #ff6b6b;
    background: rgba(255, 107, 107, 0.1);
  }
}

.empty-tip {
  text-align: center;
  color: rgba(255, 255, 255, 0.25);
  font-size: 13px;
  padding: 24px 0;
}

.clear-all-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 12px 12px;
  padding: 8px 16px;
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s ease;
  flex-shrink: 0;

  &:hover {
    background: rgba(255, 107, 107, 0.08);
    color: #ff6b6b;
  }
}
</style>
