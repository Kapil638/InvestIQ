import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2, Trash2 } from 'lucide-react'
import { deleteReport, getReport } from '@/lib/api'
import type { ResearchReportResponse } from '@/types/api'
import { ProfessionalReport } from '@/components/research/ProfessionalReport'
import { ReportChat } from '@/components/research/ReportChat'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert } from '@/components/ui/alert'

export function ReportDetailPage() {
  const { reportId } = useParams<{ reportId: string }>()
  const navigate = useNavigate()
  const [report, setReport] = useState<ResearchReportResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!reportId) return

    const id = reportId
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await getReport(id)
        if (!cancelled) {
          setReport({ ...data.report, id: data.id })
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load report')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [reportId])

  async function handleDelete() {
    if (!reportId || !report) return

    const companyName = report.financial_data?.profile?.company_name
    const label = companyName ? `${report.ticker} (${companyName})` : report.ticker

    if (
      !window.confirm(
        `Delete this report for ${label}?\n\nThis permanently removes it from storage and search. This cannot be undone.`,
      )
    ) {
      return
    }

    setDeleting(true)
    setError(null)
    try {
      await deleteReport(reportId)
      navigate('/reports')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete report')
      setDeleting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to="/reports"
          className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Back to history
        </Link>
        {report && (
          <Button
            type="button"
            variant="outline"
            disabled={deleting}
            onClick={() => void handleDelete()}
            className="border-destructive/30 text-destructive hover:bg-destructive/10 hover:text-destructive"
          >
            {deleting ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
            Delete report
          </Button>
        )}
      </div>

      {loading && (
        <div className="space-y-4">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-60 w-full" />
        </div>
      )}

      {error && (
        <Alert variant="destructive" title="Error">
          {error}
        </Alert>
      )}

      {report && (
        <div className="space-y-6">
          <ProfessionalReport report={report} />
          <ReportChat reportId={report.id} />
        </div>
      )}
    </div>
  )
}
