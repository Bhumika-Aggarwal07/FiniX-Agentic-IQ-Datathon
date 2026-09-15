# Dashboard guide

Run `python -m streamlit run app.py` after `python -m src.finix.pipeline`.

| Page | Question answered |
|---|---|
| Executive overview | What is the data scale and where should a reviewer start? |
| Transaction intelligence | How do transaction volume, status, value, and chargeback linkage behave? |
| Chargeback intelligence | Which disputes, reasons, severities, and linkage statuses warrant review? |
| KYC and identity | What is KYC coverage and which summaries show inconsistency or high-risk segments? |
| Merchant risk | Which merchants have unusual activity with transparent denominators? |
| Risk network | Which observed transaction relationships and relationship signals connect entities? |
| Investigation explorer | What does a deterministic query say about an entity or supported pattern? |
| Data quality | What cleaning, validation, linkage, and graph checks were performed? |

The dashboard caches generated CSV loads for 15 minutes. It has no write controls and never renders PAN, Aadhaar, full name, or settlement account values.
