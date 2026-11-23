// 表示用の関数。日時は、APIがUTCで返すので、すべて日本時間に直して表示する。

const TIME_ZONE = 'Asia/Tokyo'

const dateFormat = new Intl.DateTimeFormat('ja-JP', {
  timeZone: TIME_ZONE,
  month: 'numeric',
  day: 'numeric',
  weekday: 'short',
})
const timeFormat = new Intl.DateTimeFormat('ja-JP', {
  timeZone: TIME_ZONE,
  hour: 'numeric',
  minute: '2-digit',
  hourCycle: 'h23',
})
const isoDateFormat = new Intl.DateTimeFormat('en-CA', {
  timeZone: TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

/** 例: `11月24日(火)` */
export function formatDate(iso: string): string {
  return dateFormat.format(new Date(iso))
}

/** 例: `13:00` */
export function formatTime(iso: string): string {
  return timeFormat.format(new Date(iso))
}

/** 例: `11月24日(火) 13:00` */
export function formatDateTime(iso: string): string {
  return `${formatDate(iso)} ${formatTime(iso)}`
}

export function formatYen(amount: number): string {
  return `${amount.toLocaleString('ja-JP')}円`
}

/** 日本時間の、今日の日付（`YYYY-MM-DD`）。 */
export function todayInJapan(): string {
  return isoDateFormat.format(new Date())
}

export const categoryLabels: Record<string, string> = {
  marine: '海',
  craft: '工芸',
  nature: '自然',
  food: '食',
}

export const areaOptions = ['那覇市', '恩納村', '国頭村']

export const statusLabels: Record<string, string> = {
  confirmed: '確定',
  pending: '承認待ち',
  rejected: '却下',
  cancelled: '取消',
}

/** 予約の状態を、旅行者に向けた短い説明にする。 */
export function statusDescription(status: string): string {
  switch (status) {
    case 'confirmed':
      return '予約が確定しています。当日、集合場所にお越しください。'
    case 'pending':
      return '事業者の承認を待っています。承認されると、予約が確定します。'
    case 'rejected':
      return '今回は、予約を受けられませんでした。別の日時や体験をお探しください。'
    case 'cancelled':
      return 'この予約は取り消されました。'
    default:
      return ''
  }
}
