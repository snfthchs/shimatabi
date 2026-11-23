import { Route, Routes } from 'react-router'

import Layout from './components/Layout'
import BookingCompletePage from './pages/BookingCompletePage'
import BookingLookupPage from './pages/BookingLookupPage'
import ExperienceDetailPage from './pages/ExperienceDetailPage'
import ExperiencesPage from './pages/ExperiencesPage'
import HomePage from './pages/HomePage'
import NotFoundPage from './pages/NotFoundPage'

// 旅行者の画面。事業者の画面（`/admin`）は、Issue G で追加する。
export default function App() {
  return (
    <Routes>
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
