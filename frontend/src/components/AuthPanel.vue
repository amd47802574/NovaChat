<template>
  <section class="auth-shell">
    <div class="auth-intro">
      <div class="auth-orbit" aria-hidden="true">
        <span class="orbit-ring orbit-ring-one"></span>
        <span class="orbit-ring orbit-ring-two"></span>
        <span class="orbit-core"
          ><i class="fas fa-wand-magic-sparkles"></i
        ></span>
      </div>
      <div class="auth-intro-copy">
        <span class="auth-eyebrow">NOVA INTELLIGENCE</span>
        <h1>让知识连接，<br />让答案发生。</h1>
        <p>融合智能检索、可信引用与多轮对话，为你的每一次探索提供清晰答案。</p>
        <div class="auth-capabilities">
          <span><i class="fas fa-bolt"></i> 智能检索</span>
          <span><i class="fas fa-link"></i> 溯源引用</span>
          <span><i class="fas fa-layer-group"></i> 知识管理</span>
        </div>
        <a
          class="auth-github-link"
          href="https://github.com/amd47802574/NovaChat"
          target="_blank"
          rel="noopener noreferrer"
          title="GitHub 仓库"
        >
          <i class="fab fa-github"></i>
          <span>在 GitHub 上查看项目</span>
        </a>
      </div>
    </div>

    <div class="auth-panel">
      <div class="auth-panel-heading">
        <span class="auth-panel-kicker">{{
          authStore.authMode === 'login' ? 'WELCOME BACK' : 'CREATE ACCOUNT'
        }}</span>
        <h2>
          {{ authStore.authMode === 'login' ? '登录星智问答' : '注册星智问答' }}
        </h2>
        <p>
          {{
            authStore.authMode === 'login'
              ? '继续进入你的智能知识工作区'
              : '创建账号，开启智能问答体验'
          }}
        </p>
      </div>

      <!-- 接口级错误 / 成功反馈 -->
      <div
        v-if="formError"
        class="auth-alert auth-alert-error"
        role="alert"
        aria-live="assertive"
      >
        <i class="fas fa-circle-exclamation" aria-hidden="true"></i>
        <span>{{ formError }}</span>
      </div>
      <div
        v-if="formNotice"
        class="auth-alert auth-alert-info"
        role="status"
        aria-live="polite"
      >
        <i class="fas fa-circle-info" aria-hidden="true"></i>
        <span>{{ formNotice }}</span>
      </div>

      <form class="auth-form" novalidate @submit.prevent="onSubmit">
        <div class="auth-field">
          <label class="auth-field-label" for="auth-username">用户名</label>
          <div
            class="auth-input-wrap"
            :class="{ 'auth-input-invalid': !!fieldErrors.username }"
          >
            <i class="fas fa-user" aria-hidden="true"></i>
            <input
              id="auth-username"
              ref="usernameInput"
              v-model="authStore.authForm.username"
              type="text"
              name="username"
              placeholder="请输入用户名"
              autocomplete="username"
              :aria-invalid="!!fieldErrors.username"
              :aria-describedby="
                fieldErrors.username ? 'auth-username-error' : undefined
              "
              @blur="validateField('username')"
              @input="fieldErrors.username && validateField('username')"
            />
          </div>
          <p
            v-if="fieldErrors.username"
            id="auth-username-error"
            class="auth-field-error"
          >
            {{ fieldErrors.username }}
          </p>
        </div>

        <div class="auth-field">
          <div class="auth-field-row">
            <label class="auth-field-label" for="auth-password">密码</label>
            <button
              v-if="authStore.authMode === 'login'"
              type="button"
              class="auth-forgot"
              @click="showForgotHint"
            >
              忘记密码？
            </button>
          </div>
          <div
            class="auth-input-wrap"
            :class="{ 'auth-input-invalid': !!fieldErrors.password }"
          >
            <i class="fas fa-lock" aria-hidden="true"></i>
            <input
              id="auth-password"
              v-model="authStore.authForm.password"
              :type="showPassword ? 'text' : 'password'"
              name="password"
              placeholder="请输入密码"
              :autocomplete="
                authStore.authMode === 'login'
                  ? 'current-password'
                  : 'new-password'
              "
              :aria-invalid="!!fieldErrors.password"
              :aria-describedby="
                fieldErrors.password ? 'auth-password-error' : undefined
              "
              @blur="validateField('password')"
              @input="fieldErrors.password && validateField('password')"
            />
            <button
              type="button"
              class="auth-toggle-password"
              :aria-label="showPassword ? '隐藏密码' : '显示密码'"
              :aria-pressed="showPassword"
              @click="showPassword = !showPassword"
            >
              <i
                class="fas"
                :class="showPassword ? 'fa-eye-slash' : 'fa-eye'"
                aria-hidden="true"
              ></i>
            </button>
          </div>
          <p
            v-if="fieldErrors.password"
            id="auth-password-error"
            class="auth-field-error"
          >
            {{ fieldErrors.password }}
          </p>
        </div>

        <div
          v-if="authStore.authMode === 'register'"
          class="auth-field"
        >
          <label class="auth-field-label" for="auth-confirm-password"
            >确认密码</label
          >
          <div
            class="auth-input-wrap"
            :class="{ 'auth-input-invalid': !!fieldErrors.confirmPassword }"
          >
            <i class="fas fa-lock" aria-hidden="true"></i>
            <input
              id="auth-confirm-password"
              v-model="authStore.authForm.confirm_password"
              :type="showPassword ? 'text' : 'password'"
              name="confirm_password"
              placeholder="请再次输入密码"
              autocomplete="new-password"
              :aria-invalid="!!fieldErrors.confirmPassword"
              :aria-describedby="
                fieldErrors.confirmPassword
                  ? 'auth-confirm-password-error'
                  : undefined
              "
              @blur="validateField('confirmPassword')"
              @input="
                fieldErrors.confirmPassword && validateField('confirmPassword')
              "
            />
            <button
              type="button"
              class="auth-toggle-password"
              :aria-label="showPassword ? '隐藏密码' : '显示密码'"
              :aria-pressed="showPassword"
              @click="showPassword = !showPassword"
            >
              <i
                class="fas"
                :class="showPassword ? 'fa-eye-slash' : 'fa-eye'"
                aria-hidden="true"
              ></i>
            </button>
          </div>
          <p
            v-if="fieldErrors.confirmPassword"
            id="auth-confirm-password-error"
            class="auth-field-error"
          >
            {{ fieldErrors.confirmPassword }}
          </p>
        </div>

        <div
          v-if="authStore.authMode === 'register'"
          class="auth-field"
        >
          <label class="auth-field-label" for="auth-role">账号类型</label>
          <div class="auth-input-wrap">
            <i class="fas fa-id-badge" aria-hidden="true"></i>
            <select id="auth-role" v-model="authStore.authForm.role">
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
              <option value="super_admin">超级管理员</option>
            </select>
          </div>
        </div>

        <div
          v-if="
            authStore.authMode === 'register' &&
            (authStore.authForm.role === 'admin' ||
              authStore.authForm.role === 'super_admin')
          "
          class="auth-field"
        >
          <label class="auth-field-label" for="auth-admin-code">
            {{
              authStore.authForm.role === 'super_admin'
                ? '超级管理员邀请码'
                : '管理员邀请码'
            }}
          </label>
          <div
            class="auth-input-wrap"
            :class="{ 'auth-input-invalid': !!fieldErrors.adminCode }"
          >
            <i class="fas fa-key" aria-hidden="true"></i>
            <input
              id="auth-admin-code"
              v-model="authStore.authForm.admin_code"
              :type="showPassword ? 'text' : 'password'"
              :placeholder="
                authStore.authForm.role === 'super_admin'
                  ? '请输入超级管理员邀请码'
                  : '请输入管理员邀请码'
              "
              autocomplete="off"
              :aria-invalid="!!fieldErrors.adminCode"
              :aria-describedby="
                fieldErrors.adminCode ? 'auth-admin-code-error' : undefined
              "
              @blur="validateField('adminCode')"
            />
          </div>
          <p
            v-if="fieldErrors.adminCode"
            id="auth-admin-code-error"
            class="auth-field-error"
          >
            {{ fieldErrors.adminCode }}
          </p>
        </div>

        <div
          v-if="
            authStore.authMode === 'register' &&
            authStore.authForm.role === 'super_admin'
          "
          class="auth-alert auth-alert-info auth-role-hint"
          role="note"
        >
          <i class="fas fa-shield-halved" aria-hidden="true"></i>
          <span>
            超级管理员用于平台全局治理（数据面板 / 用户管理 / 安全审计）。
            公开注册需填写正确的邀请码；若服务端未配置公开邀请码，
            请联系已有超级管理员在「超级管理后台 → 用户管理」中为你创建账号。
          </span>
        </div>

        <button
          type="submit"
          class="send-btn auth-submit"
          :class="{ 'auth-submit-loading': authStore.authLoading }"
          :disabled="authStore.authLoading"
        >
          <span>{{
            authStore.authLoading
              ? '正在验证...'
              : authStore.authMode === 'login'
                ? '进入工作区'
                : '创建账号'
          }}</span>
          <i
            v-if="authStore.authLoading"
            class="fas fa-circle-notch auth-spinner"
            aria-hidden="true"
          ></i>
          <i v-else class="fas fa-arrow-right" aria-hidden="true"></i>
        </button>

        <button type="button" class="auth-switch" @click="toggleAuthMode">
          {{
            authStore.authMode === 'login'
              ? '还没有账号？立即注册'
              : '已有账号？返回登录'
          }}
        </button>
      </form>
      <div class="auth-footer">
        <a
          class="icp-link"
          href="https://beian.miit.gov.cn/"
          target="_blank"
          rel="noopener noreferrer"
          >赣ICP备2026017220号</a
        >
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
  import { reactive, ref } from 'vue'
  import { useAuthStore } from '@/stores/auth'
  import { useChatStore } from '@/stores/chat'
  import { useSessionStore } from '@/stores/sessions'

  const authStore = useAuthStore()
  const chatStore = useChatStore()
  const sessionStore = useSessionStore()

  const showPassword = ref(false)
  const formError = ref('')
  const formNotice = ref('')
  const usernameInput = ref<HTMLInputElement | null>(null)
  const fieldErrors = reactive({
    username: '',
    password: '',
    confirmPassword: '',
    adminCode: '',
  })

  // 与密码相同的格式 / 强度规则：必填且至少 6 位字符
  const getPasswordStrengthError = (value: string): string => {
    if (!value) return '请输入密码'
    if (value.length < 6) return '密码至少需要 6 位字符'
    return ''
  }

  const validateField = (
    field: 'username' | 'password' | 'confirmPassword' | 'adminCode',
  ) => {
    if (field === 'username') {
      const username = authStore.authForm.username.trim()
      if (!username) {
        fieldErrors.username = '请输入用户名'
      } else if (/\s/.test(username)) {
        fieldErrors.username = '用户名不能包含空格'
      } else if (username.length < 2 || username.length > 32) {
        fieldErrors.username = '用户名长度需在 2-32 个字符之间'
      } else {
        fieldErrors.username = ''
      }
    } else if (field === 'password') {
      const password = authStore.authForm.password
      fieldErrors.password = getPasswordStrengthError(password)
      // 密码变化时，重新校验确认密码以避免“不一致”残留
      if (authStore.authMode === 'register' && fieldErrors.confirmPassword) {
        validateField('confirmPassword')
      }
    } else if (field === 'confirmPassword') {
      if (authStore.authMode !== 'register') {
        fieldErrors.confirmPassword = ''
      } else {
        const confirm = authStore.authForm.confirm_password
        if (!confirm) {
          fieldErrors.confirmPassword = '请再次输入密码'
        } else {
          const strengthError = getPasswordStrengthError(confirm)
          if (strengthError) {
            fieldErrors.confirmPassword = strengthError.replace('密码', '确认密码')
          } else if (confirm !== authStore.authForm.password) {
            fieldErrors.confirmPassword = '两次输入的密码不一致'
          } else {
            fieldErrors.confirmPassword = ''
          }
        }
      }
    } else if (field === 'adminCode') {
      const needsCode =
        authStore.authMode === 'register' &&
        (authStore.authForm.role === 'admin' ||
          authStore.authForm.role === 'super_admin') &&
        !authStore.authForm.admin_code.trim()
      if (needsCode) {
        fieldErrors.adminCode =
          authStore.authForm.role === 'super_admin'
            ? '请输入超级管理员邀请码'
            : '请输入管理员邀请码'
      } else {
        fieldErrors.adminCode = ''
      }
    }
    return !fieldErrors[field]
  }

  const validateAll = () => {
    const results = [
      validateField('username'),
      validateField('password'),
      validateField('adminCode'),
    ]
    if (authStore.authMode === 'register') {
      results.push(validateField('confirmPassword'))
    }
    return results.every(Boolean)
  }

  const toggleAuthMode = () => {
    authStore.authMode = authStore.authMode === 'login' ? 'register' : 'login'
    formError.value = ''
    formNotice.value = ''
    fieldErrors.username = ''
    fieldErrors.password = ''
    fieldErrors.confirmPassword = ''
    fieldErrors.adminCode = ''
    authStore.authForm.confirm_password = ''
    showPassword.value = false
  }

  const showForgotHint = () => {
    formNotice.value = '请联系管理员重置密码，或使用注册邮箱重新找回账号。'
  }

  const onSubmit = async () => {
    formError.value = ''
    formNotice.value = ''
    if (!validateAll()) {
      formError.value = '请先修正表单中标出的错误'
      usernameInput.value?.focus()
      return
    }

    try {
      await authStore.handleAuthSubmit()
      // 超级管理员为纯治理角色，不进入对话功能，跳过会话恢复。
      if (!authStore.isSuperAdmin) {
        try {
          await sessionStore.fetchSessions()
          chatStore.mergeCachedSessionsIntoHistory()
        } catch (_) {
          // 历史列表加载失败不影响恢复当前会话内容。
        }
        try {
          await chatStore.restoreLastSession()
        } catch (_) {
          // 恢复上次会话失败不影响进入工作区。
        }
      }
    } catch (error: any) {
      formError.value = error.message || '认证失败，请稍后重试'
    }
  }
</script>
