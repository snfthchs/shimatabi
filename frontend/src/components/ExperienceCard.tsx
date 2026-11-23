import { Link } from 'react-router'

import type { ExperienceListItem } from '../api/types'
import { categoryLabels, formatYen } from '../lib/format'
import { ExperienceBadges } from './Badges'
import Photo from './Photo'
import SlotChips from './SlotChips'

// 体験の一覧に出す、カード。
export default function ExperienceCard({ experience }: { experience: ExperienceListItem }) {
  return (
    <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <Link to={`/experiences/${experience.id}`} className="block">
        <Photo src={experience.photo_url} alt={experience.title} className="aspect-video w-full" />
        <div className="space-y-2 p-3">
          <p className="text-xs text-slate-500">
            {categoryLabels[experience.category] ?? experience.category}・{experience.area}・
            {experience.business_name}
          </p>
          <h2 className="text-base font-bold text-slate-900">{experience.title}</h2>
          <p className="line-clamp-2 text-sm text-slate-600">{experience.summary}</p>
          <ExperienceBadges experience={experience} />
          <p className="text-sm text-slate-700">
            <span className="font-bold">{formatYen(experience.price_yen)}</span>
            <span className="text-slate-500">／人・約{experience.duration_minutes}分</span>
          </p>
        </div>
      </Link>
      <div className="px-3 pb-3">
        <SlotChips experienceId={experience.id} slots={experience.slots} />
      </div>
    </article>
  )
}
