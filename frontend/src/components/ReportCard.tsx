import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight, ExternalLink, FileDown, Loader2, Trash2, Upload } from 'lucide-react'
import { deleteReport, downloadReportPdf, saveReportToGoogleDrive, API_BASE } from '@/lib/api'
import { canSaveReportToDrive } from '@/lib/reportExportState'
import type { ReportSummary } from '@/types/api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { RecommendationBadge } from '@/components/RecommendationBadge'
import { formatDate, cn } from '@/lib/utils'

interface ReportCardProps {
  report: ReportSummary
  selected?: boolean
  pdfReady?: boolean
  driveConnected?: boolean
  onSelectedChange?: (reportId: string, selected: boolean) => void
  onDeleted?: (reportId: string) => void
  onReportUpdated?: (reportId: string, patch: Partial<ReportSummary>) => void
}

export function ReportCard({
  report,
  selected = false,
  pdfReady = false,
  driveConnected = false,
  onSelectedChange,
  onDeleted,
  onReportUpdated,
}: ReportCardProps) {
  const [deleting, setDeleting] = useState(false)
  const [generatingPdf, setGeneratingPdf] = useState(false)
  const [savingDrive, setSavingDrive] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canSaveToDrive = canSaveReportToDrive(report, pdfReady)
  const isSavedToDrive = Boolean(report.google_drive_url)

  const driveButtonLabel = useMemo(() => {
    if (savingDrive) return 'Saving to Drive...'
    if (isSavedToDrive) return 'Saved'
    return 'Save to Google Drive'
  }, [isSavedToDrive, savingDrive])

  async function handleDelete(e: React.MouseEvent) {
    e.preventDefault()
    e.stopPropagation()

    const label = report.company_name
      ? `${report.ticker} (${report.company_name})`
      : report.ticker

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
      await deleteReport(report.id)
      onDeleted?.(report.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete report')
    } finally {
      setDeleting(false)
    }
  }

  async function handleGeneratePdf(e: React.MouseEvent) {
    e.preventDefault()
    e.stopPropagation()
    setGeneratingPdf(true)
    setError(null)
    try {
      await downloadReportPdf(report.id)
      onReportUpdated?.(report.id, {
        pdf_generated_at: new Date().toISOString(),
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'PDF generation failed')
    } finally {
      setGeneratingPdf(false)
    }
  }

  async function handleSaveToDrive(e: React.MouseEvent) {
    e.preventDefault()
    e.stopPropagation()
    if (!canSaveToDrive || isSavedToDrive) return

    setSavingDrive(true)
    setError(null)
    try {
      const result = await saveReportToGoogleDrive(report.id)
      onReportUpdated?.(report.id, {
        pdf_generated_at: report.pdf_generated_at ?? new Date().toISOString(),
        google_drive_file_id: result.drive_file_id,
        google_drive_url: result.drive_url,
        google_drive_saved_at: new Date().toISOString(),
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save to Google Drive failed')
    } finally {
      setSavingDrive(false)
    }
  }

  function handleSelectChange(e: React.ChangeEvent<HTMLInputElement>) {
    e.stopPropagation()
    onSelectedChange?.(report.id, e.target.checked)
  }

  return (
    <div className="space-y-1">
      <Card
        className={cn(
          'transition-colors hover:border-primary/40 hover:bg-muted/20',
          selected && 'border-primary/50 bg-primary/5',
        )}
      >
        <CardContent className="flex flex-col gap-3 p-4">
          <div className="flex items-center gap-3">
            {onSelectedChange && (
              <input
                type="checkbox"
                checked={selected}
                onChange={handleSelectChange}
                onClick={(e) => e.stopPropagation()}
                className="size-4 shrink-0 cursor-pointer rounded border-border accent-primary"
                aria-label={`Select report for ${report.ticker}`}
              />
            )}
            <Link
              to={`/reports/${report.id}`}
              className="flex min-w-0 flex-1 items-center justify-between gap-4"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-lg font-semibold">{report.ticker}</span>
                  {report.company_name && (
                    <span className="truncate text-sm text-muted-foreground">
                      {report.company_name}
                    </span>
                  )}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {formatDate(report.generated_at)}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <RecommendationBadge
                  rating={report.rating}
                  confidence={report.confidence_score}
                />
                <ChevronRight className="size-4 text-muted-foreground" />
              </div>
            </Link>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={deleting}
              onClick={handleDelete}
              className="size-9 shrink-0 border-destructive/30 p-0 text-destructive hover:bg-destructive/10 hover:text-destructive"
              aria-label={`Delete report for ${report.ticker}`}
            >
              {deleting ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
            </Button>
          </div>

          <div className="flex flex-wrap items-center gap-2 pl-0 sm:pl-7">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={generatingPdf}
              onClick={(e) => void handleGeneratePdf(e)}
              className="gap-2"
            >
              {generatingPdf ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <FileDown className="size-4" />
              )}
              {generatingPdf ? 'Generating PDF...' : 'Generate PDF'}
            </Button>

            {driveConnected || isSavedToDrive ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={!canSaveToDrive || savingDrive}
                onClick={(e) => void handleSaveToDrive(e)}
                className="gap-2"
              >
                {savingDrive ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Upload className="size-4" />
                )}
                {driveButtonLabel}
              </Button>
            ) : (
              <a
                href={`${API_BASE}/google-drive/login`}
                onClick={(e) => e.stopPropagation()}
                className="inline-flex h-8 items-center gap-2 rounded-lg border border-border/70 px-3 text-xs font-medium text-muted-foreground hover:bg-muted"
              >
                <Upload className="size-4" />
                Connect Google Drive
              </a>
            )}

            {isSavedToDrive && report.google_drive_url && (
              <a
                href={report.google_drive_url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="inline-flex h-8 items-center gap-2 rounded-lg px-3 text-xs font-medium text-primary hover:bg-muted"
              >
                <ExternalLink className="size-4" />
                Open in Drive
              </a>
            )}
          </div>
        </CardContent>
      </Card>
      {error && <p className="px-1 text-xs text-destructive">{error}</p>}
    </div>
  )
}
