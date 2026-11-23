import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router'

import { useLogin } from '../api/adminHooks'
import { ApiError } from '../api/client'
import { ErrorNotice } from '../components/Notices'
import TextField from '../components/TextField'

// 事業者のログイン。ログインIDとパスワードのどちらが違うかは、伝えない。
export default function AdminLoginPage() {
  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')
  const login = useLogin()
  const navigate = useNavigate()

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!loginId.trim() || !password || login.isPending) {
      return
    }
    login.mutate(
      { login_id: loginId.trim(), password },
      { onSuccess: () => navigate('/admin/bookings', { replace: true }) },
    )
  }

  const error = login.error
  const errorMessage =
    error instanceof ApiError && (error.status === 401 || error.status === 422)
      ? 'ログインIDまたはパスワードが違います。'
      : error?.message

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <div>
          <p className="text-lg font-bold text-brand-700">🌺 シマタビ</p>
          <h1 className="text-xl font-bold text-slate-900">事業者のログイン</h1>
        </div>
        {errorMessage && <ErrorNotice>{errorMessage}</ErrorNotice>}
        <TextField
          id="login-id"
          label="ログインID"
          value={loginId}
          onChange={(event) => setLoginId(event.target.value)}
          maxLength={50}
          autoComplete="username"
          autoCapitalize="none"
        />
        <TextField
          id="password"
          label="パスワード"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          maxLength={200}
          autoComplete="current-password"
        />
        <button
          type="submit"
          disabled={!loginId.trim() || !password || login.isPending}
          className="min-h-12 w-full rounded-xl bg-brand-500 text-base font-bold text-white hover:bg-brand-600 disabled:bg-slate-300 disabled:text-slate-500"
        >
          {login.isPending ? 'ログインしています…' : 'ログイン'}
        </button>
      </form>
    </div>
  )
}
