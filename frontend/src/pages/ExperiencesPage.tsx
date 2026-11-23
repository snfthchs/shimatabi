import type { ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router'

import type { ExperienceFilters } from '../api/hooks'
import { useExperiences } from '../api/hooks'
import type { Category } from '../api/types'
import ExperienceCard from '../components/ExperienceCard'
import { ErrorNotice, InfoNotice, LoadingNotice } from '../components/Notices'
import Stepper from '../components/Stepper'
import { areaOptions, categoryLabels, todayInJapan } from '../lib/format'

const CATEGORIES = Object.keys(categoryLabels) as Category[]
const MAX_PARTY_SIZE = 10

function parseCategory(value: string | null): Category | undefined {
  return CATEGORIES.find((category) => category === value)
}

function parsePartySize(value: string | null): number | undefined {
  const size = Number(value)
  return Number.isInteger(size) && size >= 1 && size <= MAX_PARTY_SIZE ? size : undefined
}

function FilterToggle({
  pressed,
  onClick,
  children,
}: {
  pressed: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={`min-h-11 rounded-full border px-4 text-sm font-medium ${
        pressed
          ? 'border-brand-500 bg-brand-500 text-white'
          : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
      }`}
    >
      {children}
    </button>
  )
}

// 体験の一覧と、絞り込み。絞り込みの条件は、URLに入れる（共有でき、戻るボタンでも戻れる）。
export default function ExperiencesPage() {
  const [params, setParams] = useSearchParams()

  const filters: ExperienceFilters = {
    date: params.get('date') ?? undefined,
    party_size: parsePartySize(params.get('party_size')),
    kids_ok: params.get('kids_ok') === 'true' ? true : undefined,
    rain_ok: params.get('rain_ok') === 'true' ? true : undefined,
    area: params.get('area') ?? undefined,
    category: parseCategory(params.get('category')),
  }
  const hasFilters = Object.values(filters).some((value) => value !== undefined)
  const query = useExperiences(filters)

  function update(key: string, value: string | null) {
    const next = new URLSearchParams(params)
    if (value === null || value === '') {
      next.delete(key)
    } else {
      next.set(key, value)
    }
    setParams(next, { replace: true })
  }

  const inputClass =
    'min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-base focus:outline-2 focus:outline-offset-1 focus:outline-brand-600'

  return (
    // スマホは縦に1列。PC幅では、左に絞り込み、右に一覧を並べる。
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-900">体験を探す</h1>

      <div className="space-y-4 lg:grid lg:grid-cols-[16rem_1fr] lg:items-start lg:gap-8 lg:space-y-0">
      <section
        aria-label="絞り込み"
        className="space-y-3 rounded-2xl bg-slate-50 p-3 lg:sticky lg:top-32"
      >
        <div className="flex flex-wrap gap-2">
          <FilterToggle
            pressed={filters.kids_ok === true}
            onClick={() => update('kids_ok', filters.kids_ok ? null : 'true')}
          >
            👶 子連れOK
          </FilterToggle>
          <FilterToggle
            pressed={filters.rain_ok === true}
            onClick={() => update('rain_ok', filters.rain_ok ? null : 'true')}
          >
            ☔ 雨でもOK
          </FilterToggle>
        </div>

        <div>
          <label htmlFor="filter-date" className="mb-1 block text-xs font-medium text-slate-600">
            日にち
          </label>
          <input
            id="filter-date"
            type="date"
            min={todayInJapan()}
            value={filters.date ?? ''}
            onChange={(event) => update('date', event.target.value)}
            className={inputClass}
          />
        </div>

        <Stepper
          label="人数"
          value={filters.party_size ?? 1}
          min={1}
          max={MAX_PARTY_SIZE}
          onChange={(size) => update('party_size', size === 1 ? null : String(size))}
        />

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label htmlFor="filter-area" className="mb-1 block text-xs font-medium text-slate-600">
              エリア
            </label>
            <select
              id="filter-area"
              value={filters.area ?? ''}
              onChange={(event) => update('area', event.target.value)}
              className={inputClass}
            >
              <option value="">すべて</option>
              {areaOptions.map((area) => (
                <option key={area} value={area}>
                  {area}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label
              htmlFor="filter-category"
              className="mb-1 block text-xs font-medium text-slate-600"
            >
              種類
            </label>
            <select
              id="filter-category"
              value={filters.category ?? ''}
              onChange={(event) => update('category', event.target.value)}
              className={inputClass}
            >
              <option value="">すべて</option>
              {CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {categoryLabels[category]}
                </option>
              ))}
            </select>
          </div>
        </div>

        {hasFilters && (
          <Link
            to="/experiences"
            replace
            className="flex min-h-11 items-center justify-center text-sm text-brand-700 underline"
          >
            条件をリセット
          </Link>
        )}
      </section>

      <div aria-live="polite">
        {query.isPending && <LoadingNotice />}
        {query.isError && <ErrorNotice>{query.error.message}</ErrorNotice>}
        {query.data && query.data.length === 0 && (
          <InfoNotice>
            条件に合う体験は、見つかりませんでした。条件を減らして、もう一度お試しください。
          </InfoNotice>
        )}
        {query.data && query.data.length > 0 && (
          <div className="space-y-3">
            <p className="text-sm text-slate-600">{query.data.length}件の体験</p>
            <ul className="grid gap-4 sm:grid-cols-2">
              {query.data.map((experience) => (
                <li key={experience.id}>
                  <ExperienceCard experience={experience} />
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      </div>
    </div>
  )
}
