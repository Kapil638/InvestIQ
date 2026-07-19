"""Sample Yahoo Finance payloads for tests."""

SAMPLE_YAHOO_INFO = {
    "symbol": "INFY.NS",
    "longName": "Infosys Limited",
    "shortName": "Infosys",
    "exchange": "NSI",
    "sector": "Technology",
    "industry": "Information Technology Services",
    "country": "India",
    "currency": "INR",
    "marketCap": 700000000000,
    "regularMarketPrice": 1500.0,
    "currentPrice": 1500.0,
    "beta": 0.9,
    "longBusinessSummary": "Infosys provides IT consulting and services.",
    "website": "https://www.infosys.com",
    "previousClose": 1490.0,
    "dayHigh": 1510.0,
    "dayLow": 1485.0,
    "fiftyTwoWeekHigh": 1700.0,
    "fiftyTwoWeekLow": 1200.0,
    "volume": 2000000,
    "averageVolume": 1800000,
    "trailingPE": 25.5,
    "priceToBook": 8.2,
    "returnOnEquity": 0.28,
    "debtToEquity": 0.05,
    "revenueGrowth": 0.12,
    "profitMargins": 0.18,
    "grossMargins": 0.32,
    "returnOnAssets": 0.15,
    "currentRatio": 2.1,
    "dividendYield": 0.02,
    "revenuePerShare": 250.0,
    "trailingEps": 58.0,
    "enterpriseValue": 720000000000,
    "enterpriseToEbitda": 18.0,
}

SAMPLE_FMP_PROFILE = {
    "symbol": "AAPL",
    "companyName": "Apple Inc.",
    "exchangeShortName": "NASDAQ",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "country": "US",
    "currency": "USD",
    "mktCap": 3000000000000,
    "price": 190.0,
    "beta": 1.2,
    "description": "Apple designs consumer electronics.",
    "ceo": "Tim Cook",
    "website": "https://www.apple.com",
    "ipoDate": "1980-12-12",
}

SAMPLE_INCOME = [
    {
        "date": "2024-09-28",
        "period": "FY",
        "revenue": 1000000,
        "grossProfit": 400000,
        "operatingIncome": 300000,
        "netIncome": 250000,
        "eps": 6.5,
        "ebitda": 350000,
    }
]

SAMPLE_BALANCE = [
    {
        "date": "2024-09-28",
        "period": "FY",
        "totalAssets": 500000,
        "totalLiabilities": 200000,
        "totalStockholdersEquity": 300000,
        "totalDebt": 100000,
        "cashAndCashEquivalents": 50000,
    }
]

SAMPLE_CASHFLOW = [
    {
        "date": "2024-09-28",
        "period": "FY",
        "netCashProvidedByOperatingActivities": 120000,
        "netCashUsedForInvestingActivities": -30000,
        "netCashUsedProvidedByFinancingActivities": -40000,
        "freeCashFlow": 90000,
        "capitalExpenditure": -10000,
    }
]

SAMPLE_RATIOS = [
    {
        "date": "2024-09-28",
        "period": "FY",
        "currentRatio": 1.5,
        "debtEquityRatio": 1.2,
        "returnOnEquity": 0.25,
        "returnOnAssets": 0.15,
        "grossProfitMargin": 0.4,
        "netProfitMargin": 0.25,
        "priceEarningsRatio": 28.0,
        "priceToBookRatio": 35.0,
    }
]

SAMPLE_METRICS = [
    {
        "date": "2024-09-28",
        "period": "FY",
        "revenuePerShare": 25.0,
        "netIncomePerShare": 6.5,
        "enterpriseValue": 3100000000000,
        "enterpriseValueOverEBITDA": 22.0,
        "peRatio": 28.0,
        "pbRatio": 35.0,
    }
]
