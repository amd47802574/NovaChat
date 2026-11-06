<template>
  <div class="audit" @keydown.esc.window="selectedLog = null">
    <div class="section-title">
      <h3><i class="fas fa-clipboard-list"></i> 安全审计</h3>
      <div class="toolbar">
        <select v-model="actionFilter" class="filter-select" @change="onFilter">
          <option value="">全部动作</option>
          <option v-for="a in actionOptions" :key="a.value" :value="a.value">{{ a.label }}</option>
        </select>
        <div class="search-box">
          <i class="fas fa-search"></i>
          <input v-model="searchInput" type="text" placeholder="操作人 / 详情 / 对象" @keyup.enter="onFilter" />
        </div>
        <button class="btn-secondary" @click="onFilter"><i class="fas fa-search"></i> 检索</button>
      </div>
    </div>

    <div v-if="store.auditLoading && !store.auditLogs.length" class="loading-box">加载中...</div>

    <template v-else>
      <div v-if="store.auditLogs.length" class="table-wrap">
        <table class="audit-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>操作人</th>
              <th>动作</th>
              <th>对象</th>
              <th>详情</th>
              <th>来源 IP</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in store.auditLogs" :key="log.id">
              <td class="cell-time">{{ formatTime(log.created_at) }}</td>
              <td>
                {{ log.actor }}
                <span class="role-badge" :class="'role-' + log.actor_role">{{ roleLabel(log.actor_role) }}</span>
              </td>
              <td><span class="action-tag">{{ actionLabel(log.action) }}</span></td>
              <td class="cell-target">
                <template v-if="log.target_type">{{ log.target_type }}#{{ log.target_id }}</template>
                <span v-else>—</span>
              </td>
              <td class="cell-detail">
                <button
                  type="button"
                  class="detail-trigger"
                  :title="log.detail || '查看审计记录详情'"
                  aria-haspopup="dialog"
                  @click="selectedLog = log"
                >
                  <span class="detail-preview">{{ log.detail || '—' }}</span>
                  <span class="detail-hint"><i class="fas fa-arrow-up-right-from-square"></i> 查看详情</span>
                </button>
              </td>
              <td class="cell-time">{{ log.ip || '—' }}</td>
            </tr>
          </tbody>
        </table>

        <div class="pager">
          <button :disabled="store.auditPage <= 1" @click="store.setAuditPage(store.auditPage - 1)">
            <i class="fas fa-chevron-left"></i> 上一页
          </button>
          <span>第 {{ store.auditPage }} 页 / 共 {{ auditPages }} 页（{{ store.auditTotal }} 条）</span>
          <button :disabled="store.auditPage >= auditPages" @click="store.setAuditPage(store.auditPage + 1)">
            下一页 <i class="fas fa-chevron-right"></i>
          </button>
        </div>
      </div>

      <div v-else class="empty-box">
        <i class="fas fa-clipboard"></i>
        <p>暂无审计记录</p>
      </div>
    </template>

    <div v-if="selectedLog" class="detail-mask" @click.self="selectedLog = null">
      <section
        class="detail-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="audit-detail-title"
        tabindex="-1"
      >
        <div class="detail-header">
          <div>
            <h4 id="audit-detail-title">审计记录详情</h4>
            <span class="detail-record-id">记录 #{{ selectedLog.id }}</span>
          </div>
          <button type="button" class="detail-close" aria-label="关闭详情" @click="selectedLog = null">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <dl class="detail-fields">
          <div class="detail-field">
            <dt>时间</dt>
            <dd>{{ formatTime(selectedLog.created_at) }}</dd>
          </div>
          <div class="detail-field">
            <dt>操作人</dt>
            <dd>
              {{ selectedLog.actor }}
              <span class="role-badge" :class="'role-' + selectedLog.actor_role">{{ roleLabel(selectedLog.actor_role) }}</span>
            </dd>
          </div>
          <div class="detail-field">
            <dt>动作</dt>
            <dd>{{ actionLabel(selectedLog.action) }}</dd>
          </div>
          <div class="detail-field">
            <dt>对象</dt>
            <dd>{{ selectedLog.target_type ? `${selectedLog.target_type}#${selectedLog.target_id}` : '—' }}</dd>
          </div>
          <div class="detail-field">
            <dt>来源 IP</dt>
            <dd>{{ selectedLog.ip || '—' }}</dd>
          </div>
          <div class="detail-field detail-field-full">
            <dt>详情</dt>
            <dd class="detail-content">{{ selectedLog.detail || '—' }}</dd>
          </div>
        </dl>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useSuperAdminStore, ROLE_LABELS } from '@/stores/superAdmin';
import type { AuditLogItem, UserRole } from '@/types/user';
import { formatUtc8 } from '@/utils/time';

const store = useSuperAdminStore();
const searchInput = ref('');
const actionFilter = ref('');
const selectedLog = ref<AuditLogItem | null>(null);

const actionOptions = [
  { value: 'login', label: '登录成功' },
  { value: 'login_failed', label: '登录失败' },
  { value: 'user_register', label: '自助注册' },
  { value: 'user_create', label: '后台创建用户' },
  { value: 'user_update', label: '修改用户' },
  { value: 'user_enable', label: '启用用户' },
  { value: 'user_disable', label: '禁用用户' },
];

const auditPages = computed(() => Math.max(1, Math.ceil(store.auditTotal / store.auditPageSize)));
const roleLabel = (role: string) => ROLE_LABELS[role as UserRole] || role;

const actionLabel = (action: string) => {
  const found = actionOptions.find((a) => a.value === action);
  if (found) return found.label;
  return action;
};

const formatTime = (iso: string | null) => formatUtc8(iso);

const onFilter = () => store.setAuditFilter(actionFilter.value, searchInput.value);

onMounted(() => {
  store.fetchAuditLogs();
});
</script>

<style scoped>
.audit {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.section-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.section-title h3 {
  color: var(--primary-color);
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.filter-select {
  flex: 0 0 auto;
  max-width: 100%;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 14px;
  padding: 8px 12px;
  min-height: 38px;
  box-sizing: border-box;
  background: var(--white);
  color: var(--text-color);
  box-shadow: var(--shadow);
}
.search-box {
  display: flex;
  align-items: center;
  flex: 1 1 200px;
  min-width: 0;
  min-height: 38px;
  box-sizing: border-box;
  background: var(--white);
  border-radius: 14px;
  padding: 8px 12px;
  box-shadow: var(--shadow);
  gap: 8px;
}
.search-box input {
  border: none;
  outline: none;
  background: transparent;
  width: 100%;
  min-width: 0;
  color: var(--text-color);
}
.btn-secondary {
  margin: 0;
  border: 1px solid var(--border-color, #e3eaf3);
  background: var(--white);
  color: var(--primary-color);
  border-radius: 14px;
  padding: 8px 22px;
  min-width: 88px;
  min-height: 38px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  line-height: 1.2;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.08);
}
.btn-secondary:hover {
  background: #f0f6ff;
  transform: none;
}
.table-wrap {
  max-width: 100%;
  background: var(--white);
  border: 1px solid var(--border-color, #e3eaf3);
  border-radius: var(--border-radius);
  box-shadow: var(--shadow);
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.audit-table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 0.88rem;
}
.audit-table th:nth-child(1) {
  width: 165px;
}
.audit-table th:nth-child(3) {
  width: 150px;
}
.audit-table th:nth-child(4) {
  width: 130px;
}
.audit-table th:nth-child(6) {
  width: 140px;
}
.audit-table th,
.audit-table td {
  padding: 12px 14px;
  text-align: left;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.audit-table th {
  color: var(--text-light);
  font-weight: 700;
}
.cell-time {
  color: var(--text-light);
}
.cell-target {
  font-family: monospace;
}
.cell-detail {
  color: var(--text-color);
}
.audit-table td.cell-detail {
  padding: 4px 8px;
}
.detail-trigger {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 0;
  border-radius: 8px;
  padding: 8px 10px;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.detail-trigger:hover,
.detail-trigger:focus-visible {
  outline: none;
  background: #f0f6ff;
}
.detail-preview {
  min-width: 0;
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  white-space: normal;
  overflow-wrap: anywhere;
  color: var(--text-color);
}
.detail-hint {
  flex: 0 0 auto;
  color: var(--primary-color);
  font-size: 0.78rem;
  font-weight: 600;
  white-space: nowrap;
}
.detail-mask {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(15, 23, 42, 0.48);
}
.detail-modal {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: min(640px, 100%);
  max-height: min(80vh, 760px);
  overflow-y: auto;
  padding: 24px;
  border: 1px solid var(--border-color, #e3eaf3);
  border-radius: var(--border-radius);
  background: var(--white);
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.24);
  outline: none;
}
.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.detail-header h4 {
  margin: 0;
  color: var(--primary-color);
  font-size: 1.1rem;
}
.detail-record-id {
  display: inline-block;
  margin-top: 5px;
  color: var(--text-light);
  font-size: 0.82rem;
}
.detail-close {
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: 50%;
  background: var(--bg-color);
  color: var(--text-light);
  cursor: pointer;
}
.detail-close:hover {
  color: var(--text-color);
  background: #e8eef6;
}
.detail-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin: 0;
}
.detail-field {
  min-width: 0;
  padding: 12px 14px;
  border: 1px solid var(--border-color, #e3eaf3);
  border-radius: 12px;
  background: var(--white);
}
.detail-field dt {
  margin-bottom: 6px;
  color: var(--text-light);
  font-size: 0.78rem;
  font-weight: 600;
}
.detail-field dd {
  margin: 0;
  color: var(--text-color);
  font-size: 0.9rem;
  overflow-wrap: anywhere;
}
.detail-field-full {
  grid-column: 1 / -1;
}
.detail-content {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
  line-height: 1.6;
}
.role-badge {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 0.72rem;
  margin-left: 6px;
}
.role-user {
  background: #eef2f7;
  color: #475569;
}
.role-admin {
  background: #e8f1fe;
  color: #1d4ed8;
}
.role-super_admin {
  background: #ffe9e6;
  color: #c0392b;
}
.role-unknown {
  background: #eef2f7;
  color: #64748b;
}
.action-tag {
  background: var(--bg-color);
  padding: 3px 10px;
  border-radius: 12px;
  color: var(--text-color);
  font-size: 0.8rem;
}
.pager {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 14px;
  color: var(--text-light);
  font-size: 0.85rem;
}
.pager button {
  border: none;
  background: var(--bg-color);
  border-radius: 12px;
  padding: 6px 12px;
  cursor: pointer;
  color: var(--text-color);
}
.pager button:disabled {
  opacity: 0.5;
  cursor: default;
}
.empty-box,
.loading-box {
  text-align: center;
  color: var(--text-light);
  padding: 40px;
}
.empty-box i {
  font-size: 2rem;
  display: block;
  margin-bottom: 10px;
}

@media (max-width: 640px) {
  .toolbar {
    width: 100%;
  }
  .filter-select {
    flex: 1 1 100%;
  }
  .search-box {
    flex: 1 1 100%;
  }
  .audit-table th:nth-child(1) {
    width: 140px;
  }
  .audit-table th:nth-child(3) {
    width: 110px;
  }
  .audit-table th:nth-child(4) {
    width: 100px;
  }
  .audit-table th:nth-child(6) {
    width: 120px;
  }
  .audit-table th,
  .audit-table td {
    padding: 10px 12px;
  }
  .detail-mask {
    padding: 12px;
  }
  .detail-modal {
    max-height: 88vh;
    padding: 18px;
  }
  .detail-fields {
    grid-template-columns: minmax(0, 1fr);
  }
  .detail-field-full {
    grid-column: auto;
  }
}
</style>
