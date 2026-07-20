import { Outlet } from 'react-router-dom'
import { RequireAuth } from '@/components/auth/RequireAuth'
import { Layout } from '@/components/Layout'

export function ProtectedLayout() {
  return (
    <RequireAuth>
      <Layout>
        <Outlet />
      </Layout>
    </RequireAuth>
  )
}
