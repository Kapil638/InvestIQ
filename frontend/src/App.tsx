import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { HomePage } from '@/pages/HomePage'
import { PortfolioPage } from '@/pages/PortfolioPage'
import { ReportsPage } from '@/pages/ReportsPage'
import { ReportDetailPage } from '@/pages/ReportDetailPage'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/portfolio" element={<PortfolioPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/reports/:reportId" element={<ReportDetailPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
