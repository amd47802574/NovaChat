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
            placeholder="按用户名检索"
            @keyup.enter="onSearch"
          />
        </div>
        <button class="btn-secondary" @click="onSearch"><i class="fas fa-search"></i> 检索</button>
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
        <i class="fas fa-user-slash"></i>
        <p>没有匹配的用户</p>
      </div>
    </template>

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
import { computed, onMounted, ref } from 'vue';
import { useSuperAdminStore, ROLE_LABELS } from '@/stores/superAdmin';
import { useAuthStore } from '@/stores/auth';
import type { AdminUserItem, UserRole } from '@/types/user';

const store = useSuperAdminStore();
const authStore = useAuthStore();

const searchInput = ref('');
const editTarget = ref<AdminUserItem | null>(null);
const editRole = ref<UserRole>('user');
const editActive = ref(true);
const showCreate = ref(false);
const saving = ref(false);
const createForm = ref({ username: '', password: '', role: 'user' as UserRole, is_active: true });

const totalPages = computed(() => Math.max(1, Math.ceil(store.usersTotal / store.usersPageSize)));
const selfEditWarn = computed(
  () => editTarget.value?.username === authStore.currentUser?.username && (editRole.value !== 'super_admin' || !editActive.value)
);

const roleLabel = (role: string) => ROLE_LABELS[role as UserRole] || role;

const formatTime = (iso: string | null) => {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
};

const onSearch = () => store.setUsersSearch(searchInput.value);

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
.btn-secondary,
.btn-primary {
  border: none;
  border-radius: 14px;
  padding: 8px 14px;
  font-weight: 600;
  cursor: pointer;
}
.btn-secondary {
  background: var(--white);
  color: var(--primary-color);
  border: 1px solid var(--border-color, #e3eaf3);
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.08);
}
.btn-primary {
  background: var(--primary-color);
  color: #fff;
  box-shadow: var(--shadow);
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
  .toolbar .btn-secondary,
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
