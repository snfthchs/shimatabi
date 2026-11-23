import { Link } from 'react-router'

import type { Suggestion } from '../api/types'
import { formatYen } from '../lib/format'
import Photo from './Photo'
import SlotChips from './SlotChips'

// AI相談の提案カード。選んだ理由（DBの事実から、アプリが作ったもの）を見せる。
export default function SuggestionCard({ suggestion }: { suggestion: Suggestion }) {
  return (
    <article className="overflow-hidden rounded-2xl border border-brand-100 bg-white shadow-sm">
      <Link to={`/experiences/${suggestion.experience_id}`} className="flex gap-3 p-3">
        <Photo
          src={suggestion.photo_url}
          alt={suggestion.title}
          className="h-20 w-24 shrink-0 rounded-lg"
        />
        <div className="min-w-0 space-y-1">
          <h3 className="text-base font-bold text-slate-900">{suggestion.title}</h3>
          <p className="text-sm text-slate-700">
            <span className="font-bold">{formatYen(suggestion.price_yen)}</span>
            <span className="text-slate-500">／人</span>
          </p>
        </div>
      </Link>
      <p className="mx-3 rounded-lg bg-brand-50 px-3 py-2 text-xs leading-relaxed text-brand-900">
        {suggestion.reason}
      </p>
      <div className="p-3">
        <SlotChips experienceId={suggestion.experience_id} slots={suggestion.slots} />
      </div>
    </article>
  )
}
