// 入力の確認。送る前に、画面で確認して、分かりやすいメッセージを出す。
// サーバーの確認（422）も、同じ形（項目名 → メッセージ）に直して、同じ場所に表示する。

import type { ErrorDetail } from '../api/client'

export type FieldErrors = Partial<Record<string, string>>

// APIと同じ規則（`backend/app/contact.py`）。電話番号は、空白・ハイフン・括弧を取り除いた形で確かめる。
const PHONE_PATTERN = /^\+?[0-9]{8,15}$/
const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

function normalizeText(value: string): string {
  return value.normalize('NFKC').trim()
}

export function normalizePhone(value: string): string {
  return normalizeText(value).replace(/[\s\-()]/g, '')
}

export type BookingFields = { name: string; phone: string; email: string }

export function validateBookingFields(fields: BookingFields): FieldErrors {
  const errors: FieldErrors = {}

  const name = normalizeText(fields.name)
  if (!name) {
    errors.name = 'お名前を入力してください。'
  } else if (name.length > 100) {
    errors.name = 'お名前は、100文字以内で入力してください。'
  }

  if (!normalizeText(fields.phone)) {
    errors.phone = '電話番号を入力してください。'
  } else if (!PHONE_PATTERN.test(normalizePhone(fields.phone))) {
    errors.phone = '電話番号の形式が正しくありません。（例: 090-1234-5678）'
  }

  const email = normalizeText(fields.email)
  if (!email) {
    errors.email = 'メールアドレスを入力してください。'
  } else if (email.length > 254 || !EMAIL_PATTERN.test(email)) {
    errors.email = 'メールアドレスの形式が正しくありません。（例: name@example.com）'
  }

  return errors
}

// APIの項目名 → 画面の項目名
const FIELD_NAMES: Record<string, string> = {
  guest_name: 'name',
  guest_phone: 'phone',
  guest_email: 'email',
  party_size: 'partySize',
  slot_id: 'slot',
  booking_number: 'number',
  contact: 'contact',
  message: 'message',
}

function describeServerError(type: string): string {
  switch (type) {
    case 'missing':
    case 'string_too_short':
      return '入力してください。'
    case 'string_too_long':
      return '長すぎます。短くして、もう一度お試しください。'
    case 'value_error':
      return '形式が正しくありません。'
    default:
      return '入力内容を確認してください。'
  }
}

/** サーバーの入力エラー（422）を、画面の項目ごとのメッセージに直す。 */
export function serverFieldErrors(details: ErrorDetail[]): FieldErrors {
  const errors: FieldErrors = {}
  for (const detail of details) {
    const field = FIELD_NAMES[detail.field] ?? detail.field
    errors[field] ??= describeServerError(detail.type)
  }
  return errors
}
