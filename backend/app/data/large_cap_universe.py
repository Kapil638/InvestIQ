"""Curated large-cap NSE universe — supplementary candidate source for the
Advisor's broad market-cap-tier requests only.

Deliberate, scoped exception to advisor_retrieval.py's "no hardcoded theme
universes" principle: that principle holds for THEMES (defence, AI, EV, etc.),
which genuinely shouldn't be hardcoded since they're subjective and shift
over time. "Large cap" is different — it's a well-defined, slow-changing
category (index constituents), and the alternative (fuzzy company-NAME
substring search) was surfacing obscure small-cap shell companies whose
legal names happen to contain generic words like "Investment" or "Quality".

This list is a supplementary SEED only — every candidate still goes through
the same real-data enrichment (financial_data_service) and validation
(AdvisorValidator.validate_market's market-cap check) as everything else, so a
stale or wrong entry here gets filtered out downstream, not blindly trusted.

Not exhaustive, not officially the Nifty 100 index — a reasonably diverse,
well-known set of large-cap names across sectors for advisor discovery.
Update only when a listed large-cap company changes name/ticker.
"""

from __future__ import annotations

LARGE_CAP_UNIVERSE: list[dict[str, str]] = [
    {"symbol": "RELIANCE", "company_name": "Reliance Industries Ltd", "sector": "Energy"},
    {"symbol": "TCS", "company_name": "Tata Consultancy Services Ltd", "sector": "Information Technology"},
    {"symbol": "HDFCBANK", "company_name": "HDFC Bank Ltd", "sector": "Financial Services"},
    {"symbol": "INFY", "company_name": "Infosys Ltd", "sector": "Information Technology"},
    {"symbol": "ICICIBANK", "company_name": "ICICI Bank Ltd", "sector": "Financial Services"},
    {"symbol": "HINDUNILVR", "company_name": "Hindustan Unilever Ltd", "sector": "Consumer Goods"},
    {"symbol": "ITC", "company_name": "ITC Ltd", "sector": "Consumer Goods"},
    {"symbol": "SBIN", "company_name": "State Bank of India", "sector": "Financial Services"},
    {"symbol": "BHARTIARTL", "company_name": "Bharti Airtel Ltd", "sector": "Telecommunication"},
    {"symbol": "KOTAKBANK", "company_name": "Kotak Mahindra Bank Ltd", "sector": "Financial Services"},
    {"symbol": "LT", "company_name": "Larsen & Toubro Ltd", "sector": "Industrials"},
    {"symbol": "AXISBANK", "company_name": "Axis Bank Ltd", "sector": "Financial Services"},
    {"symbol": "ASIANPAINT", "company_name": "Asian Paints Ltd", "sector": "Consumer Goods"},
    {"symbol": "MARUTI", "company_name": "Maruti Suzuki India Ltd", "sector": "Automobile"},
    {"symbol": "SUNPHARMA", "company_name": "Sun Pharmaceutical Industries Ltd", "sector": "Healthcare"},
    {"symbol": "TITAN", "company_name": "Titan Company Ltd", "sector": "Consumer Goods"},
    {"symbol": "ULTRACEMCO", "company_name": "UltraTech Cement Ltd", "sector": "Materials"},
    {"symbol": "BAJFINANCE", "company_name": "Bajaj Finance Ltd", "sector": "Financial Services"},
    {"symbol": "WIPRO", "company_name": "Wipro Ltd", "sector": "Information Technology"},
    {"symbol": "NESTLEIND", "company_name": "Nestle India Ltd", "sector": "Consumer Goods"},
    {"symbol": "ONGC", "company_name": "Oil and Natural Gas Corporation Ltd", "sector": "Energy"},
    {"symbol": "NTPC", "company_name": "NTPC Ltd", "sector": "Utilities"},
    {"symbol": "POWERGRID", "company_name": "Power Grid Corporation of India Ltd", "sector": "Utilities"},
    {"symbol": "TATASTEEL", "company_name": "Tata Steel Ltd", "sector": "Materials"},
    {"symbol": "TATAMOTORS", "company_name": "Tata Motors Ltd", "sector": "Automobile"},
    {"symbol": "M&M", "company_name": "Mahindra & Mahindra Ltd", "sector": "Automobile"},
    {"symbol": "HCLTECH", "company_name": "HCL Technologies Ltd", "sector": "Information Technology"},
    {"symbol": "ADANIENT", "company_name": "Adani Enterprises Ltd", "sector": "Industrials"},
    {"symbol": "ADANIPORTS", "company_name": "Adani Ports and Special Economic Zone Ltd", "sector": "Industrials"},
    {"symbol": "COALINDIA", "company_name": "Coal India Ltd", "sector": "Materials"},
    {"symbol": "GRASIM", "company_name": "Grasim Industries Ltd", "sector": "Materials"},
    {"symbol": "JSWSTEEL", "company_name": "JSW Steel Ltd", "sector": "Materials"},
    {"symbol": "BAJAJFINSV", "company_name": "Bajaj Finserv Ltd", "sector": "Financial Services"},
    {"symbol": "DRREDDY", "company_name": "Dr. Reddy's Laboratories Ltd", "sector": "Healthcare"},
    {"symbol": "CIPLA", "company_name": "Cipla Ltd", "sector": "Healthcare"},
    {"symbol": "DIVISLAB", "company_name": "Divi's Laboratories Ltd", "sector": "Healthcare"},
    {"symbol": "EICHERMOT", "company_name": "Eicher Motors Ltd", "sector": "Automobile"},
    {"symbol": "HEROMOTOCO", "company_name": "Hero MotoCorp Ltd", "sector": "Automobile"},
    {"symbol": "BRITANNIA", "company_name": "Britannia Industries Ltd", "sector": "Consumer Goods"},
    {"symbol": "APOLLOHOSP", "company_name": "Apollo Hospitals Enterprise Ltd", "sector": "Healthcare"},
    {"symbol": "INDUSINDBK", "company_name": "IndusInd Bank Ltd", "sector": "Financial Services"},
    {"symbol": "TECHM", "company_name": "Tech Mahindra Ltd", "sector": "Information Technology"},
    {"symbol": "UPL", "company_name": "UPL Ltd", "sector": "Materials"},
    {"symbol": "HDFCLIFE", "company_name": "HDFC Life Insurance Company Ltd", "sector": "Financial Services"},
    {"symbol": "SBILIFE", "company_name": "SBI Life Insurance Company Ltd", "sector": "Financial Services"},
    {"symbol": "BPCL", "company_name": "Bharat Petroleum Corporation Ltd", "sector": "Energy"},
    {"symbol": "IOC", "company_name": "Indian Oil Corporation Ltd", "sector": "Energy"},
    {"symbol": "SHREECEM", "company_name": "Shree Cement Ltd", "sector": "Materials"},
    {"symbol": "BAJAJ-AUTO", "company_name": "Bajaj Auto Ltd", "sector": "Automobile"},
    {"symbol": "HINDALCO", "company_name": "Hindalco Industries Ltd", "sector": "Materials"},
    {"symbol": "VEDL", "company_name": "Vedanta Ltd", "sector": "Materials"},
    {"symbol": "GAIL", "company_name": "GAIL (India) Ltd", "sector": "Energy"},
    {"symbol": "PIDILITIND", "company_name": "Pidilite Industries Ltd", "sector": "Materials"},
    {"symbol": "DABUR", "company_name": "Dabur India Ltd", "sector": "Consumer Goods"},
    {"symbol": "GODREJCP", "company_name": "Godrej Consumer Products Ltd", "sector": "Consumer Goods"},
    {"symbol": "SIEMENS", "company_name": "Siemens Ltd", "sector": "Industrials"},
    {"symbol": "DLF", "company_name": "DLF Ltd", "sector": "Real Estate"},
    {"symbol": "AMBUJACEM", "company_name": "Ambuja Cements Ltd", "sector": "Materials"},
    {"symbol": "BANKBARODA", "company_name": "Bank of Baroda", "sector": "Financial Services"},
    {"symbol": "PNB", "company_name": "Punjab National Bank", "sector": "Financial Services"},
    {"symbol": "CANBK", "company_name": "Canara Bank", "sector": "Financial Services"},
    {"symbol": "ZOMATO", "company_name": "Eternal Ltd", "sector": "Consumer Services"},
    {"symbol": "IRCTC", "company_name": "Indian Railway Catering and Tourism Corporation Ltd", "sector": "Consumer Services"},
    {"symbol": "TRENT", "company_name": "Trent Ltd", "sector": "Consumer Services"},
    {"symbol": "PIIND", "company_name": "PI Industries Ltd", "sector": "Materials"},
    {"symbol": "HAVELLS", "company_name": "Havells India Ltd", "sector": "Industrials"},
    {"symbol": "COLPAL", "company_name": "Colgate-Palmolive (India) Ltd", "sector": "Consumer Goods"},
    {"symbol": "MARICO", "company_name": "Marico Ltd", "sector": "Consumer Goods"},
    {"symbol": "BOSCHLTD", "company_name": "Bosch Ltd", "sector": "Automobile"},
    {"symbol": "BEL", "company_name": "Bharat Electronics Ltd", "sector": "Industrials"},
    {"symbol": "HAL", "company_name": "Hindustan Aeronautics Ltd", "sector": "Industrials"},
    {"symbol": "IRFC", "company_name": "Indian Railway Finance Corporation Ltd", "sector": "Financial Services"},
    {"symbol": "LICI", "company_name": "Life Insurance Corporation of India", "sector": "Financial Services"},
    {"symbol": "PFC", "company_name": "Power Finance Corporation Ltd", "sector": "Financial Services"},
    {"symbol": "RECLTD", "company_name": "REC Ltd", "sector": "Financial Services"},
]
