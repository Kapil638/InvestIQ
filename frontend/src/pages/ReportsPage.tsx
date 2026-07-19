import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Loader2, Trash2 } from 'lucide-react'
import { deleteReportsBulk, listReports } from '@/lib/api'
import type { ReportSummary } from '@/types/api'
import { ReportCard } from '@/components/ReportCard'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert } from '@/components/ui/alert'
import { useGoogleDriveStatus } from '@/hooks/useGoogleDriveStatus'

export function ReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { driveConnected, refetch: refetchDriveStatus } = useGoogleDriveStatus()
  const [reports, setReports] = useState<ReportSummary[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [appliedFilter, setAppliedFilter] = useState<string | undefined>()
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [bulkDeleting, setBulkDeleting] = useState(false)
  const [pdfReadyIds, setPdfReadyIds] = useState<Set<string>>(new Set())

  useEffect(() => {
    const connected = searchParams.get('drive_connected')
    const errored = searchParams.get('drive_error')
    if (connected === '1' || errored === '1') {
      refetchDriveStatus()
      if (errored === '1') {
        setError('Failed to connect Google Drive. Please try again.')
      }
      setSearchParams({}, { replace: true })
    }
  }, [searchParams, refetchDriveStatus, setSearchParams])

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await listReports({
          ticker: appliedFilter,
          limit: 50,
        })
        if (!cancelled) {
          setReports(data.items)
          setTotal(data.total)
          setSelectedIds(new Set())
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load reports')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [appliedFilter])

  const allSelected = reports.length > 0 && selectedIds.size === reports.length
  const someSelected = selectedIds.size > 0 && !allSelected
  const selectedCount = selectedIds.size

  const selectAllLabel = useMemo(() => {
    if (reports.length === 0) return 'Select all'
    if (total > reports.length) {
      return `Select all (${reports.length} shown)`
    }
    return `Select all (${reports.length})`
  }, [reports.length, total])

  function toggleSelectAll() {
    if (allSelected) {
      setSelectedIds(new Set())
      return
    }
    setSelectedIds(new Set(reports.map((r) => r.id)))
  }

  function handleSelectedChange(reportId: string, selected: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (selected) next.add(reportId)
      else next.delete(reportId)
      return next
    })
  }

  function handleDeleted(reportId: string) {
    setReports((prev) => prev.filter((r) => r.id !== reportId))
    setTotal((prev) => Math.max(0, prev - 1))
    setSelectedIds((prev) => {
      if (!prev.has(reportId)) return prev
      const next = new Set(prev)
      next.delete(reportId)
      return next
    })
    setPdfReadyIds((prev) => {
      if (!prev.has(reportId)) return prev
      const next = new Set(prev)
      next.delete(reportId)
      return next
    })
  }

  function handleReportUpdated(reportId: string, patch: Partial<ReportSummary>) {
    setReports((prev) =>
      prev.map((report) => (report.id === reportId ? { ...report, ...patch } : report)),
    )
    if (patch.pdf_generated_at) {
      setPdfReadyIds((prev) => new Set(prev).add(reportId))
    }
  }

  async function handleBulkDelete() {
    if (selectedCount === 0) return

    const noun = selectedCount === 1 ? 'report' : 'reports'
    if (
      !window.confirm(
        `Delete ${selectedCount} ${noun}?\n\nThis permanently removes them from storage and search. This cannot be undone.`,
      )
    ) {
      return
    }

    setBulkDeleting(true)
    setError(null)
    try {
      const ids = Array.from(selectedIds)
      const result = await deleteReportsBulk(ids)
      const removed = new Set(ids.filter((id) => !result.not_found.includes(id)))
      setReports((prev) => prev.filter((r) => !removed.has(r.id)))
      setTotal((prev) => Math.max(0, prev - result.deleted))
      setSelectedIds((prev) => {
        const next = new Set(prev)
        for (const id of removed) next.delete(id)
        return next
      })
      if (result.not_found.length > 0) {
        setError(`${result.deleted} deleted. ${result.not_found.length} could not be found.`)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete reports')
    } finally {
      setBulkDeleting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Report History</h1>
        <p className="text-muted-foreground">
          Browse stored research reports ({total} total)
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <div className="flex max-w-sm flex-1 gap-2">
          <Input
            placeholder="Filter by ticker"
            value={filter}
            onChange={(e) => setFilter(e.target.value.toUpperCase())}
          />
          <Button variant="outline" onClick={() => setAppliedFilter(filter.trim() || undefined)}>
            Filter
          </Button>
        </div>

        {!loading && reports.length > 0 && (
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={allSelected}
                ref={(el) => {
                  if (el) el.indeterminate = someSelected
                }}
                onChange={toggleSelectAll}
                className="size-4 cursor-pointer rounded border-border accent-primary"
              />
              {selectAllLabel}
            </label>
            <Button
              type="button"
              variant="outline"
              disabled={selectedCount === 0 || bulkDeleting}
              onClick={() => void handleBulkDelete()}
              className="border-destructive/30 text-destructive hover:bg-destructive/10 hover:text-destructive"
            >
              {bulkDeleting ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Trash2 className="size-4" />
              )}
              {selectedCount > 0 ? `Delete selected (${selectedCount})` : 'Delete selected'}
            </Button>
          </div>
        )}
      </div>

      {error && (
        <Alert variant="destructive" title="Error">
          {error}
        </Alert>
      )}

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : reports.length === 0 ? (
        <Alert title="No reports yet">
          Generate your first report from the Research page. Reports are saved automatically when
          storage is enabled.
        </Alert>
      ) : (
        <div className="space-y-3">
          {reports.map((report) => (
            <ReportCard
              key={report.id}
              report={report}
              selected={selectedIds.has(report.id)}
              pdfReady={pdfReadyIds.has(report.id)}
              driveConnected={driveConnected}
              onSelectedChange={handleSelectedChange}
              onDeleted={handleDeleted}
              onReportUpdated={handleReportUpdated}
            />
          ))}
        </div>
      )}
    </div>
  )
}
