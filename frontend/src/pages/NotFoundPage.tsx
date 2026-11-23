import { Link } from 'react-router'

export default function NotFoundPage() {
  return (
    <div className="space-y-3 py-8 text-center">
      <h1 className="text-lg font-bold text-slate-900">ページが見つかりません</h1>
      <p className="text-sm text-slate-600">URLが違うか、ページが移動した可能性があります。</p>
      <Link
        to="/"
        className="inline-flex min-h-11 items-center rounded-xl bg-teal-600 px-5 text-sm font-bold text-white"
      >
        トップへ戻る
      </Link>
    </div>
  )
}
