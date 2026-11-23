import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router'

import { ApiError } from '../api/client'
import { useConcierge } from '../api/hooks'
import { ErrorNotice, InfoNotice, LoadingNotice } from '../components/Notices'
import SuggestionCard from '../components/SuggestionCard'
import { todayInJapan } from '../lib/format'

const EXAMPLES = [
  '今日の午後、那覇から行ける子連れOKの体験は？',
  '明日、雨でも楽しめる体験を教えて',
  'あさって、3人で海の体験がしたい',
]
const MAX_LENGTH = 500

// トップ。AIコンシェルジュに、自然な文章で相談できる（探す入口）。予約は、AIではなく、提案から詳細の画面へ進んで行う。
export default function HomePage() {
  const [message, setMessage] = useState('')
  const concierge = useConcierge()

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const text = message.trim()
    if (!text || concierge.isPending) {
      return
    }
    concierge.mutate(text)
  }

  // 候補があるときは、返答のうち、条件のまとめ（最初の行）と案内（最後の行）だけを見せる。
  // 候補ごとの詳細（理由・便）は、その下のカードに出るので、重複させない。
  const replyLines = concierge.data?.reply.split('\n') ?? []
  const hasSuggestions = (concierge.data?.suggestions.length ?? 0) > 0
  const shownReply = hasSuggestions
    ? [replyLines[0], replyLines[replyLines.length - 1]].join('\n')
    : replyLines.join('\n')

  const error = concierge.error
  const errorMessage =
    error instanceof ApiError && error.code === 'VALIDATION_ERROR'
      ? '文章を入力してください（500文字まで）。'
      : error?.message

  return (
    // スマホは縦に1列。PC幅では、左に入力と条件、右に結果を並べる。
    // 右の結果が高くなっても、左の行が引き伸ばされないよう、最後の行（1fr）に、余りの高さを受けさせる。
    <div className="grid gap-6 lg:grid-cols-2 lg:grid-rows-[auto_auto_auto_1fr] lg:gap-x-10">
      <section className="rounded-2xl border border-brand-100 bg-linear-to-br from-brand-50 to-white px-5 py-5 shadow-sm lg:col-start-1">
        <h1 className="text-xl font-bold text-brand-800">
          <span className="inline-block">沖縄の体験を、</span>
          <span className="inline-block">サクッと探して、予約。</span>
        </h1>
      </section>

      <form onSubmit={handleSubmit} className="space-y-3 lg:col-start-1">
        <label htmlFor="concierge-message" className="block text-sm font-medium text-slate-800">
          どんな体験を探していますか？
        </label>
        <textarea
          id="concierge-message"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          maxLength={MAX_LENGTH}
          rows={3}
          placeholder="例: 明日の午後、那覇から行ける子連れOKの体験は？"
          aria-describedby="concierge-notice"
          className="w-full rounded-xl border border-slate-300 px-3 py-2 text-base focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
        />
        <p id="concierge-notice" className="text-xs text-slate-500">
          氏名や電話番号など、個人情報は入力しないでください。（{message.length}/{MAX_LENGTH}文字）
        </p>
        <button
          type="submit"
          disabled={!message.trim() || concierge.isPending}
          className="min-h-12 w-full rounded-xl bg-brand-500 text-base font-bold text-white hover:bg-brand-600 disabled:bg-slate-300 disabled:text-slate-500"
        >
          {concierge.isPending ? '探しています…' : '探してもらう'}
        </button>
        <div className="flex flex-wrap gap-2" aria-label="相談の例">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => setMessage(example)}
              className="min-h-11 rounded-full border border-slate-300 bg-white px-3 text-left text-xs text-slate-700 hover:bg-slate-50"
            >
              {example}
            </button>
          ))}
        </div>
      </form>

      <div
        aria-live="polite"
        className="space-y-3 lg:col-start-2 lg:row-span-4 lg:row-start-1"
      >
        {!concierge.isPending && !concierge.data && !errorMessage && (
          <p className="hidden rounded-2xl border border-dashed border-slate-300 px-4 py-10 text-center text-sm text-slate-500 lg:block">
            相談すると、合う体験の提案が、ここに出ます。
          </p>
        )}
        {concierge.isPending && <LoadingNotice>AIが考えています…</LoadingNotice>}
        {errorMessage && <ErrorNotice>{errorMessage}</ErrorNotice>}
        {concierge.data && (
          <>
            {concierge.data.pii_masked && (
              <InfoNotice>
                電話番号やメールアドレスなどに見える文字列が含まれていたため、AIには送らずに、伏せて探しました。個人情報は入力しないでください。
              </InfoNotice>
            )}
            <p className="rounded-xl bg-brand-50 px-4 py-3 text-sm leading-relaxed whitespace-pre-line text-brand-950">
              {shownReply}
            </p>
            {concierge.data.suggestions.length > 0 && (
              <ul className="space-y-3">
                {concierge.data.suggestions.map((suggestion) => (
                  <li key={suggestion.experience_id}>
                    <SuggestionCard suggestion={suggestion} />
                  </li>
                ))}
              </ul>
            )}
            {concierge.data.suggestions.length === 0 && (
              <InfoNotice>
                条件を変えて、もう一度相談するか、下の「条件から探す」や「体験を探す」をお試しください。
              </InfoNotice>
            )}
          </>
        )}
      </div>

      <section className="space-y-2 lg:col-start-1">
        <h2 className="text-sm font-bold text-slate-800">条件から探す</h2>
        <div className="flex flex-wrap gap-2">
          <Link to="/experiences?kids_ok=true" className={shortcutClass}>
            👶 子連れOK
          </Link>
          <Link to="/experiences?rain_ok=true" className={shortcutClass}>
            ☔ 雨でもOK
          </Link>
          <Link to={`/experiences?date=${todayInJapan()}`} className={shortcutClass}>
            📅 今日
          </Link>
          <Link to="/experiences" className={shortcutClass}>
            すべての体験 →
          </Link>
        </div>
      </section>
    </div>
  )
}

const shortcutClass =
  'flex min-h-11 items-center rounded-full border border-brand-200 bg-white px-4 text-sm font-medium text-brand-700 hover:bg-brand-50'
