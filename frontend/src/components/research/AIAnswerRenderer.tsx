import { Fragment, useMemo, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

const METRIC_KEYWORDS = [
  'price',
  'market cap',
  'revenue',
  'growth',
  'p/e',
  'pe ratio',
  'pb ratio',
  'roe',
  'dividend',
  'eps',
  'margin',
  'debt',
  'ratio',
  'yield',
  'volume',
  '52-week',
  '52 week',
  'target',
  'valuation',
  'ebitda',
  'profit',
  'sales',
  'earnings',
  'cash flow',
  'net income',
  'operating',
  'fcf',
  'book value',
]

type Block =
  | { type: 'heading'; level: number; text: string }
  | { type: 'ul'; items: string[] }
  | { type: 'ol'; items: string[] }
  | { type: 'table'; headers: string[]; rows: string[][] }
  | { type: 'blockquote'; lines: string[] }
  | { type: 'metrics'; items: { label: string; value: string }[] }
  | { type: 'paragraph'; text: string }

interface AIAnswerRendererProps {
  content: string
  sources?: string[]
  className?: string
}

function stripMarkdownDecorators(text: string): string {
  return text.replace(/\*\*/g, '').replace(/\*/g, '').replace(/`/g, '').trim()
}

function isMetricLine(line: string): { label: string; value: string } | null {
  const trimmed = line.trim()
  const match = trimmed.match(/^(?:\*\*)?(.+?)(?:\*\*)?:\s*(.+)$/)
  if (!match) return null

  const label = stripMarkdownDecorators(match[1])
  const value = stripMarkdownDecorators(match[2])
  const lower = label.toLowerCase()

  if (!METRIC_KEYWORDS.some((kw) => lower.includes(kw))) return null
  return { label, value }
}

function isTableRow(line: string): boolean {
  const trimmed = line.trim()
  return trimmed.startsWith('|') && trimmed.endsWith('|') && trimmed.includes('|')
}

function parseTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => stripMarkdownDecorators(cell.trim()))
}

function isTableSeparator(line: string): boolean {
  return /^\|?[\s:-]+\|[\s|:-]+\|?$/.test(line.trim())
}

function parseBlocks(content: string): Block[] {
  const lines = content.replace(/\r\n/g, '\n').split('\n')
  const blocks: Block[] = []
  let i = 0

  function flushMetrics(buffer: { label: string; value: string }[]) {
    if (buffer.length > 0) {
      blocks.push({ type: 'metrics', items: [...buffer] })
      buffer.length = 0
    }
  }

  const metricBuffer: { label: string; value: string }[] = []

  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()

    if (!trimmed) {
      flushMetrics(metricBuffer)
      i += 1
      continue
    }

    const headingMatch = trimmed.match(/^(#{1,3})\s+(.+)$/)
    if (headingMatch) {
      flushMetrics(metricBuffer)
      blocks.push({
        type: 'heading',
        level: headingMatch[1].length,
        text: stripMarkdownDecorators(headingMatch[2]),
      })
      i += 1
      continue
    }

    if (isTableRow(trimmed)) {
      flushMetrics(metricBuffer)
      const tableLines: string[] = []
      while (i < lines.length && isTableRow(lines[i].trim())) {
        tableLines.push(lines[i].trim())
        i += 1
      }
      const dataRows = tableLines.filter((row) => !isTableSeparator(row))
      if (dataRows.length > 0) {
        const headers = parseTableRow(dataRows[0])
        const rows = dataRows.slice(1).map(parseTableRow)
        blocks.push({ type: 'table', headers, rows })
      }
      continue
    }

    if (trimmed.startsWith('>')) {
      flushMetrics(metricBuffer)
      const quoteLines: string[] = []
      while (i < lines.length && lines[i].trim().startsWith('>')) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ''))
        i += 1
      }
      blocks.push({ type: 'blockquote', lines: quoteLines })
      continue
    }

    const metric = isMetricLine(trimmed)
    if (metric) {
      metricBuffer.push(metric)
      i += 1
      continue
    }

    if (/^[-*•]\s+/.test(trimmed)) {
      flushMetrics(metricBuffer)
      const items: string[] = []
      while (i < lines.length && /^[-*•]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*•]\s+/, ''))
        i += 1
      }
      blocks.push({ type: 'ul', items })
      continue
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      flushMetrics(metricBuffer)
      const items: string[] = []
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+\.\s+/, ''))
        i += 1
      }
      blocks.push({ type: 'ol', items })
      continue
    }

    flushMetrics(metricBuffer)
    const paragraphLines: string[] = [trimmed]
    i += 1
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].trim().startsWith('#') &&
      !isTableRow(lines[i].trim()) &&
      !lines[i].trim().startsWith('>') &&
      !/^[-*•]\s+/.test(lines[i].trim()) &&
      !/^\d+\.\s+/.test(lines[i].trim()) &&
      !isMetricLine(lines[i].trim())
    ) {
      paragraphLines.push(lines[i].trim())
      i += 1
    }
    blocks.push({ type: 'paragraph', text: paragraphLines.join(' ') })
  }

  flushMetrics(metricBuffer)
  return blocks
}

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = []
  const pattern = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g
  let lastIndex = 0
  let match: RegExpExecArray | null
  let partIndex = 0

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(
        <Fragment key={`${keyPrefix}-t-${partIndex++}`}>
          {text.slice(lastIndex, match.index)}
        </Fragment>,
      )
    }

    const token = match[0]
    if (token.startsWith('**')) {
      nodes.push(
        <strong key={`${keyPrefix}-b-${partIndex++}`} className="font-semibold text-violet-50">
          {token.slice(2, -2)}
        </strong>,
      )
    } else if (token.startsWith('`')) {
      nodes.push(
        <code
          key={`${keyPrefix}-c-${partIndex++}`}
          className="rounded bg-violet-500/15 px-1.5 py-0.5 font-mono text-xs text-violet-200"
        >
          {token.slice(1, -1)}
        </code>,
      )
    } else {
      nodes.push(
        <em key={`${keyPrefix}-i-${partIndex++}`} className="text-violet-100/90">
          {token.slice(1, -1)}
        </em>,
      )
    }
    lastIndex = match.index + token.length
  }

  if (lastIndex < text.length) {
    nodes.push(
      <Fragment key={`${keyPrefix}-t-${partIndex++}`}>{text.slice(lastIndex)}</Fragment>,
    )
  }

  return nodes.length > 0 ? nodes : [text]
}

function HeadingBlock({ level, text }: { level: number; text: string }) {
  const Tag = level <= 2 ? 'h2' : 'h3'
  return (
    <Tag
      className={cn(
        'border-b border-violet-500/20 pb-2 font-semibold tracking-tight text-violet-50',
        level === 1 && 'text-xl',
        level === 2 && 'text-lg',
        level >= 3 && 'text-base',
      )}
    >
      {text}
    </Tag>
  )
}

function MetricGrid({ items }: { items: { label: string; value: string }[] }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => (
        <div
          key={`${item.label}-${item.value}`}
          className="rounded-xl border border-violet-500/20 bg-violet-950/30 px-4 py-3"
        >
          <p className="text-[10px] font-semibold uppercase tracking-wider text-violet-300/80">
            {item.label}
          </p>
          <p className="mt-1 text-sm font-semibold text-foreground">{item.value}</p>
        </div>
      ))}
    </div>
  )
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-2">
      {items.map((item, idx) => (
        <li
          key={`${idx}-${item.slice(0, 24)}`}
          className="flex gap-3 rounded-xl border border-violet-500/15 bg-violet-950/20 px-4 py-3 text-sm leading-relaxed text-violet-50/95"
        >
          <span className="mt-2 size-1.5 shrink-0 rounded-full bg-violet-400" />
          <span>{renderInline(item, `ul-${idx}`)}</span>
        </li>
      ))}
    </ul>
  )
}

function NumberedList({ items }: { items: string[] }) {
  return (
    <ol className="space-y-2">
      {items.map((item, idx) => (
        <li
          key={`${idx}-${item.slice(0, 24)}`}
          className="flex gap-3 rounded-xl border border-violet-500/15 bg-violet-950/20 px-4 py-3 text-sm leading-relaxed text-violet-50/95"
        >
          <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-violet-500/20 text-xs font-semibold text-violet-200">
            {idx + 1}
          </span>
          <span className="pt-0.5">{renderInline(item, `ol-${idx}`)}</span>
        </li>
      ))}
    </ol>
  )
}

function DataTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-violet-500/20 bg-violet-950/20">
      <table className="w-full min-w-[320px] text-sm">
        <thead>
          <tr className="border-b border-violet-500/20 bg-violet-500/10">
            {headers.map((header) => (
              <th
                key={header}
                className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-violet-200"
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIdx) => (
            <tr key={rowIdx} className="border-b border-violet-500/10 last:border-0">
              {row.map((cell, cellIdx) => (
                <td key={cellIdx} className="px-4 py-2.5 text-violet-50/90">
                  {renderInline(cell, `t-${rowIdx}-${cellIdx}`)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CitationBlock({ sources }: { sources: string[] }) {
  return (
    <div className="rounded-xl border border-violet-500/15 bg-background/30 px-4 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-violet-300/80">
        Sources
      </p>
      <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
        {sources.join(' · ')}
      </p>
    </div>
  )
}

export function AIAnswerRenderer({ content, sources, className }: AIAnswerRendererProps) {
  const blocks = useMemo(() => parseBlocks(content), [content])

  return (
    <div className={cn('ai-answer space-y-5 text-sm leading-relaxed', className)}>
      {blocks.map((block, idx) => {
        switch (block.type) {
          case 'heading':
            return (
              <div key={idx} className="pt-1">
                <HeadingBlock level={block.level} text={block.text} />
              </div>
            )
          case 'metrics':
            return <MetricGrid key={idx} items={block.items} />
          case 'ul':
            return <BulletList key={idx} items={block.items} />
          case 'ol':
            return <NumberedList key={idx} items={block.items} />
          case 'table':
            return <DataTable key={idx} headers={block.headers} rows={block.rows} />
          case 'blockquote':
            return (
              <blockquote
                key={idx}
                className="rounded-xl border-l-4 border-violet-400/50 bg-violet-500/10 px-4 py-3 text-sm italic text-violet-100/90"
              >
                {block.lines.map((line, lineIdx) => (
                  <p key={lineIdx} className={lineIdx > 0 ? 'mt-2' : undefined}>
                    {renderInline(line, `q-${idx}-${lineIdx}`)}
                  </p>
                ))}
              </blockquote>
            )
          case 'paragraph':
            return (
              <p key={idx} className="text-[15px] leading-7 text-violet-50/90">
                {renderInline(block.text, `p-${idx}`)}
              </p>
            )
          default:
            return null
        }
      })}
      {sources && sources.length > 0 && <CitationBlock sources={sources} />}
    </div>
  )
}
