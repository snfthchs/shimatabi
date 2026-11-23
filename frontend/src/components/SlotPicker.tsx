import type { Slot } from '../api/types'
import { formatDate, formatTime } from '../lib/format'

type Props = {
  slots: Slot[]
  value: number | null
  onChange: (slotId: number) => void
  error?: string
}

// 便の選択。満席の便は、選べない（「満席」と表示する）。日付ごとにまとめる。
export default function SlotPicker({ slots, value, onChange, error }: Props) {
  if (slots.length === 0) {
    return <p className="text-sm text-slate-500">いま予約できる便はありません。</p>
  }

  const byDate = new Map<string, Slot[]>()
  for (const slot of slots) {
    const date = formatDate(slot.starts_at)
    byDate.set(date, [...(byDate.get(date) ?? []), slot])
  }

  return (
    <fieldset aria-describedby={error ? 'slot-error' : undefined}>
      <legend className="sr-only">便を選ぶ</legend>
      <div className="space-y-3">
        {[...byDate.entries()].map(([date, daySlots]) => (
          <div key={date}>
            <p className="mb-1 text-xs font-medium text-slate-500">{date}</p>
            <div className="grid grid-cols-2 gap-2">
              {daySlots.map((slot) => {
                const selected = value === slot.id
                return (
                  <label
                    key={slot.id}
                    className={`flex min-h-14 cursor-pointer flex-col justify-center rounded-lg border px-3 py-1 text-sm ${
                      slot.is_full
                        ? 'cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400'
                        : selected
                          ? 'border-teal-600 bg-teal-50 ring-2 ring-teal-600'
                          : 'border-slate-300 bg-white hover:bg-slate-50'
                    }`}
                  >
                    <input
                      type="radio"
                      name="slot"
                      className="sr-only"
                      value={slot.id}
                      aria-label={`${date} ${formatTime(slot.starts_at)} ${
                        slot.is_full ? '満席' : `残り${slot.remaining}席`
                      }`}
                      checked={selected}
                      disabled={slot.is_full}
                      onChange={() => onChange(slot.id)}
                    />
                    <span className="font-bold">{formatTime(slot.starts_at)}</span>
                    <span className="text-xs">
                      {slot.is_full ? '満席' : `残り${slot.remaining}席`}
                    </span>
                  </label>
                )
              })}
            </div>
          </div>
        ))}
      </div>
      {error && (
        <p id="slot-error" role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </fieldset>
  )
}
