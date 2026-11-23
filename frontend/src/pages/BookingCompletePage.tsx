import { useState } from 'react'
import { Link, useLocation } from 'react-router'

import type { BookingCreated } from '../api/types'
import StatusBadge from '../components/StatusBadge'
import { formatDateTime, statusDescription } from '../lib/format'

function isBookingCreated(value: unknown): value is BookingCreated {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as BookingCreated).booking_number === 'string'
  )
}

// 予約の完了。予約番号は、あとで予約を確認するときに必要なので、控えてもらう。
export default function BookingCompletePage() {
  const location = useLocation()
  const [copied, setCopied] = useState(false)
  const booking: unknown = location.state

  if (!isBookingCreated(booking)) {
    // 再読み込みなどで、予約の情報が残っていないとき（個人情報を、ブラウザに保存しないため）
    return (
      <div className="space-y-3 py-8 text-center">
        <h1 className="text-lg font-bold text-slate-900">予約の情報が見つかりません</h1>
        <p className="text-sm text-slate-600">
          予約した直後の画面でのみ表示されます。予約番号をお持ちなら、予約の確認で状態を見られます。
        </p>
        <Link
          to="/bookings/lookup"
          className="inline-flex min-h-11 items-center rounded-xl bg-brand-500 px-5 text-sm font-bold text-white"
        >
          予約を確認する
        </Link>
      </div>
    )
  }

  async function copyNumber() {
    try {
      await navigator.clipboard.writeText((booking as BookingCreated).booking_number)
      setCopied(true)
    } catch {
      setCopied(false) // コピーできない環境では、番号を目で見て控えてもらう
    }
  }

  const confirmed = booking.status === 'confirmed'

  return (
    <div className="mx-auto max-w-xl space-y-5">
      <section className="space-y-2 text-center">
        <p className="text-4xl" aria-hidden="true">
          {confirmed ? '🎉' : '📨'}
        </p>
        <h1 className="text-xl font-bold text-slate-900">
          {confirmed ? '予約が確定しました' : '予約をリクエストしました'}
        </h1>
        <StatusBadge status={booking.status} />
        <p className="text-sm text-slate-600">{statusDescription(booking.status)}</p>
      </section>

      <section className="space-y-2 rounded-2xl border-2 border-brand-500 bg-brand-50 p-4 text-center">
        <p className="text-sm font-medium text-brand-900">予約番号（必ず控えてください）</p>
        <p
          className="font-mono text-3xl font-bold tracking-widest text-brand-950"
          aria-label={`予約番号 ${booking.booking_number.split('').join(' ')}`}
        >
          {booking.booking_number}
        </p>
        <button
          type="button"
          onClick={() => void copyNumber()}
          className="min-h-11 rounded-lg border border-brand-500 bg-white px-4 text-sm font-medium text-brand-800"
        >
          {copied ? 'コピーしました' : '番号をコピー'}
        </button>
        <p className="text-xs text-brand-900">
          予約番号と、予約のときの電話番号またはメールアドレスで、予約の状態を確認できます。
        </p>
      </section>

      <dl className="space-y-2 rounded-2xl bg-slate-50 p-4 text-sm">
        <div className="flex justify-between gap-4">
          <dt className="text-slate-500">体験</dt>
          <dd className="text-right font-medium">{booking.experience_title}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-slate-500">日時</dt>
          <dd className="text-right font-medium">{formatDateTime(booking.starts_at)}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-slate-500">人数</dt>
          <dd className="text-right font-medium">{booking.party_size}名</dd>
        </div>
      </dl>

      <div className="flex flex-col gap-2">
        <Link
          to="/bookings/lookup"
          className="flex min-h-12 items-center justify-center rounded-xl bg-brand-500 text-base font-bold text-white"
        >
          予約の状態を確認する
        </Link>
        <Link
          to="/experiences"
          className="flex min-h-12 items-center justify-center rounded-xl border border-slate-300 text-base font-medium text-slate-700"
        >
          ほかの体験を探す
        </Link>
      </div>
    </div>
  )
}
