export interface IndianCompany {
  name: string
  ticker: string
  exchange?: string
  sector?: string
  aliases?: string[]
}

/** Local catalogue for portfolio ticker resolution — search uses GET /api/v1/search/companies */
export const INDIAN_COMPANIES: IndianCompany[] = [
  { name: 'Infosys Ltd', ticker: 'INFY', exchange: 'NSE', sector: 'Information Technology', aliases: ['infosys'] },
  { name: 'Reliance Industries Ltd', ticker: 'RELIANCE', exchange: 'NSE', sector: 'Oil & Gas', aliases: ['ril', 'reliance'] },
  { name: 'Tata Consultancy Services Ltd', ticker: 'TCS', exchange: 'NSE', sector: 'Information Technology', aliases: ['tcs', 'tata consultancy'] },
  { name: 'HDFC Bank Ltd', ticker: 'HDFCBANK', exchange: 'NSE', sector: 'Financial Services', aliases: ['hdfc bank', 'hdfc'] },
  { name: 'ICICI Bank Ltd', ticker: 'ICICIBANK', exchange: 'NSE', sector: 'Financial Services', aliases: ['icici'] },
  { name: 'State Bank of India', ticker: 'SBIN', exchange: 'NSE', sector: 'Financial Services', aliases: ['sbi', 'state bank'] },
  { name: 'Bharti Airtel Ltd', ticker: 'BHARTIARTL', exchange: 'NSE', sector: 'Telecommunication', aliases: ['airtel', 'bharti'] },
  { name: 'Larsen & Toubro Ltd', ticker: 'LT', exchange: 'NSE', sector: 'Industrials', aliases: ['l&t', 'larsen'] },
  { name: 'ITC Ltd', ticker: 'ITC', exchange: 'NSE', sector: 'Consumer Goods', aliases: ['itc'] },
  { name: 'Axis Bank Ltd', ticker: 'AXISBANK', exchange: 'NSE', sector: 'Financial Services', aliases: ['axis'] },
  { name: 'Kotak Mahindra Bank Ltd', ticker: 'KOTAKBANK', exchange: 'NSE', sector: 'Financial Services', aliases: ['kotak'] },
  { name: 'Hindustan Unilever Ltd', ticker: 'HINDUNILVR', exchange: 'NSE', sector: 'Consumer Goods', aliases: ['hul', 'unilever'] },
  { name: 'Wipro Ltd', ticker: 'WIPRO', exchange: 'NSE', sector: 'Information Technology', aliases: ['wipro'] },
  { name: 'Tech Mahindra Ltd', ticker: 'TECHM', exchange: 'NSE', sector: 'Information Technology', aliases: ['tech mahindra', 'techm'] },
  { name: 'Tata Motors Ltd', ticker: 'TATAMOTORS', exchange: 'NSE', sector: 'Automobile', aliases: ['tata motors'] },
  { name: 'Tata Steel Ltd', ticker: 'TATASTEEL', exchange: 'NSE', sector: 'Metals & Mining', aliases: ['tata steel'] },
  { name: 'InfoBeans Technologies Ltd', ticker: 'INFOBEAN', exchange: 'NSE', sector: 'Information Technology', aliases: ['infobeans'] },
  { name: 'Infomedia Press Ltd', ticker: 'INFOMEDIA', exchange: 'BSE', sector: 'Media', aliases: ['infomedia'] },
  { name: 'Influx Healthtech Ltd', ticker: 'INFLUX', exchange: 'BSE', sector: 'Healthcare', aliases: ['influx'] },
  { name: 'HCL Technologies Ltd', ticker: 'HCLTECH', exchange: 'NSE', sector: 'Information Technology', aliases: ['hcl'] },
  { name: 'Asian Paints Ltd', ticker: 'ASIANPAINT', exchange: 'NSE', sector: 'Consumer Goods', aliases: ['asian paints'] },
  { name: 'Maruti Suzuki India Ltd', ticker: 'MARUTI', exchange: 'NSE', sector: 'Automobile', aliases: ['maruti'] },
  { name: 'Sun Pharmaceutical Industries Ltd', ticker: 'SUNPHARMA', exchange: 'NSE', sector: 'Healthcare', aliases: ['sun pharma'] },
  { name: 'Titan Company Ltd', ticker: 'TITAN', exchange: 'NSE', sector: 'Consumer Goods', aliases: ['titan'] },
  { name: 'Nestle India Ltd', ticker: 'NESTLEIND', exchange: 'NSE', sector: 'Consumer Goods', aliases: ['nestle'] },
]

export function findCompanyByTicker(ticker: string): IndianCompany | undefined {
  const upper = ticker.trim().toUpperCase()
  return INDIAN_COMPANIES.find((c) => c.ticker === upper)
}
