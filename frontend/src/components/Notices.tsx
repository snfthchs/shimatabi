import type { ReactNode } from 'react'

// エラーの表示。画面読み上げでも、すぐ伝わるよう、role="alert" にする。
export function ErrorNotice({ children }: { children: ReactNode }) {
  return (
    <div
      role="alert"
      className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
    >
      {children}
    </div>
  )
}

// 読み込み中の表示。
export function LoadingNotice({ children = '読み込み中…' }: { children?: ReactNode }) {
  return (
    <p role="status" className="py-6 text-center text-sm text-slate-500">
      {children}
    </p>
  )
}

// 補足の説明（注意書きなど）。
export function InfoNotice({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-xl bg-slate-50 px-4 py-3 text-sm leading-relaxed text-slate-600">
      {children}
    </p>
  )
}
