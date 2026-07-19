import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { createPortal } from 'react-dom'
import { Building2, Loader2, Search } from 'lucide-react'
import type { IndianCompany } from '@/data/indianCompanies'
import { searchCompaniesApi } from '@/lib/api'
import type { CompanySearchResponse, CompanySearchResult } from '@/types/api'
import { cn } from '@/lib/utils'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

interface CompanySearchProps {
  onSelect: (company: IndianCompany) => void
  selectedCompany?: IndianCompany | null
  placeholder?: string
  className?: string
  autoFocus?: boolean
}

const DEBOUNCE_MS = 300
const MIN_CHARS = 2
const CACHE_TTL_MS = 5 * 60 * 1000

const SOURCE_LABELS: Record<string, string> = {
  nse: 'NSE',
  tapetide_mcp: 'Tapetide MCP',
  local_master: 'Local Master',
  yahoo: 'Yahoo',
}

const searchCache = new Map<string, { ts: number; data: CompanySearchResponse }>()
const inFlight = new Map<string, Promise<CompanySearchResponse>>()

function formatCompanyLabel(company: IndianCompany): string {
  return `${company.name} (${company.ticker})`
}

function toIndianCompany(result: CompanySearchResult): IndianCompany {
  return {
    name: result.company_name,
    ticker: result.symbol,
    exchange: result.exchange,
    sector: result.sector ?? undefined,
  }
}

function getCached(query: string): CompanySearchResponse | null {
  const entry = searchCache.get(query)
  if (!entry) return null
  if (Date.now() - entry.ts > CACHE_TTL_MS) {
    searchCache.delete(query)
    return null
  }
  return entry.data
}

async function fetchSearchResults(
  query: string,
  signal: AbortSignal,
): Promise<CompanySearchResponse> {
  const cached = getCached(query)
  if (cached) return cached

  const existing = inFlight.get(query)
  if (existing) return existing

  const request = searchCompaniesApi(query, { signal })
    .then((data) => {
      searchCache.set(query, { ts: Date.now(), data })
      return data
    })
    .finally(() => {
      inFlight.delete(query)
    })

  inFlight.set(query, request)
  return request
}

export function CompanySearch({
  onSelect,
  selectedCompany = null,
  placeholder = 'Search company or ticker…',
  className,
  autoFocus,
}: CompanySearchProps) {
  const listboxId = useId()
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [highlightIndex, setHighlightIndex] = useState(0)
  const [dropdownStyle, setDropdownStyle] = useState<{ top: number; left: number; width: number } | null>(
    null,
  )
  const [results, setResults] = useState<CompanySearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [searchSource, setSearchSource] = useState<string | null>(null)
  const [pendingCompany, setPendingCompany] = useState<IndianCompany | null>(null)

  const trimmedQuery = query.trim()
  const canSearch = trimmedQuery.length >= MIN_CHARS
  const showDropdown = open && canSearch && !pendingCompany
  const isDebouncing = canSearch && !pendingCompany && debouncedQuery !== trimmedQuery.toLowerCase()

  async function confirmSearch() {
    if (!canSearch) return

    if (pendingCompany) {
      setOpen(false)
      onSelect(pendingCompany)
      return
    }

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setOpen(false)

    try {
      const data = await fetchSearchResults(trimmedQuery.toLowerCase(), controller.signal)
      if (controller.signal.aborted) return

      const best = data.results[0]
      if (!best) return

      const company = toIndianCompany(best)
      setPendingCompany(company)
      setQuery(formatCompanyLabel(company))
      onSelect(company)
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        console.error('Company search failed:', err.message)
      }
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
      }
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    void confirmSearch()
  }

  useEffect(() => {
    if (!canSearch || pendingCompany) {
      setDebouncedQuery('')
      return
    }

    const timer = window.setTimeout(() => {
      setDebouncedQuery(trimmedQuery.toLowerCase())
    }, DEBOUNCE_MS)

    return () => window.clearTimeout(timer)
  }, [trimmedQuery, canSearch, pendingCompany])

  useEffect(() => {
    if (selectedCompany) {
      setQuery(formatCompanyLabel(selectedCompany))
      setPendingCompany(null)
      setOpen(false)
    }
  }, [selectedCompany])

  useEffect(() => {
    if (!debouncedQuery || debouncedQuery.length < MIN_CHARS || pendingCompany) {
      abortRef.current?.abort()
      setResults([])
      setLoading(false)
      setSearchSource(null)
      return
    }

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setSearchSource(null)

    void fetchSearchResults(debouncedQuery, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return
        setResults(data.results)
        setSearchSource(data.source)
        setHighlightIndex(0)
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setResults([])
        setSearchSource(null)
        if (err instanceof Error && err.name !== 'AbortError') {
          console.error('Company search failed:', err.message)
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      })

    return () => {
      controller.abort()
    }
  }, [debouncedQuery, pendingCompany])

  function updateDropdownPosition() {
    const input = inputRef.current
    if (!input) return
    const rect = input.getBoundingClientRect()
    setDropdownStyle({
      top: rect.bottom + 8,
      left: rect.left,
      width: rect.width,
    })
  }

  useEffect(() => {
    if (!showDropdown) {
      setDropdownStyle(null)
      return
    }
    updateDropdownPosition()
    window.addEventListener('resize', updateDropdownPosition)
    window.addEventListener('scroll', updateDropdownPosition, true)
    return () => {
      window.removeEventListener('resize', updateDropdownPosition)
      window.removeEventListener('scroll', updateDropdownPosition, true)
    }
  }, [showDropdown, query, results.length, loading])

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as HTMLElement
      if (
        containerRef.current?.contains(target) ||
        target.closest('[data-company-search-dropdown]')
      ) {
        return
      }
      setOpen(false)
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [])

  function pickFromDropdown(result: CompanySearchResult) {
    const company = toIndianCompany(result)
    setPendingCompany(company)
    setQuery(formatCompanyLabel(company))
    setOpen(false)
    setDebouncedQuery('')
    setResults([])
    setSearchSource(null)
    inputRef.current?.blur()
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault()
      if (open && !pendingCompany && results[highlightIndex]) {
        pickFromDropdown(results[highlightIndex])
        return
      }
      void confirmSearch()
      return
    }

    if (!open && e.key === 'ArrowDown' && results.length > 0) {
      setOpen(true)
      return
    }
    if (!open) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlightIndex((i) => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlightIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  const statusMessage = (() => {
    if (!canSearch) return null
    if (isDebouncing || loading) return 'Searching NSE master…'
    if (debouncedQuery && results.length === 0) return 'No companies found.'
    return null
  })()

  const sourceLabel = searchSource ? SOURCE_LABELS[searchSource] ?? searchSource : null

  return (
    <div ref={containerRef} className={cn('relative', className)}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            ref={inputRef}
            autoFocus={autoFocus}
            role="combobox"
            aria-expanded={open}
            aria-controls={listboxId}
            aria-autocomplete="list"
            placeholder={placeholder}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setPendingCompany(null)
              setOpen(true)
            }}
            onFocus={() => {
              if (canSearch && !pendingCompany) setOpen(true)
            }}
            onKeyDown={handleKeyDown}
            className="h-12 border-border/80 bg-background/50 pl-10 backdrop-blur"
          />
        </div>

        <Button
          type="submit"
          disabled={!canSearch || loading}
          className="w-full bg-gradient-to-r from-emerald-600 to-emerald-500 text-white hover:from-emerald-500 hover:to-emerald-400 sm:w-auto"
        >
          {loading ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Searching…
            </>
          ) : (
            <>
              <Search className="size-4" />
              Search
            </>
          )}
        </Button>
      </form>

      {showDropdown &&
        dropdownStyle &&
        createPortal(
          <div
            data-company-search-dropdown
            style={{
              position: 'fixed',
              top: dropdownStyle.top,
              left: dropdownStyle.left,
              width: dropdownStyle.width,
            }}
            className="z-[200] overflow-hidden rounded-xl border border-border/80 bg-card shadow-2xl shadow-black/50"
          >
            {(statusMessage || sourceLabel) && (
              <div className="flex items-center justify-between gap-2 border-b border-border/60 px-3 py-2">
                <span className="text-xs text-muted-foreground">{statusMessage}</span>
                {sourceLabel && !loading && (
                  <Badge variant="outline" className="shrink-0 text-[10px] font-normal">
                    {sourceLabel}
                  </Badge>
                )}
              </div>
            )}

            <ul id={listboxId} role="listbox" className="max-h-80 overflow-y-auto p-1.5">
              {debouncedQuery && !loading && !isDebouncing && results.length > 0 ? (
                results.map((company, index) => (
                  <li
                    key={`${company.exchange}:${company.symbol}`}
                    role="option"
                    aria-selected={index === highlightIndex}
                  >
                    <button
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        pickFromDropdown(company)
                      }}
                      onMouseEnter={() => setHighlightIndex(index)}
                      className={cn(
                        'flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-colors',
                        index === highlightIndex ? 'bg-primary/10' : 'hover:bg-muted/50',
                      )}
                    >
                      <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-background/60">
                        <Building2 className="size-4 text-primary" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium text-foreground">
                          {company.company_name}
                        </span>
                        <span className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                          <span className="font-mono text-primary/90">{company.symbol}</span>
                          <span aria-hidden="true">•</span>
                          <span>{company.exchange}</span>
                          {company.source && (
                            <Badge variant="outline" className="px-1.5 py-0 text-[10px] font-normal">
                              {SOURCE_LABELS[company.source] ?? company.source}
                            </Badge>
                          )}
                        </span>
                        {company.sector && (
                          <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                            {company.sector}
                          </span>
                        )}
                      </span>
                    </button>
                  </li>
                ))
              ) : debouncedQuery && !loading && !isDebouncing ? (
                <li className="px-3 py-4 text-sm text-muted-foreground">No companies found.</li>
              ) : isDebouncing || loading ? (
                <li className="px-3 py-4 text-sm text-muted-foreground">Searching…</li>
              ) : null}
            </ul>
          </div>,
          document.body,
        )}
    </div>
  )
}
