export type DataSourceSlug = 'tapetide_mcp' | 'local_master' | 'kite' | 'yahoo' | string

const SOURCE_LABELS: Record<string, string> = {
  nse: 'NSE',
  tapetide_mcp: 'Tapetide NSE/BSE MCP',
  local_master: 'Local Master',
  kite: 'Kite',
  yahoo: 'Yahoo',
  nse_bse_mcp: 'Tapetide NSE/BSE MCP',
  static: 'Local Master',
  'Kite Connect': 'Kite',
  'Yahoo Finance': 'Yahoo',
  'NSE/BSE MCP': 'Tapetide NSE/BSE MCP',
  'Tapetide NSE/BSE MCP': 'Tapetide NSE/BSE MCP',
  curated_large_cap: 'Curated Large-Cap List',
}

export function formatDataSourceLabel(source: string | null | undefined): string {
  if (!source) return 'Yahoo'
  return SOURCE_LABELS[source] ?? source
}
