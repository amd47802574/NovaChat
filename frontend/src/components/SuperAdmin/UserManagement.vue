<template>
  <div class="user-mgmt">
    <div class="section-title">
      <h3><i class="fas fa-users-cog"></i> 用户管理</h3>
      <div class="toolbar">
        <div class="search-box">
          <i class="fas fa-search"></i>
          <input
            v-model="searchInput"
            type="text"
            placeholder="按用户名检索（输入即搜）"
            @input="onInput"
            @compositionstart="composing = true"
            @compositionend="onCompositionEnd"
          />
          <button v-if="searchInput" class="clear-btn" title="清空检索" @click="clearSearch">
            <i class="fas fa-circle-xmark"></i>
          </button>
          <i v-if="store.usersLoading" class="fas fa-spinner fa-spin search-spin"></i>
        </div>
        <button class="btn-primary" @click="openCreate"><i class="fas fa-user-plus"></i> 新建用户</button>
      </div>
    </div>

    <div v-if="store.usersLoading && !store.users.length" class="loading-box">加载中...</div>

    <template v-else>
      <div v-if="store.users.length" class="table-wrap">
        <table class="user-table">
          <thead>
            <tr>
              <th>用户名</th>
              <th>角色</th>
              <th>状态</th>
              <th>创建时间</th>
              <th>最近登录</th>
              <th class="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in store.users" :key="u.id">
              <td class="cell-username">{{ u.username }}</td>
              <td>
                <span class="role-badge" :class="'role-' + u.role">{{ roleLabel(u.role) }}</span>
              </td>
              <td>
                <span v-if="!u.is_active" class="status-badge status-off">已禁用</span>
                <span v-else-if="u.is_locked" class="status-badge status-lock">已锁定</span>
                <span v-else class="status-badge status-on">启用中</span>
              </td>
              <td class="cell-time">{{ formatTime(u.created_at) }}</td>
              <td class="cell-time">{{ formatTime(u.last_login_at) || '—' }}</td>
              <td class="col-actions">
                <button class="link-btn" @click="openEdit(u)"><i class="fas fa-edit"></i> 编辑</button>
                <button class="link-btn" @click="openResetPwd(u)"><i class="fas fa-key"></i> 重置密码</button>
                <button class="link-btn" :class="u.is_active ? 'danger' : 'success'" @click="onToggle(u)">
                  <i :class="u.is_active ? 'fas fa-ban' : 'fas fa-check'"></i>
                  {{ u.is_active ? '禁用' : '启用' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>

        <div class="pager">
          <button :disabled="store.usersPage <= 1" @click="store.setUsersPage(store.usersPage - 1)">
            <i class="fas fa-chevron-left"></i> 上一页
          </button>
          <span>第 {{ store.usersPage }} 页 / 共 {{ totalPages }} 页（{{ store.usersTotal }} 人）</span>
          <button :disabled="store.usersPage >= totalPages" @click="store.setUsersPage(store.usersPage + 1)">
            下一页 <i class="fas fa-chevron-right"></i>
          </button>
        </div>
      </div>

      <div v-else class="empty-box">
        <i :class="store.usersError ? 'fas fa-plug-circle-exclamation' : 'fas fa-user-slash'"></i>
        <p>{{ store.usersError ? '检索失败，请检查网络后重试' : `没有匹配「${store.usersSearch.trim()}」的用户` }}</p>
        <button v-if="store.usersError" class="btn-secondary retry-btn" @click="triggerSearch">
          <i class="fas fa-rotate-right"></i> 重试
        </button>
      </div>
    </template>

    <!-- 重置密码弹窗 -->
    <div v-if="resetTarget" class="modal-mask" @click.self="resetTarget = null">
      <div class="modal">
        <h4><i class="fas fa-key"></i> 重置密码：{{ resetTarget.username }}</h4>
        <label class="field">
          <span>新密码（至少 6 位）</span>
          <input v-model="resetPwd" type="password" placeholder="输入新密码" autocomplete="new-password" />
        </label>
        <label class="field">
          <span>确认新密码</span>
          <input v-model="resetPwdConfirm" type="password" placeholder="再次输入新密码" autocomplete="new-password" />
        </label>
        <p v-if="resetTarget.is_locked" class="warn">
          <i class="fas fa-triangle-exclamation"></i> 该账号当前处于锁定状态，重置密码后将自动解除锁定
        </p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="resetTarget = null">取消</button>
          <button class="btn-primary" :disabled="saving" @click="onResetPwd">{{ saving ? '提交中...' : '确认重置' }}</button>
        </div>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <div v-if="editTarget" class="modal-mask" @click.self="editTarget = null">
      <div class="modal">
        <h4><i class="fas fa-edit"></i> 编辑用户：{{ editTarget.username }}</h4>
        <label class="field">
          <span>角色</span>
          <select v-model="editRole">
            <option value="user">普通用户</option>
            <option value="admin">管理员</option>
            <option value="super_admin">超级管理员</option>
          </select>
        </label>
        <label class="field">
          <span>账号状态</span>
          <select v-model="editActive">
            <option :value="true">启用</option>
            <option :value="false">禁用</option>
          </select>
        </label>
        <p v-if="selfEditWarn" class="warn"><i class="fas fa-triangle-exclamation"></i> 不能修改自身角色或禁用自己</p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="editTarget = null">取消</button>
          <button class="btn-primary" :disabled="saving" @click="onSaveEdit">{{ saving ? '保存中...' : '保存' }}</button>
        </div>
      </div>
    </div>

    <!-- 新建弹窗 -->
    <div v-if="showCreate" class="modal-mask" @click.self="showCreate = false">
      <div class="modal">
        <h4><i class="fas fa-user-plus"></i> 新建用户</h4>
        <label class="field">
          <span>用户名</span>
          <input v-model="createForm.username" type="text" placeholder="登录用户名" />
        </label>
        <label class="field">
          <span>初始密码</span>
          <input v-model="createForm.password" type="password" placeholder="初始密码" />
        </label>
        <label class="field">
          <span>角色</span>
          <select v-model="createForm.role">
            <option value="user">普通用户</option>
            <option value="admin">管理员</option>
            <option value="super_admin">超级管理员</option>
          </select>
        </label>
        <label class="field row">
          <span>账号状态</span>
          <select v-model="createForm.is_active">
            <option :value="true">启用</option>
            <option :value="false">禁用</option>
          </select>
        </label>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showCreate = false">取消</button>
          <button class="btn-primary" :disabled="saving" @click="onCreate">{{ saving ? '创建中...' : '创建' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useSuperAdminStore, ROLE_LABELS } from '@/stores/superAdmin';
import { useAuthStore } from '@/stores/auth';
import type { AdminUserItem, UserRole } from '@/types/user';
import { formatUtc8 } from '@/utils/time';

const store = useSuperAdminStore();
const authStore = useAuthStore();

const SEARCH_DEBOUNCE_MS = 300;
const searchInput = ref('');
const composing = ref(false);
let debounceTimer: ReturnType<typeof setTimeout> | null = null;
const editTarget = ref<AdminUserItem | null>(null);
const editRole = ref<UserRole>('user');
const editActive = ref(true);
const showCreate = ref(false);
const saving = ref(false);
const resetTarget = ref<AdminUserItem | null>(null);
const resetPwd = ref('');
const resetPwdConfirm = ref('');
const createForm = ref({ username: '', password: '', role: 'user' as UserRole, is_active: true });

const totalPages = computed(() => Math.max(1, Math.ceil(store.usersTotal / store.usersPageSize)));
const selfEditWarn = computed(
  () => editTarget.value?.username === authStore.currentUser?.username && (editRole.value !== 'super_admin' || !editActive.value)
);

const roleLabel = (role: string) => ROLE_LABELS[role as UserRole] || role;

const formatTime = (iso: string | null) => formatUtc8(iso);

const triggerSearch = () => {
  store.setUsersSearch(searchInput.value).catch(() => {});
};

const onInput = () => {
  if (composing.value) return;
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(triggerSearch, SEARCH_DEBOUNCE_MS);
};

const onCompositionEnd = () => {
  composing.value = false;
  onInput();
};

const clearSearch = () => {
  if (debounceTimer) clearTimeout(debounceTimer);
  searchInput.value = '';
  triggerSearch();
};

onBeforeUnmount(() => {
  if (debounceTimer) clearTimeout(debounceTimer);
});

const openEdit = (u: AdminUserItem) => {
  editTarget.value = u;
  editRole.value = u.role;
  editActive.value = u.is_active;
};

const onSaveEdit = async () => {
  if (!editTarget.value) return;
  if (selfEditWarn.value) {
    alert('不能修改自身角色或禁用自己');
    return;
  }
  saving.value = true;
  try {
    await store.updateUser(editTarget.value.id, { role: editRole.value, is_active: editActive.value });
    alert('已保存');
    editTarget.value = null;
  } catch (e: any) {
    alert(e.message);
  } finally {
    saving.value = false;
  }
};

const onToggle = async (u: AdminUserItem) => {
  if (u.username === authStore.currentUser?.username) {
    alert('不能禁用自身账号');
    return;
  }
  if (!confirm(`确定要${u.is_active ? '禁用' : '启用'}用户「${u.username}」吗？`)) return;
  try {
    await store.toggleUserActive(u.id);
  } catch (e: any) {
    alert(e.message);
  }
};

const openCreate = () => {
  createForm.value = { username: '', password: '', role: 'user', is_active: true };
  showCreate.value = true;
};

const openResetPwd = (u: AdminUserItem) => {
  resetTarget.value = u;
  resetPwd.value = '';
  resetPwdConfirm.value = '';
};

const onResetPwd = async () => {
  if (!resetTarget.value) return;
  const pwd = resetPwd.value.trim();
  if (!pwd) {
    alert('新密码不能为空');
    return;
  }
  if (pwd.length < 6) {
    alert('新密码长度不能少于 6 位');
    return;
  }
  if (pwd !== resetPwdConfirm.value.trim()) {
    alert('两次输入的密码不一致');
    return;
  }
  if (!confirm(`确定要将用户「${resetTarget.value.username}」的密码重置为该新密码吗？`)) return;
  saving.value = true;
  try {
    const data = await store.resetUserPassword(resetTarget.value.id, { new_password: pwd });
    alert(data.message || '密码已重置');
    resetTarget.value = null;
  } catch (e: any) {
    alert(e.message);
  } finally {
    saving.value = false;
  }
};

const onCreate = async () => {
  saving.value = true;
  try {
    await store.createUser({ ...createForm.value });
    alert('用户已创建');
    showCreate.value = false;
  } catch (e: any) {
    alert(e.message);
  } finally {
    saving.value = false;
  }
};

onMounted(() => {
  if (!store.users.length) store.fetchUsers();
});
</script>

<style scoped>
.user-mgmt {
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
  gap: 10px;
  flex-wrap: wrap;
}
.search-box {
  display: flex;
  align-items: center;
  flex: 1 1 200px;
  min-width: 0;
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
  font-size: 0.9rem;
  color: var(--text-color);
  width: 100%;
  min-width: 0;
}
.clear-btn {
  border: none;
  background: transparent;
  color: var(--text-light);
  cursor: pointer;
  padding: 0;
  font-size: 0.95rem;
}
.clear-btn:hover {
  color: var(--text-color);
}
.search-spin {
  color: var(--primary-color);
  font-size: 0.85rem;
}
.retry-btn {
  margin-top: 12px;
}
.btn-secondary,
.btn-primary {
  margin: 0;
  border: 1px solid transparent;
  border-radius: 14px;
  padding: 8px 22px;
  min-width: 88px;
  min-height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1.2;
  font-weight: 600;
  cursor: pointer;
  box-sizing: border-box;
}
.btn-secondary {
  background: var(--white);
  color: var(--primary-color);
  border-color: var(--border-color, #e3eaf3);
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.08);
}
.btn-secondary:hover {
  background: #f0f6ff;
  transform: none;
}
.btn-primary {
  background: var(--primary-color);
  color: #fff;
  box-shadow: var(--shadow);
}
.btn-primary:hover:not(:disabled) {
  background: var(--primary-color);
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
.user-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}
.user-table th,
.user-table td {
  padding: 12px 14px;
  text-align: left;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  white-space: nowrap;
}
.user-table th {
  color: var(--text-light);
  font-weight: 700;
}
.cell-username {
  font-weight: 700;
  color: var(--text-color);
}
.cell-time {
  color: var(--text-light);
}
.role-badge {
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 0.78rem;
  font-weight: 600;
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
.status-badge {
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 0.78rem;
}
.status-on {
  background: #e7f6ec;
  color: #1f7a46;
}
.status-off {
  background: #fdeceb;
  color: #c0392b;
}
.status-lock {
  background: #fff5e6;
  color: #a5620e;
}
.col-actions {
  display: flex;
  gap: 8px;
}
.link-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  font-weight: 600;
  color: var(--primary-color);
}
.link-btn.danger {
  color: #c0392b;
}
.link-btn.success {
  color: #1f7a46;
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
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}
.modal {
  background: var(--white);
  border-radius: var(--border-radius);
  padding: 24px;
  width: 360px;
  max-width: 90vw;
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.modal h4 {
  color: var(--primary-color);
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 0.85rem;
  color: var(--text-color);
}
.field.row {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}
.field select,
.field input {
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 12px;
  padding: 8px 10px;
  font-size: 0.9rem;
  outline: none;
}
.warn {
  color: #d99a2b;
  font-size: 0.8rem;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 4px;
}

@media (max-width: 640px) {
  .toolbar {
    width: 100%;
  }
  .search-box {
    flex: 1 1 100%;
  }
  .toolbar .btn-primary {
    flex: 1 1 auto;
  }
  .user-table th,
  .user-table td {
    padding: 10px 12px;
  }
  .modal {
    padding: 18px;
  }
}
</style>
