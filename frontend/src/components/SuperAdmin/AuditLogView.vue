<template>
  <div class="audit">
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
              <td class="cell-detail">{{ log.detail || '—' }}</td>
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useSuperAdminStore, ROLE_LABELS } from '@/stores/superAdmin';
import type { UserRole } from '@/types/user';

const store = useSuperAdminStore();
const searchInput = ref('');
const actionFilter = ref('');

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

const formatTime = (iso: string | null) => {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
};

const onFilter = () => store.setAuditFilter(actionFilter.value, searchInput.value);

onMounted(() => {
  if (!store.auditLogs.length) store.fetchAuditLogs();
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
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
  overflow: hidden;
  text-overflow: unset;
  color: var(--text-color);
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
}
</style>
