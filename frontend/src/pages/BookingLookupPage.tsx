import { useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError } from '../api/client'
import { useLookupBooking } from '../api/hooks'
import { ErrorNotice, InfoNotice } from '../components/Notices'
import StatusBadge from '../components/StatusBadge'
import TextField from '../components/TextField'
import { formatDateTime, statusDescription } from '../lib/format'
import type { FieldErrors } from '../lib/validation'
import { serverFieldErrors } from '../lib/validation'

// 予約の確認。ログインは不要で、予約番号と、予約のときの連絡先（電話またはメール）で確かめる。
// 連絡先は個人情報なので、URLには入れず、ブラウザにも保存しない。
export default function BookingLookupPage() {
  const [number, setNumber] = useState('')
  const [contact, setContact] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const lookup = useLookupBooking()

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const found: FieldErrors = {}
    if (!number.trim()) {
      found.number = '予約番号を入力してください。'
    }
    if (!contact.trim()) {
      found.contact = '電話番号またはメールアドレスを入力してください。'
    }
    setErrors(found)
    if (Object.keys(found).length > 0) {
      return
    }
    lookup.mutate(
      { booking_number: number, contact },
      {
        onError: (error) => {
          if (error instanceof ApiError && error.code === 'VALIDATION_ERROR') {
            setErrors(serverFieldErrors(error.details))
          }
        },
      },
    )
  }

  const error = lookup.error
  const notFound = error instanceof ApiError && error.status === 404
  const otherError = error && !notFound && !(error instanceof ApiError && error.status === 422)

  return (
    <div className="space-y-5">
      <section className="space-y-1">
        <h1 className="text-xl font-bold text-slate-900">予約の確認</h1>
        <p className="text-sm text-slate-600">
          予約番号と、予約のときに入力した電話番号またはメールアドレスで、予約の状態を確認できます。
        </p>
      </section>

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <TextField
          id="lookup-number"
          label="予約番号"
          value={number}
          onChange={(event) => setNumber(event.target.value)}
          error={errors.number}
          hint="予約が完了したときに表示された、10文字の番号です。"
          autoCapitalize="characters"
          autoComplete="off"
          spellCheck={false}
        />
        <TextField
          id="lookup-contact"
          label="電話番号またはメールアドレス"
          value={contact}
          onChange={(event) => setContact(event.target.value)}
          error={errors.contact}
          hint="予約のときに入力したものを、入力してください。"
          autoComplete="off"
          spellCheck={false}
        />
        <button
          type="submit"
          disabled={lookup.isPending}
          className="min-h-12 w-full rounded-xl bg-teal-600 text-base font-bold text-white hover:bg-teal-700 disabled:bg-slate-300"
        >
          {lookup.isPending ? '確認しています…' : '予約を確認する'}
        </button>
      </form>

      <div aria-live="polite" className="space-y-3">
        {notFound && (
          <ErrorNotice>
            予約が見つかりませんでした。予約番号と、予約のときの電話番号またはメールアドレスを、確認してください。
          </ErrorNotice>
        )}
        {otherError && <ErrorNotice>{error.message}</ErrorNotice>}

        {lookup.data && (
          <section className="space-y-3 rounded-2xl border border-slate-200 p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-slate-900">{lookup.data.experience_title}</h2>
              <StatusBadge status={lookup.data.status} />
            </div>
            <p className="text-sm text-slate-700">{statusDescription(lookup.data.status)}</p>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">予約番号</dt>
                <dd className="font-mono font-medium">{lookup.data.booking_number}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">日時</dt>
                <dd className="text-right font-medium">{formatDateTime(lookup.data.starts_at)}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">人数</dt>
                <dd className="font-medium">{lookup.data.party_size}名</dd>
              </div>
            </dl>
            <p className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
              <span className="font-bold">📍 集合場所</span>
              <br />
              {lookup.data.meeting_point}
            </p>
          </section>
        )}
        {!lookup.data && !error && (
          <InfoNotice>
            予約番号が分からないときは、予約したときの画面を見返してください。
          </InfoNotice>
        )}
      </div>
    </div>
  )
}
