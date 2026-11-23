// 事業者の画面から使う、APIの呼び出し（TanStack Query）。認証は、HttpOnlyのCookieで行うので、画面は、トークンを持たない。

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiRequest } from './client'
import type { AdminBooking, AdminSlot, Contact, LoginRequest, Me } from './types'

const ME_KEY = ['admin', 'me'] as const
const BOOKINGS_KEY = ['admin', 'bookings'] as const
const SLOTS_KEY = ['admin', 'slots'] as const

/** ログイン中の事業者。未ログイン（401）のときは、`error` が `ApiError`（`status === 401`）になる。 */
export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: () => apiRequest<Me>('/api/admin/me'),
    retry: false,
    staleTime: 60_000,
  })
}

export function isUnauthenticated(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: LoginRequest) =>
      apiRequest<Me>('/api/admin/login', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: (me) => {
      // ログアウトしないまま別の事業者が入っても、前の事業者のデータが見えないよう、先に捨てる
      queryClient.removeQueries({ queryKey: ['admin'] })
      queryClient.setQueryData(ME_KEY, me)
    },
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiRequest<void>('/api/admin/logout', { method: 'POST' }),
    onSettled: () => {
      // 成否にかかわらず、画面に残っている事業者のデータ（個人情報を含む）を捨てる
      queryClient.removeQueries({ queryKey: ['admin'] })
    },
  })
}

export function useAdminSlots() {
  return useQuery({
    queryKey: SLOTS_KEY,
    queryFn: () => apiRequest<AdminSlot[]>('/api/admin/slots'),
  })
}

export function useAdminBookings() {
  return useQuery({
    queryKey: BOOKINGS_KEY,
    queryFn: () => apiRequest<AdminBooking[]>('/api/admin/bookings'),
  })
}

/** 承認・却下のあとは、予約と便（予約済み人数）を取得し直す。409（すでに処理済み）のときも、取得し直す。 */
function useDecision(action: 'approve' | 'reject') {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (bookingId: number) =>
      apiRequest<AdminBooking>(`/api/admin/bookings/${bookingId}/${action}`, { method: 'POST' }),
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: BOOKINGS_KEY }),
        queryClient.invalidateQueries({ queryKey: SLOTS_KEY }),
      ]),
  })
}

export function useApproveBooking() {
  return useDecision('approve')
}

export function useRejectBooking() {
  return useDecision('reject')
}

/**
 * 連絡先（平文）を取得する。キャッシュに残さないよう、`useQuery` ではなく `useMutation` を使い、
 * 結果は、呼び出した部品の状態にだけ持たせる。
 */
export function useRevealContact() {
  return useMutation({
    mutationFn: (bookingId: number) =>
      apiRequest<Contact>(`/api/admin/bookings/${bookingId}/contact`),
    gcTime: 0,
  })
}
