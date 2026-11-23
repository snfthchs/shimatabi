// 画面から使う、APIの呼び出し（TanStack Query）。

import { useMutation, useQuery } from '@tanstack/react-query'

import { apiRequest, buildQuery } from './client'
import type {
  BookingCreate,
  BookingCreated,
  BookingLookup,
  BookingStatusOut,
  Category,
  ConciergeResponse,
  ExperienceDetail,
  ExperienceListItem,
} from './types'

export type ExperienceFilters = {
  date?: string
  party_size?: number
  kids_ok?: boolean
  rain_ok?: boolean
  area?: string
  category?: Category
}

export function useExperiences(filters: ExperienceFilters) {
  return useQuery({
    queryKey: ['experiences', filters],
    queryFn: () => apiRequest<ExperienceListItem[]>(`/api/experiences${buildQuery(filters)}`),
  })
}

export function useExperience(id: number | null) {
  return useQuery({
    queryKey: ['experience', id],
    queryFn: () => apiRequest<ExperienceDetail>(`/api/experiences/${id}`),
    enabled: id !== null,
  })
}

export function useCreateBooking() {
  return useMutation({
    mutationFn: (body: BookingCreate) =>
      apiRequest<BookingCreated>('/api/bookings', { method: 'POST', body: JSON.stringify(body) }),
  })
}

export function useLookupBooking() {
  return useMutation({
    mutationFn: (body: BookingLookup) =>
      apiRequest<BookingStatusOut>('/api/bookings/lookup', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
  })
}

export function useConcierge() {
  return useMutation({
    mutationFn: (message: string) =>
      apiRequest<ConciergeResponse>('/api/concierge/search', {
        method: 'POST',
        body: JSON.stringify({ message }),
      }),
  })
}
