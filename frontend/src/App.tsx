import { Navigate, Route, Routes } from 'react-router'

import AdminLayout from './components/AdminLayout'
import Layout from './components/Layout'
import AdminBookingsPage from './pages/AdminBookingsPage'
import AdminLoginPage from './pages/AdminLoginPage'
import BookingCompletePage from './pages/BookingCompletePage'
import BookingLookupPage from './pages/BookingLookupPage'
import ExperienceDetailPage from './pages/ExperienceDetailPage'
import ExperiencesPage from './pages/ExperiencesPage'
import HomePage from './pages/HomePage'
import NotFoundPage from './pages/NotFoundPage'

// 旅行者の画面（スマホ幅）と、事業者の画面（`/admin`、PC幅）。
export default function App() {
  return (
    <Routes>
      <Route path="admin/login" element={<AdminLoginPage />} />
      <Route path="admin" element={<AdminLayout />}>
        <Route index element={<Navigate to="bookings" replace />} />
        <Route path="bookings" element={<AdminBookingsPage />} />
      </Route>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="experiences" element={<ExperiencesPage />} />
        <Route path="experiences/:id" element={<ExperienceDetailPage />} />
        <Route path="bookings/complete" element={<BookingCompletePage />} />
        <Route path="bookings/lookup" element={<BookingLookupPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
