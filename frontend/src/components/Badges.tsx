import type { ReactNode } from 'react'

type Tone = 'teal' | 'sky' | 'amber' | 'slate'

const toneClass: Record<Tone, string> = {
  teal: 'bg-teal-50 text-teal-800 ring-teal-200',
  sky: 'bg-sky-50 text-sky-800 ring-sky-200',
  amber: 'bg-amber-50 text-amber-900 ring-amber-200',
  slate: 'bg-slate-50 text-slate-700 ring-slate-200',
}

export function Badge({ tone = 'slate', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${toneClass[tone]}`}
    >
      {children}
    </span>
  )
}

type BadgeSource = {
  kids_ok?: boolean
  min_age?: number | null
  rain_ok?: boolean
  confirmation_mode: string
  minutes_from_naha?: number
}

// 体験の特徴を、アイコンと短い文字で見せる（子連れ可、雨天可、確定方式、那覇からの時間）。
export function ExperienceBadges({ experience }: { experience: BadgeSource }) {
  const minAge = experience.min_age
  return (
    <div className="flex flex-wrap gap-1.5">
      {experience.kids_ok && (
        <Badge tone="teal">👶 子連れOK{minAge ? `（${minAge}歳〜）` : ''}</Badge>
      )}
      {experience.rain_ok && <Badge tone="sky">☔ 雨でもOK</Badge>}
      {experience.confirmation_mode === 'instant' ? (
        <Badge tone="slate">⚡ すぐ確定</Badge>
      ) : (
        <Badge tone="amber">📝 承認制</Badge>
      )}
      {experience.minutes_from_naha !== undefined && (
        <Badge tone="slate">🚗 那覇から約{experience.minutes_from_naha}分</Badge>
      )}
    </div>
  )
}
