import { useEffect } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'

const navClass = ({ isActive }: { isActive: boolean }) =>
  `flex min-h-11 flex-1 items-center justify-center text-sm font-medium lg:flex-none lg:px-5 ${
    isActive ? 'border-b-2 border-teal-600 text-teal-700' : 'text-slate-500'
  }`

// スマホでは全幅の1列。PC幅（lg: 1024px以上）では、中央の枠（max-w-5xl）に広げ、ヘッダーとナビを横に並べる。
export default function Layout() {
  const { pathname } = useLocation()

  // ページを移動したときは、画面の一番上に戻す。
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return (
    <div className="min-h-screen bg-white">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-5xl lg:flex lg:items-center lg:justify-between lg:px-6">
          <div className="flex items-center justify-between px-4 py-3 lg:gap-4 lg:px-0">
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
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 pt-4 pb-8 lg:px-6 lg:pt-8 lg:pb-12">
        <Outlet />
      </main>
    </div>
  )
}
