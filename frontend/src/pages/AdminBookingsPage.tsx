import { useState } from 'react'

import {
  useAdminBookings,
  useAdminSlots,
  useApproveBooking,
  useRejectBooking,
  useRevealContact,
} from '../api/adminHooks'
import { ApiError } from '../api/client'
import type { AdminBooking, AdminSlot } from '../api/types'
import { ErrorNotice, InfoNotice, LoadingNotice } from '../components/Notices'
import StatusBadge from '../components/StatusBadge'
import { formatDate, formatDateTime, formatTime } from '../lib/format'

type SlotGroup = {
  slotId: number
  startsAt: string
  title: string
  capacity: number | null
  bookedCount: number | null
  pendingCount: number
  bookings: AdminBooking[]
}

// 予約を、便ごとにまとめる。承認待ちのある便を上に、便の中では承認待ちを上に並べる。
function groupBySlot(bookings: AdminBooking[], slots: AdminSlot[]): SlotGroup[] {
  const slotById = new Map(slots.map((slot) => [slot.id, slot]))
  const groups = new Map<number, SlotGroup>()
  for (const booking of bookings) {
    let group = groups.get(booking.slot_id)
    if (!group) {
      const slot = slotById.get(booking.slot_id)
      group = {
        slotId: booking.slot_id,
        startsAt: booking.starts_at,
        title: booking.experience_title,
        capacity: slot?.capacity ?? null,
        bookedCount: slot?.booked_count ?? null,
        pendingCount: 0,
        bookings: [],
      }
      groups.set(booking.slot_id, group)
    }
    group.bookings.push(booking)
    if (booking.status === 'pending') {
      group.pendingCount += 1
    }
  }
  for (const group of groups.values()) {
    group.bookings.sort(
      (a, b) =>
        Number(b.status === 'pending') - Number(a.status === 'pending') ||
        a.created_at.localeCompare(b.created_at),
    )
  }
  return [...groups.values()].sort(
    (a, b) =>
      Number(b.pendingCount > 0) - Number(a.pendingCount > 0) ||
      a.startsAt.localeCompare(b.startsAt),
  )
}

// 予約の管理。承認待ちを目立たせ、承認・却下を、一覧から直接行う。連絡先は伏せ字で、「連絡先を表示」を押したときだけ、平文を取得する。
export default function AdminBookingsPage() {
  const bookingsQuery = useAdminBookings()
  const slotsQuery = useAdminSlots()
  const [pendingOnly, setPendingOnly] = useState(false)

  if (bookingsQuery.isPending || slotsQuery.isPending) {
    return <LoadingNotice />
  }
  if (bookingsQuery.isError || slotsQuery.isError) {
    return (
      <ErrorNotice>
        {(bookingsQuery.error ?? slotsQuery.error)?.message ?? 'エラーが発生しました。'}
      </ErrorNotice>
    )
  }

  const allBookings = bookingsQuery.data
  const pendingTotal = allBookings.filter((booking) => booking.status === 'pending').length
  const shown = pendingOnly
    ? allBookings.filter((booking) => booking.status === 'pending')
    : allBookings
  const groups = groupBySlot(shown, slotsQuery.data)

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-slate-900">予約の管理</h1>
          <p
            className={`rounded-full px-4 py-1.5 text-base font-bold ${
              pendingTotal > 0 ? 'bg-amber-100 text-amber-900' : 'bg-slate-100 text-slate-600'
            }`}
            aria-live="polite"
          >
            承認待ち {pendingTotal}件
          </p>
        </div>
        <label className="flex min-h-11 cursor-pointer items-center gap-2 text-sm text-slate-800">
          <input
            type="checkbox"
            checked={pendingOnly}
            onChange={(event) => setPendingOnly(event.target.checked)}
            className="size-5"
          />
          承認待ちだけを表示する
        </label>
      </section>

      {groups.length === 0 && (
        <InfoNotice>
          {pendingOnly ? '承認待ちの予約はありません。' : 'まだ、予約はありません。'}
        </InfoNotice>
      )}

      {groups.map((group) => (
        <section
          key={group.slotId}
          aria-label={`${formatDateTime(group.startsAt)} ${group.title}`}
          className="overflow-hidden rounded-2xl border border-slate-200 bg-white"
        >
          <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-4 py-3">
            <div>
              <p className="text-sm text-slate-600">
                {formatDate(group.startsAt)} {formatTime(group.startsAt)}
              </p>
              <h2 className="text-base font-bold text-slate-900">{group.title}</h2>
            </div>
            <div className="flex items-center gap-3 text-sm text-slate-700">
              {group.capacity !== null && group.bookedCount !== null && (
                <span>
                  予約済み {group.bookedCount}/{group.capacity}人
                </span>
              )}
              {group.pendingCount > 0 && (
                <span className="rounded-full bg-amber-100 px-3 py-1 font-bold text-amber-900">
                  承認待ち {group.pendingCount}件
                </span>
              )}
            </div>
          </header>
          <ul className="divide-y divide-slate-100">
            {group.bookings.map((booking) => (
              <li key={booking.id}>
                <BookingRow booking={booking} />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

function BookingRow({ booking }: { booking: AdminBooking }) {
  const approve = useApproveBooking()
  const reject = useRejectBooking()
  const reveal = useRevealContact()
  const [confirmingReject, setConfirmingReject] = useState(false)

  const isPending = booking.status === 'pending'
  const busy = approve.isPending || reject.isPending
  const decisionError = approve.error ?? reject.error
  const decisionMessage =
    decisionError instanceof ApiError && decisionError.code === 'INVALID_STATE'
      ? 'この予約は、すでに処理されています。一覧を更新しました。'
      : decisionError?.message

  // 連絡先は、平文の取得に成功したときだけ、この部品の状態として持つ（キャッシュやURLには残さない）。
  const contact = reveal.data
  const guestName = contact?.guest_name ?? booking.guest_name
  const guestPhone = contact?.guest_phone ?? booking.guest_phone
  const guestEmail = contact?.guest_email ?? booking.guest_email

  return (
    <div
      className={`space-y-2 px-4 py-3 ${isPending ? 'border-l-4 border-amber-400 bg-amber-50' : ''}`}
    >
      <div className="grid items-center gap-3 lg:grid-cols-[9rem_4rem_6rem_1fr_auto]">
        <div>
          <p className="font-mono text-sm font-bold tracking-wider text-slate-900">
            {booking.booking_number}
          </p>
          <p className="text-xs text-slate-500">{formatDateTime(booking.created_at)} 受付</p>
        </div>
        <p className="text-sm text-slate-800">{booking.party_size}名</p>
        <div>
          <StatusBadge status={booking.status} />
        </div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 text-sm text-slate-800">
          <dt className="whitespace-nowrap text-slate-500">氏名</dt>
          <dd>{guestName}</dd>
          <dt className="whitespace-nowrap text-slate-500">電話</dt>
          <dd className="whitespace-nowrap">{guestPhone}</dd>
          <dt className="whitespace-nowrap text-slate-500">メール</dt>
          <dd className="break-all">{guestEmail}</dd>
        </dl>
        <div className="flex flex-wrap items-center gap-2 lg:justify-end">
          {contact ? (
            <button
              type="button"
              onClick={() => reveal.reset()}
              className="min-h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              連絡先を隠す
            </button>
          ) : (
            <button
              type="button"
              onClick={() => reveal.mutate(booking.id)}
              disabled={reveal.isPending}
              aria-label={`予約 ${booking.booking_number} の連絡先を表示`}
              className="min-h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            >
              {reveal.isPending ? '取得中…' : '連絡先を表示'}
            </button>
          )}
          {isPending && !confirmingReject && (
            <>
              <button
                type="button"
                onClick={() => approve.mutate(booking.id)}
                disabled={busy}
                aria-label={`予約 ${booking.booking_number} を承認する`}
                className="min-h-11 rounded-lg bg-teal-600 px-5 text-sm font-bold text-white hover:bg-teal-700 disabled:bg-slate-300"
              >
                {approve.isPending ? '承認中…' : '承認する'}
              </button>
              <button
                type="button"
                onClick={() => setConfirmingReject(true)}
                disabled={busy}
                aria-label={`予約 ${booking.booking_number} を却下する`}
                className="min-h-11 rounded-lg border border-red-300 bg-white px-4 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-60"
              >
                却下する
              </button>
            </>
          )}
        </div>
      </div>

      {isPending && confirmingReject && (
        <div
          role="group"
          aria-label="却下の確認"
          className="flex flex-wrap items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2"
        >
          <p className="text-sm text-red-900">
            この予約を却下します。押さえていた定員は解放され、元に戻せません。
          </p>
          <button
            type="button"
            onClick={() => reject.mutate(booking.id)}
            disabled={busy}
            className="min-h-11 rounded-lg bg-red-700 px-4 text-sm font-bold text-white hover:bg-red-800 disabled:opacity-60"
          >
            {reject.isPending ? '却下中…' : '本当に却下する'}
          </button>
          <button
            type="button"
            onClick={() => setConfirmingReject(false)}
            disabled={busy}
            className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm text-slate-700 hover:bg-slate-50"
          >
            やめる
          </button>
        </div>
      )}

      {decisionMessage && <ErrorNotice>{decisionMessage}</ErrorNotice>}
      {reveal.error && <ErrorNotice>{reveal.error.message}</ErrorNotice>}
    </div>
  )
}
