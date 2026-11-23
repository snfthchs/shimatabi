import { statusLabels } from '../lib/format'

const statusClass: Record<string, string> = {
  confirmed: 'bg-emerald-100 text-emerald-900',
  pending: 'bg-amber-100 text-amber-900',
  rejected: 'bg-slate-200 text-slate-800',
  cancelled: 'bg-slate-200 text-slate-800',
}

// 予約の状態（確定、承認待ちなど）。色だけでなく、文字でも区別できる。
export default function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-block rounded-full px-3 py-1 text-sm font-bold ${statusClass[status] ?? 'bg-slate-100 text-slate-800'}`}
    >
      {statusLabels[status] ?? status}
    </span>
  )
}
