import type { ReportSummary } from '@/types/api'

export function isReportPdfReady(
  report: Pick<ReportSummary, 'pdf_generated_at'>,
  sessionPdfReady: boolean,
): boolean {
  return sessionPdfReady || Boolean(report.pdf_generated_at)
}

export function canSaveReportToDrive(
  report: Pick<ReportSummary, 'pdf_generated_at' | 'google_drive_url'>,
  sessionPdfReady: boolean,
): boolean {
  return isReportPdfReady(report, sessionPdfReady) && !report.google_drive_url
}
