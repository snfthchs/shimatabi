import { Link } from 'react-router'

import type { Slot } from '../api/types'
import { formatDateTime } from '../lib/format'

// 体験のカードに載せる、便の候補。押すと、その便を選んだ状態で、詳細の画面へ進む。
export default function SlotChips({ experienceId, slots }: { experienceId: number; slots: Slot[] }) {
  if (slots.length === 0) {
    return null
  }
  return (
    <ul className="flex flex-wrap gap-2" aria-label="予約できる便">
      {slots.map((slot) => (
        <li key={slot.id}>
          <Link
            to={`/experiences/${experienceId}?slot=${slot.id}`}
            className="flex min-h-11 flex-col justify-center rounded-lg border border-brand-200 bg-white px-3 text-sm text-brand-700 hover:bg-brand-50"
          >
            <span className="font-medium">{formatDateTime(slot.starts_at)}</span>
            <span className="text-xs text-slate-500">残り{slot.remaining}席</span>
          </Link>
        </li>
      ))}
    </ul>
  )
}
