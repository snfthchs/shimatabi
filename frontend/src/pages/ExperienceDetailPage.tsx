import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import { useCreateBooking, useExperience } from '../api/hooks'
import type { ExperienceDetail } from '../api/types'
import { ExperienceBadges } from '../components/Badges'
import { ErrorNotice, InfoNotice, LoadingNotice } from '../components/Notices'
import Photo from '../components/Photo'
import SlotPicker from '../components/SlotPicker'
import Stepper from '../components/Stepper'
import TextField from '../components/TextField'
import { categoryLabels, formatDateTime, formatYen } from '../lib/format'
import type { FieldErrors } from '../lib/validation'
import { serverFieldErrors, validateBookingFields } from '../lib/validation'

const MAX_PARTY_SIZE = 10

// エラーのある最初の項目に、移動する（画面読み上げや、スマホの画面で、気づきやすくするため）。
function focusFirstError(errors: FieldErrors) {
  if (errors.slot) {
    document.getElementById('slot-section')?.scrollIntoView({ block: 'center' })
    return
  }
  const order: [string, string][] = [
    ['name', 'guest-name'],
    ['phone', 'guest-phone'],
    ['email', 'guest-email'],
  ]
  const target = order.find(([field]) => errors[field])
  if (target) {
    document.getElementById(target[1])?.focus()
  }
}

function ExperienceDetailView({
  experience,
  refetch,
}: {
  experience: ExperienceDetail
  refetch: () => void
}) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()
  const createBooking = useCreateBooking()

  const [pickedSlotId, setPickedSlotId] = useState<number | null>(null)
  const [partySizeInput, setPartySizeInput] = useState(1)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [notice, setNotice] = useState<string | null>(null)

  // 選んだ便。URLの `?slot=`（提案のカードから来たとき）か、自分で選んだ便。満席の便は、選べない。
  const requestedSlotId = pickedSlotId ?? (Number(searchParams.get('slot')) || null)
  const selectedSlot =
    experience.slots.find((slot) => slot.id === requestedSlotId && !slot.is_full) ?? null
  const maxPartySize = selectedSlot ? Math.min(selectedSlot.remaining, MAX_PARTY_SIZE) : MAX_PARTY_SIZE
  const partySize = Math.min(Math.max(partySizeInput, 1), maxPartySize)
  const isInstant = experience.confirmation_mode === 'instant'

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setNotice(null)

    const found = validateBookingFields({ name, phone, email })
    if (!selectedSlot) {
      found.slot = '便を選んでください。'
    }
    if (Object.keys(found).length > 0) {
      setErrors(found)
      focusFirstError(found)
      return
    }
    setErrors({})

    createBooking.mutate(
      {
        slot_id: selectedSlot!.id,
        party_size: partySize,
        guest_name: name,
        guest_phone: phone,
        guest_email: email,
      },
      {
        onSuccess: (booking) => {
          // 残席が変わったので、一覧と詳細は、取り直す。
          void queryClient.invalidateQueries({ queryKey: ['experiences'] })
          void queryClient.invalidateQueries({ queryKey: ['experience'] })
          navigate('/bookings/complete', { state: booking, replace: true })
        },
        onError: (error) => {
          if (error instanceof ApiError && error.code === 'SLOT_UNAVAILABLE') {
            // 満席になった（ほかの人が先に予約した）など。便の一覧を取り直して、選び直してもらう。
            setNotice('この便は、満席になったか、受付を終了しました。ほかの便を選んでください。')
            setPickedSlotId(null)
            refetch()
          } else if (error instanceof ApiError && error.code === 'VALIDATION_ERROR') {
            const fields = serverFieldErrors(error.details)
            setErrors(fields)
            setNotice('入力内容を確認してください。')
            focusFirstError(fields)
          } else {
            setNotice(error.message || 'エラーが発生しました。もう一度お試しください。')
          }
        },
      },
    )
  }

  return (
    <div className="space-y-5">
      <Photo
        src={experience.photo_url}
        alt={experience.title}
        className="aspect-video w-full rounded-2xl"
      />

      <section className="space-y-2">
        <p className="text-xs text-slate-500">
          {categoryLabels[experience.category] ?? experience.category}・{experience.area}・
          {experience.business_name}
        </p>
        <h1 className="text-xl font-bold text-slate-900">{experience.title}</h1>
        <ExperienceBadges experience={experience} />
        <p className="text-sm text-slate-700">
          <span className="text-lg font-bold">{formatYen(experience.price_yen)}</span>
          <span className="text-slate-500">／人・約{experience.duration_minutes}分</span>
        </p>
        <p className="text-sm leading-relaxed text-slate-700">{experience.description}</p>
        <p className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
          <span className="font-bold">📍 集合場所</span>
          <br />
          {experience.meeting_point}
        </p>
      </section>

      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        <h2 className="text-lg font-bold text-slate-900">予約する</h2>

        {notice && <ErrorNotice>{notice}</ErrorNotice>}

        <section id="slot-section" className="space-y-2">
          <h3 className="text-sm font-bold text-slate-800">① 便を選ぶ</h3>
          <SlotPicker
            slots={experience.slots}
            value={selectedSlot?.id ?? null}
            onChange={setPickedSlotId}
            error={errors.slot}
          />
          <InfoNotice>
            {isInstant
              ? '空きがあれば、予約と同時に確定します。'
              : 'この体験は、事業者が承認すると、予約が確定します。承認の結果は、予約の確認の画面で見られます。'}
          </InfoNotice>
        </section>

        <section className="space-y-3">
          <h3 className="text-sm font-bold text-slate-800">② 人数とご連絡先</h3>
          <Stepper
            label="人数"
            value={partySize}
            min={1}
            max={maxPartySize}
            onChange={setPartySizeInput}
          />
          <TextField
            id="guest-name"
            label="お名前"
            value={name}
            onChange={(event) => setName(event.target.value)}
            error={errors.name}
            autoComplete="name"
            maxLength={100}
          />
          <TextField
            id="guest-phone"
            label="電話番号"
            type="tel"
            inputMode="tel"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            error={errors.phone}
            hint="例: 090-1234-5678（当日の緊急連絡に使います）"
            autoComplete="tel"
          />
          <TextField
            id="guest-email"
            label="メールアドレス"
            type="email"
            inputMode="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            error={errors.email}
            hint="例: name@example.com"
            autoComplete="email"
          />
          <p className="text-xs text-slate-500">
            お名前・電話番号・メールアドレスは、予約の連絡と確認のためにだけ使います。
          </p>
        </section>

        <div className="sticky bottom-0 -mx-4 space-y-1 border-t border-slate-200 bg-white px-4 py-3">
          {selectedSlot ? (
            <p className="text-xs text-slate-600">
              {formatDateTime(selectedSlot.starts_at)}・{partySize}名・
              <span className="font-bold">{formatYen(experience.price_yen * partySize)}</span>
            </p>
          ) : (
            <p className="text-xs text-slate-500">便を選ぶと、金額が表示されます。</p>
          )}
          <button
            type="submit"
            disabled={createBooking.isPending}
            className="min-h-12 w-full rounded-xl bg-teal-600 text-base font-bold text-white hover:bg-teal-700 disabled:bg-slate-300"
          >
            {createBooking.isPending
              ? '送信中…'
              : isInstant
                ? '予約を確定する'
                : '予約をリクエストする'}
          </button>
        </div>
      </form>
    </div>
  )
}

export default function ExperienceDetailPage() {
  const { id } = useParams()
  const experienceId = /^\d+$/.test(id ?? '') ? Number(id) : null
  const query = useExperience(experienceId)

  if (experienceId === null || (query.isError && query.error instanceof ApiError && query.error.status === 404)) {
    return (
      <div className="space-y-3 py-8 text-center">
        <h1 className="text-lg font-bold text-slate-900">体験が見つかりません</h1>
        <Link to="/experiences" className="text-sm text-teal-700 underline">
          体験の一覧へ
        </Link>
      </div>
    )
  }
  if (query.isPending) {
    return <LoadingNotice />
  }
  if (query.isError) {
    return <ErrorNotice>{query.error.message}</ErrorNotice>
  }
  return (
    <ExperienceDetailView
      key={query.data.id}
      experience={query.data}
      refetch={() => void query.refetch()}
    />
  )
}
