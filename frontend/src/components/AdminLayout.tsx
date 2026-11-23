import { Navigate, Outlet, useNavigate } from 'react-router'

import { isUnauthenticated, useLogout, useMe } from '../api/adminHooks'
import { ErrorNotice, LoadingNotice } from './Notices'

// 事業者の画面の枠。PC幅を基本にする。未ログインのときは、ログインの画面へ戻す。
export default function AdminLayout() {
  const me = useMe()
  const logout = useLogout()
  const navigate = useNavigate()

  if (me.isPending) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-10">
        <LoadingNotice />
      </div>
    )
  }
  if (isUnauthenticated(me.error)) {
    return <Navigate to="/admin/login" replace />
  }
  if (me.isError) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-10">
        <ErrorNotice>{me.error.message}</ErrorNotice>
      </div>
    )
  }

  function handleLogout() {
    logout.mutate(undefined, {
      onSettled: () => navigate('/admin/login', { replace: true }),
    })
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <div>
            <p className="text-lg font-bold text-teal-700">🌺 シマタビ 事業者の管理</p>
            <p className="text-sm text-slate-600">
              {me.data.business.name}（{me.data.business.area}）
            </p>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            disabled={logout.isPending}
            className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          >
            ログアウト
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
