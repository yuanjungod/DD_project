# Configuration Schema

This document describes the configuration contract shared by the frontend, backend, and agent service.

## Company Configuration

```json
{
  "target_company": {
    "name": "Example Robotics",
    "aliases": ["ExampleBot"],
    "website": "https://example.com",
    "jurisdiction": "China",
    "industry": "Robotics",
    "keywords": ["warehouse automation", "robot arm"]
  },
  "scope": {
    "time_range": "last 5 years",
    "focus_areas": ["business", "financial", "legal", "ownership", "public_opinion", "compliance"],
    "report_language": "zh-CN"
  },
  "resources": {
    "uploaded_files": [],
    "trusted_sources": ["official website", "exchange filings"],
    "blocked_sources": [],
    "competitors": ["Peer Robotics"]
  }
}
```

## Evidence

```json
{
  "id": "ev_001",
  "title": "Official website states product line",
  "source_type": "web",
  "source_url": "https://example.com/products",
  "excerpt": "Example Robotics provides warehouse automation robots.",
  "confidence": 0.82,
  "collected_by": "WebResearchAgent",
  "metadata": {
    "published_at": "2026-01-01"
  }
}
```

## Agent Result

```json
{
  "agent": "LegalRiskAgent",
  "status": "completed",
  "summary": "No high-severity legal risk found in configured sources.",
  "findings": [
    {
      "title": "No sanctions evidence found",
      "description": "Configured MVP sources did not return sanction matches.",
      "risk_level": "low",
      "confidence": 0.65,
      "evidence_ids": ["ev_003"]
    }
  ],
  "evidence": []
}
```

## Report Section

```json
{
  "title": "Legal and Compliance Risk",
  "summary": "The available evidence indicates low legal risk, subject to registry verification.",
  "risk_level": "low",
  "evidence_ids": ["ev_003"]
}
```

## Confidence Levels

- `0.80-1.00`: Strong source coverage.
- `0.60-0.79`: Useful but incomplete source coverage.
- `0.40-0.59`: Weak source coverage, requires manual review.
- `<0.40`: Treat as unverified.
