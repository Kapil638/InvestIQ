"""Last-resort static company catalogue when live search providers are unavailable."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StaticCompany:
    name: str
    ticker: str
    exchange: str
    sector: str | None = None
    aliases: tuple[str, ...] = ()


STATIC_INDIAN_COMPANIES: tuple[StaticCompany, ...] = (
    StaticCompany("Infosys Ltd", "INFY", "NSE", "Information Technology", ("infosys",)),
    StaticCompany("Reliance Industries Ltd", "RELIANCE", "NSE", "Oil & Gas", ("ril", "reliance")),
    StaticCompany("Tata Consultancy Services Ltd", "TCS", "NSE", "Information Technology", ("tcs",)),
    StaticCompany("HDFC Bank Ltd", "HDFCBANK", "NSE", "Financial Services", ("hdfc",)),
    StaticCompany("ICICI Bank Ltd", "ICICIBANK", "NSE", "Financial Services", ("icici",)),
    StaticCompany("State Bank of India", "SBIN", "NSE", "Financial Services", ("sbi",)),
    StaticCompany("Bharti Airtel Ltd", "BHARTIARTL", "NSE", "Telecommunication", ("airtel",)),
    StaticCompany("Larsen & Toubro Ltd", "LT", "NSE", "Industrials", ("larsen",)),
    StaticCompany("ITC Ltd", "ITC", "NSE", "Consumer Goods", ("itc",)),
    StaticCompany("Axis Bank Ltd", "AXISBANK", "NSE", "Financial Services", ("axis",)),
    StaticCompany("Kotak Mahindra Bank Ltd", "KOTAKBANK", "NSE", "Financial Services", ("kotak",)),
    StaticCompany("Hindustan Unilever Ltd", "HINDUNILVR", "NSE", "Consumer Goods", ("hul",)),
    StaticCompany("Wipro Ltd", "WIPRO", "NSE", "Information Technology", ("wipro",)),
    StaticCompany("Tech Mahindra Ltd", "TECHM", "NSE", "Information Technology", ("techm",)),
    StaticCompany("Tata Motors Ltd", "TATAMOTORS", "NSE", "Automobile", ("tata motors",)),
    StaticCompany("Tata Steel Ltd", "TATASTEEL", "NSE", "Metals & Mining", ("tata steel",)),
    StaticCompany("IndusInd Bank Ltd", "INDUSINDBK", "NSE", "Financial Services", ("indusind",)),
    StaticCompany("Indian Hotels Co Ltd", "INDHOTEL", "NSE", "Consumer Services", ("taj",)),
    StaticCompany("Indian Oil Corporation Ltd", "IOC", "NSE", "Oil & Gas", ("indian oil",)),
    StaticCompany("InfoBeans Technologies Ltd", "INFOBEAN", "NSE", "Information Technology", ("infobeans",)),
    StaticCompany("Infomedia Press Ltd", "INFOMEDIA", "BSE", "Media", ("infomedia",)),
    StaticCompany("Influx Healthtech Ltd", "INFLUX", "BSE", "Healthcare", ("influx",)),
    StaticCompany("HCL Technologies Ltd", "HCLTECH", "NSE", "Information Technology", ("hcl",)),
    StaticCompany("Asian Paints Ltd", "ASIANPAINT", "NSE", "Consumer Goods", ("asian paints",)),
    StaticCompany("Maruti Suzuki India Ltd", "MARUTI", "NSE", "Automobile", ("maruti",)),
    StaticCompany("Sun Pharmaceutical Industries Ltd", "SUNPHARMA", "NSE", "Healthcare", ("sun pharma",)),
)
