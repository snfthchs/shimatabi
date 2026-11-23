type Props = {
  label: string
  value: number
  min: number
  max: number
  onChange: (value: number) => void
  unit?: string
}

// 人数などを、＋と−のボタンで変える。ボタンは、指で押しやすい大きさにする。
export default function Stepper({ label, value, min, max, onChange, unit = '人' }: Props) {
  const buttonClass =
    'flex size-11 items-center justify-center rounded-full border border-slate-300 bg-white text-xl text-slate-700 disabled:opacity-40'
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm font-medium text-slate-800">{label}</span>
      <div className="flex items-center gap-3">
        <button
          type="button"
          className={buttonClass}
          aria-label={`${label}を1減らす`}
          disabled={value <= min}
          onClick={() => onChange(value - 1)}
        >
          −
        </button>
        <span className="min-w-12 text-center text-lg font-bold" aria-live="polite">
          {value}
          {unit}
        </span>
        <button
          type="button"
          className={buttonClass}
          aria-label={`${label}を1増やす`}
          disabled={value >= max}
          onClick={() => onChange(value + 1)}
        >
          ＋
        </button>
      </div>
    </div>
  )
}
