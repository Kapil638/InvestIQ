import { describe, expect, it } from 'vitest'
import { canSaveReportToDrive, isReportPdfReady } from '@/lib/reportExportState'

describe('reportExportState', () => {
  it('enables Drive save only after PDF is ready', () => {
    const report = {
      pdf_generated_at: null,
      google_drive_url: null,
    }

    expect(isReportPdfReady(report, false)).toBe(false)
    expect(canSaveReportToDrive(report, false)).toBe(false)
    expect(canSaveReportToDrive(report, true)).toBe(true)
  })

  it('disables Drive save when already saved', () => {
    const report = {
      pdf_generated_at: '2026-07-06T10:00:00Z',
      google_drive_url: 'https://drive.google.com/file/d/abc/view',
    }

    expect(canSaveReportToDrive(report, false)).toBe(false)
  })
})
