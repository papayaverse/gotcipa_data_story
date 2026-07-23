"""Best-effort domain/email enrichment for GotCIPA audit exports (no IP/geo)."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "aol.com",
    "me.com",
    "live.com",
    "msn.com",
    "protonmail.com",
    "proton.me",
    "gmx.net",
    "mail.com",
}

INTERNAL_EMAIL_PATTERNS = (
    re.compile(r"@papayaverse\.com$", re.I),
    re.compile(r"@papayacomply\.ai$", re.I),
    re.compile(r"@uchicago\.edu$", re.I),
    re.compile(r"@berkeley\.edu$", re.I),
)

DISPOSABLE_EMAIL_PATTERNS = (
    re.compile(r"mailinator", re.I),
    re.compile(r"tempmail", re.I),
    re.compile(r"guerrillamail", re.I),
)

ENTERPRISE_DOMAINS = {
    "amgen.com",
    "nature.com",
    "funko.com",
    "tractorsupply.com",
    "kpmg.com",
    "ycombinator.com",
    "dc.com",
    "ipsen.com",
    "borsheims.com",
    "chicagobooth.edu",
    "vanderbilt.edu",
}

SECTOR_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("Veterinary / pet care", re.compile(r"vet|pet|animal|paws|tail", re.I)),
    ("Restaurant / hospitality supply", re.compile(r"restaurant|ware|kitchen|dining|hospitality", re.I)),
    ("Jewelry / retail", re.compile(r"jewel|retail|shop|store|boutique", re.I)),
    ("Healthcare / pharma", re.compile(r"health|pharma|rx|hcp|medical|clinic|hospital|ipsen|amgen", re.I)),
    ("Insurance", re.compile(r"insurance|insur", re.I)),
    ("Education", re.compile(r"\.edu|school|university|college|booth", re.I)),
    ("Government / public sector", re.compile(r"\.gov|montana|statefund|workingfor", re.I)),
    ("Automotive", re.compile(r"auto|car|motor|vehicle", re.I)),
    ("E-commerce / DTC", re.compile(r"custom|commerce|cart|marketing", re.I)),
    ("Publishing / media", re.compile(r"nature\.com|media|press|news", re.I)),
]

SECTOR_DISPLAY = {
    "Veterinary / pet care": "Regional veterinary or pet-care business",
    "Restaurant / hospitality supply": "Restaurant or hospitality supplier",
    "Jewelry / retail": "Independent jewelry or specialty retailer",
    "Healthcare / pharma": "Healthcare or life-sciences organization",
    "Insurance": "Insurance or benefits provider",
    "Education": "College or university property",
    "Government / public sector": "Public-agency or state-related site",
    "Automotive": "Automotive dealer or services",
    "E-commerce / DTC": "Direct-to-consumer or e-commerce brand",
    "Publishing / media": "Publisher or media property",
    "General commerce": "General commercial website",
}


def parse_dt(raw: str) -> datetime | None:
    if not raw:
        return None
    s = raw.strip()
    if s.endswith("+00"):
        s = s[:-3] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def url_domain(url: str) -> str:
    try:
        u = urlparse(url if "://" in url else f"https://{url}")
        host = (u.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def email_domain(email: str) -> str:
    e = (email or "").lower().strip()
    if "@" not in e:
        return ""
    return e.split("@", 1)[1]


def is_internal_email(email: str) -> bool:
    e = (email or "").lower()
    return any(p.search(e) for p in INTERNAL_EMAIL_PATTERNS)


def is_disposable_email(email: str) -> bool:
    e = (email or "").lower()
    return any(p.search(e) for p in DISPOSABLE_EMAIL_PATTERNS)


def is_noise_lead(email: str) -> bool:
    return is_internal_email(email) or is_disposable_email(email)


def org_type_from_signals(email: str, audit_domain: str) -> str:
    ed = email_domain(email)
    if ed.endswith(".gov") or ".gov" in audit_domain:
        return "public_agency"
    if ed.endswith(".edu") or audit_domain.endswith(".edu"):
        return "education"
    if ed.endswith(".org") or audit_domain.endswith(".org"):
        return "nonprofit_org"
    if ed.endswith(".mil"):
        return "public_agency"
    return "commercial"


def size_proxy(
    audit_domain: str,
    email: str | None,
    org_type: str,
    optional_band: str | None = None,
) -> str:
    if optional_band:
        return optional_band
    if org_type in ("public_agency", "education", "nonprofit_org"):
        return "agency_edu_nonprofit"
    if audit_domain in ENTERPRISE_DOMAINS:
        return "enterprise_known"
    ed = email_domain(email or "")
    if audit_domain.endswith(".com") and audit_domain not in ENTERPRISE_DOMAINS:
        if not email or ed == audit_domain or ed in FREE_EMAIL_DOMAINS:
            return "likely_smb"
    return "unknown"


def sector_tags(domain: str, optional_sector: str | None = None) -> list[str]:
    if optional_sector:
        return [optional_sector]
    tags: list[str] = []
    for name, pat in SECTOR_RULES:
        if pat.search(domain):
            tags.append(name)
    if not tags:
        tags.append("General commerce")
    return tags


def primary_sector(tags: list[str]) -> str:
    for t in tags:
        if t != "General commerce":
            return t
    return tags[0] if tags else "General commerce"


def anonymized_example(sector: str, count_in_sector: int) -> str:
    base = SECTOR_DISPLAY.get(sector, sector)
    if count_in_sector >= 3:
        return f"{base} (one of several similar sites in this dataset)"
    return base


@dataclass
class DomainProfile:
    domain: str
    request_count: int = 0
    lead_count: int = 0
    org_types: Counter = field(default_factory=Counter)
    size_buckets: Counter = field(default_factory=Counter)
    sectors: list[str] = field(default_factory=list)
    optional_sector: str | None = None
    optional_employee_band: str | None = None


def enrich_domain(
    domain: str,
    emails: list[str],
    optional_row: dict[str, str] | None = None,
) -> DomainProfile:
    row = optional_row or {}
    opt_sector = row.get("sector") or None
    opt_band = row.get("employee_band") or None
    profile = DomainProfile(domain=domain)
    profile.optional_sector = opt_sector
    profile.optional_employee_band = opt_band
    profile.sectors = sector_tags(domain, opt_sector)

    sample_email = next((e for e in emails if e and not is_noise_lead(e)), emails[0] if emails else "")
    ot = org_type_from_signals(sample_email, domain)
    profile.org_types[ot] += 1
    sz = size_proxy(domain, sample_email, ot, opt_band)
    profile.size_buckets[sz] += 1
    return profile


def week_label(dt: datetime) -> str:
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def compute_aggregates(
    leads: list[dict[str, str]],
    requests: list[dict[str, str]],
    *,
    reference_end: datetime | None = None,
) -> dict:
    """Build all story metrics from raw lead/request rows."""

    ref_end = reference_end or max(
        (parse_dt(r.get("created_at", "")) for r in leads + requests),
        key=lambda x: x or datetime.min.replace(tzinfo=timezone.utc),
        default=datetime.now(timezone.utc),
    )
    if ref_end.tzinfo is None:
        ref_end = ref_end.replace(tzinfo=timezone.utc)
    cut_14 = ref_end - timedelta(days=14)
    cut_28 = ref_end - timedelta(days=28)

    # --- requests ---
    req_by_week = Counter()
    req_domains_by_week: dict[str, set[str]] = defaultdict(set)
    domain_req_count: Counter = Counter()
    full_session_count = 0

    for r in requests:
        dt = parse_dt(r.get("created_at", ""))
        dom = url_domain(r.get("url", ""))
        if not dom:
            continue
        domain_req_count[dom] += 1
        if dt:
            wk = week_label(dt)
            req_by_week[wk] += 1
            req_domains_by_week[wk].add(dom)
        if r.get("accept_session_id") and r.get("gpc_session_id"):
            full_session_count += 1

    unique_req_domains = set(domain_req_count.keys())
    repeat_testers = [
        {"domain": d, "count": c}
        for d, c in domain_req_count.most_common()
        if c >= 5
    ]

    req_last_14 = sum(
        1 for r in requests if (parse_dt(r.get("created_at", "")) or datetime.min.replace(tzinfo=timezone.utc)) >= cut_14
    )
    req_prior_14 = sum(
        1
        for r in requests
        if cut_28 <= (parse_dt(r.get("created_at", "")) or datetime.min.replace(tzinfo=timezone.utc)) < cut_14
    )
    uniq_dom_last_14 = len(
        {
            url_domain(r.get("url", ""))
            for r in requests
            if (parse_dt(r.get("created_at", "")) or datetime.min.replace(tzinfo=timezone.utc)) >= cut_14
            and url_domain(r.get("url", ""))
        }
    )
    uniq_dom_prior_14 = len(
        {
            url_domain(r.get("url", ""))
            for r in requests
            if cut_28
            <= (parse_dt(r.get("created_at", "")) or datetime.min.replace(tzinfo=timezone.utc))
            < cut_14
            and url_domain(r.get("url", ""))
        }
    )

    weekly_requests = [
        {"week": wk, "audits": req_by_week[wk], "unique_domains": len(req_domains_by_week[wk])}
        for wk in sorted(req_by_week.keys())
    ]

    # --- leads ---
    lead_by_week = Counter()
    all_emails: set[str] = set()
    user_emails: set[str] = set()
    filtered_leads = 0
    domain_lead_emails: dict[str, list[str]] = defaultdict(list)
    verdicts = Counter()

    for row in leads:
        dt = parse_dt(row.get("created_at", ""))
        email = (row.get("email") or "").lower()
        dom = url_domain(row.get("audit_url") or row.get("url", ""))
        verdict = row.get("verdict") or ""
        if verdict:
            verdicts[verdict] += 1
        if email:
            all_emails.add(email)
            domain_lead_emails[dom].append(email)
        if is_noise_lead(email):
            filtered_leads += 1
        else:
            if email:
                user_emails.add(email)
        if dt:
            lead_by_week[week_label(dt)] += 1

    leads_last_14 = sum(
        1
        for row in leads
        if (parse_dt(row.get("created_at", "")) or datetime.min.replace(tzinfo=timezone.utc)) >= cut_14
        and not is_noise_lead(row.get("email", ""))
    )
    leads_prior_14 = sum(
        1
        for row in leads
        if cut_28
        <= (parse_dt(row.get("created_at", "")) or datetime.min.replace(tzinfo=timezone.utc))
        < cut_14
        and not is_noise_lead(row.get("email", ""))
    )

    weekly_leads = [{"week": wk, "leads": lead_by_week[wk]} for wk in sorted(lead_by_week.keys())]

    # --- enrich unique domains (from requests, primary universe) ---
    org_type_counts: Counter = Counter()
    size_counts: Counter = Counter()
    sector_counts: Counter = Counter()
    profiles: dict[str, DomainProfile] = {}

    for dom in unique_req_domains:
        emails = domain_lead_emails.get(dom, [])
        prof = enrich_domain(dom, emails)
        prof.request_count = domain_req_count[dom]
        prof.lead_count = len(emails)
        profiles[dom] = prof
        ot = prof.org_types.most_common(1)[0][0] if prof.org_types else "commercial"
        org_type_counts[ot] += 1
        sz = prof.size_buckets.most_common(1)[0][0] if prof.size_buckets else "unknown"
        size_counts[sz] += 1
        sector_counts[primary_sector(prof.sectors)] += 1

    sector_audit_counts: Counter = Counter()
    for r in requests:
        dom = url_domain(r.get("url", ""))
        if not dom:
            continue
        prof = profiles.get(dom)
        sector = primary_sector(prof.sectors) if prof else primary_sector(sector_tags(dom))
        sector_audit_counts[sector] += 1

    # Lead-only org signals (email-based, for "who is checking")
    lead_org_type = Counter()
    for row in leads:
        email = row.get("email", "")
        if is_noise_lead(email):
            continue
        dom = url_domain(row.get("audit_url", ""))
        lead_org_type[org_type_from_signals(email, dom)] += 1

    # Anonymized examples (one per sector, max 10)
    examples: list[str] = []
    seen_sectors: set[str] = set()
    for sector, _ in sector_audit_counts.most_common():
        if sector in seen_sectors:
            continue
        seen_sectors.add(sector)
        n = sector_audit_counts[sector]
        examples.append(anonymized_example(sector, n))
        if len(examples) >= 10:
            break

    public_agency_signal = org_type_counts.get("public_agency", 0) >= 1
    public_agency_note = (
        "Public-agency signals are present in the dataset (e.g. .gov email or government-related domains)."
        if public_agency_signal
        else None
    )
    if org_type_counts.get("public_agency", 0) < 3:
        public_agency_note = (
            "At least one public-sector signal appears in aggregate; individual contacts are not listed."
            if public_agency_signal
            else None
        )

    free_email_leads = sum(
        1 for row in leads if email_domain(row.get("email", "")) in FREE_EMAIL_DOMAINS and not is_noise_lead(row.get("email", ""))
    )
    user_lead_rows = sum(1 for row in leads if not is_noise_lead(row.get("email", "")))

    return {
        "meta": {
            "generated_for": "Liz Tulasi / ACTUM (private draft)",
            "reference_end": ref_end.date().isoformat(),
            "data_sources": ["audit_leads.csv", "audit_requests.csv"],
        },
        "volume": {
            "total_audit_requests": len(requests),
            "unique_domains_audited": len(unique_req_domains),
            "total_leads": len(leads),
            "unique_emails_all": len(all_emails),
            "unique_emails_users": len(user_emails),
            "leads_filtered_internal_test": filtered_leads,
            "user_lead_rows": user_lead_rows,
            "free_email_user_leads": free_email_leads,
            "full_accept_gpc_sessions": full_session_count,
            "repeat_testers_5plus": repeat_testers,
        },
        "spike": {
            "requests_last_14d": req_last_14,
            "requests_prior_14d": req_prior_14,
            "unique_domains_last_14d": uniq_dom_last_14,
            "unique_domains_prior_14d": uniq_dom_prior_14,
            "leads_last_14d": leads_last_14,
            "leads_prior_14d": leads_prior_14,
        },
        "weekly_requests": weekly_requests,
        "weekly_leads": weekly_leads,
        "org_type_unique_domains": dict(org_type_counts),
        "org_type_lead_rows": dict(lead_org_type),
        "size_proxy_unique_domains": dict(size_counts),
        "sector_unique_domains": dict(sector_counts.most_common(15)),
        "sector_audit_counts": dict(sector_audit_counts.most_common(15)),
        "verdicts_leads": dict(verdicts),
        "anonymized_examples": examples,
        "public_agency_note": public_agency_note,
        "methodology": {
            "no_ip_geo": True,
            "size_proxy_inferred": True,
            "sector_keyword_inferred": True,
            "verdict_sparse": sum(verdicts.values()) < len(leads) * 0.2,
            "optional_columns_supported": ["sector", "employee_band", "tracker_vendors"],
        },
    }
