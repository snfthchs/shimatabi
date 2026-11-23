import { useEffect } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'

const navClass = ({ isActive }: { isActive: boolean }) =>
  `flex min-h-11 flex-1 items-center justify-center text-sm font-medium ${
    isActive ? 'border-b-2 border-teal-600 text-teal-700' : 'text-slate-500'
  }`

// スマホで使いやすい幅（max-w-md）の列。PCでは、中央に細く表示する。
export default function Layout() {
  const { pathname } = useLocation()

  // ページを移動したときは、画面の一番上に戻す。
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return (
    <div className="mx-auto min-h-screen max-w-md bg-white shadow-sm">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white">
        <div className="flex items-center justify-between px-4 py-3">
          <Link to="/" className="text-lg font-bold text-teal-700">
            🌺 シマタビ
          </Link>
          <span className="text-xs text-slate-500">沖縄の体験予約（仮）</span>
        </div>
        <nav className="flex" aria-label="メニュー">
          <NavLink to="/" end className={navClass}>
            相談する
          </NavLink>
          <NavLink to="/experiences" className={navClass}>
            体験を探す
          </NavLink>
          <NavLink to="/bookings/lookup" className={navClass}>
            予約の確認
          </NavLink>
        </nav>
      </header>
      <main className="px-4 pt-4 pb-8">
        <Outlet />
      </main>
    </div>
  )
}
