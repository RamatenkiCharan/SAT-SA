"""
Export API Endpoints.
Generates comprehensive supervisory assessment reports in structured JSON or printable format.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from analytics.explainability.templates import generate_finding_explanation
from backend.repositories.in_memory_repo import SATRepository, get_repository

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/report")
def export_supervisory_report(
    dataset_version_id: Optional[UUID] = None,
    repo: SATRepository = Depends(get_repository),
):
    ver_id = dataset_version_id or repo.active_dataset_version_id
    if not ver_id:
        raise HTTPException(status_code=400, detail="No active dataset version.")

    findings = repo.get_findings(dataset_version_id=ver_id)
    canonical_ds = repo.canonical_datasets.get(ver_id)
    reconstructed_ds = repo.reconstructed_datasets.get(ver_id)

    if not canonical_ds or not reconstructed_ds:
        raise HTTPException(status_code=404, detail="Dataset version records not found.")

    findings_summary = []
    for f in findings:
        exp = generate_finding_explanation(f)
        cse = reconstructed_ds.cse_by_id.get(f.cse_id)
        findings_summary.append(
            {
                "finding_id": str(f.finding_id),
                "cse_name": cse.name if cse else "Unknown",
                "sector": cse.sector if cse else "Unknown",
                "finding_type": f.finding_type.value,
                "priority_score": round(f.priority_score, 3),
                "priority_label": exp["priority_label"],
                "headline": exp["headline"],
                "recommended_action": exp["recommended_action"],
                "supporting_signals": f.supporting_signals,
                "contradicting_signals": f.contradicting_signals,
                "review_status": f.review_status.value if f.review_status else "PENDING_REVIEW",
                "review_notes": f.review_notes,
            }
        )

    return {
        "report_title": "SAT-SA Supervisory SOC Operational Assessment Report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_version_id": str(ver_id),
        "total_critical_sector_entities": len(canonical_ds.cse_list),
        "total_alerts_analyzed": len(canonical_ds.alerts),
        "total_findings": len(findings),
        "high_priority_findings": sum(1 for f in findings if f.priority_score >= 0.75),
        "findings": findings_summary,
    }


@router.get("/report/html", response_class=HTMLResponse)
def export_supervisory_html_report(
    dataset_version_id: Optional[UUID] = None,
    repo: SATRepository = Depends(get_repository),
):
    from fastapi.responses import HTMLResponse

    ver_id = dataset_version_id or repo.active_dataset_version_id
    if not ver_id:
        raise HTTPException(status_code=400, detail="No active dataset version.")

    findings = repo.get_findings(dataset_version_id=ver_id)
    canonical_ds = repo.canonical_datasets.get(ver_id)
    reconstructed_ds = repo.reconstructed_datasets.get(ver_id)
    dataset_meta = repo.dataset_versions.get(ver_id)

    if not canonical_ds or not reconstructed_ds:
        raise HTTPException(status_code=404, detail="Dataset version records not found.")

    findings_rows = ""
    for idx, f in enumerate(findings, start=1):
        exp = generate_finding_explanation(f)
        cse = reconstructed_ds.cse_by_id.get(f.cse_id)
        cse_name = cse.name if cse else "Unknown"
        sector = cse.sector if cse else "Unknown"
        status = f.review_status.value if f.review_status else "PENDING_REVIEW"
        p_badge = "background:#ef4444;color:#fff;" if f.priority_score >= 0.75 else ("background:#f59e0b;color:#000;" if f.priority_score >= 0.5 else "background:#3b82f6;color:#fff;")

        findings_rows += f"""
        <tr>
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;">#{idx}</td>
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;"><strong>{cse_name}</strong><br><small style="color:#64748b;">{sector}</small></td>
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;"><span style="display:inline-block;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:bold;{p_badge}">{exp['priority_label']} ({f.priority_score*100:.1f}%)</span></td>
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;"><strong>{exp['title']}</strong><br><small style="color:#334155;">{exp['headline']}</small></td>
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;font-size:12px;">{exp['recommended_action']}</td>
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;font-size:11px;font-weight:bold;">{status}</td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SAT-SA Executive Supervisory Assessment Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 40px; color: #0f172a; line-height: 1.5; }}
        .header {{ border-bottom: 2px solid #0f172a; padding-bottom: 20px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: flex-end; }}
        .badge {{ background: #0f172a; color: #fff; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: bold; letter-spacing: 0.5px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px; }}
        .stat-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px; }}
        .stat-num {{ font-size: 24px; font-weight: bold; color: #0f172a; }}
        .stat-label {{ font-size: 12px; color: #64748b; text-transform: uppercase; font-weight: 600; margin-top: 4px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 30px; }}
        th {{ text-align: left; padding: 10px; background: #f1f5f9; border-bottom: 2px solid #cbd5e1; font-size: 12px; text-transform: uppercase; color: #475569; }}
        .callout {{ background: #eff6ff; border-left: 4px solid #3b82f6; padding: 15px; margin-bottom: 30px; border-radius: 0 6px 6px 0; }}
        .callout-title {{ font-weight: bold; color: #1e40af; margin-bottom: 5px; }}
        @media print {{
            body {{ margin: 20px; font-size: 12px; }}
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="no-print" style="margin-bottom: 20px;">
        <button onclick="window.print()" style="background:#0284c7;color:#fff;border:none;padding:10px 18px;border-radius:6px;cursor:pointer;font-weight:bold;">🖨️ Print / Save as PDF</button>
    </div>

    <div class="header">
        <div>
            <span class="badge">NCIIPC OPERATIONAL AUDIT DOSSIER</span>
            <h1 style="margin: 10px 0 0 0; font-size: 24px;">SAT-SA SOC Supervisory Analytics Assessment Report</h1>
            <p style="margin: 5px 0 0 0; color: #64748b; font-size: 14px;">Smart India Hackathon Problem Statement 26157 — Air-Gapped Supervisory Evaluation</p>
        </div>
        <div style="text-align: right; font-size: 12px; color: #64748b;">
            <div><strong>Report Date:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
            <div><strong>Dataset Version:</strong> {str(ver_id)[:8]}...</div>
            <div><strong>Dataset Ref:</strong> {dataset_meta.source_file_ref if dataset_meta else 'Active Run'}</div>
        </div>
    </div>

    <div class="callout">
        <div class="callout-title">🎯 Executive Supervisory Summary (Evidence-to-Assurance Methodology)</div>
        <div style="font-size: 13px; color: #1e3a8a;">
            Conventional SOC audits evaluate self-reported KPIs (e.g., 98%+ SLA compliance). SAT-SA examines the empirical operational evidence (alerts, investigations, escalations, closures, and telemetry presence). This assessment reveals whether critical infrastructure defense operations match declared security postures without relying on unvalidated claims.
        </div>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-num">{len(canonical_ds.cse_list)}</div>
            <div class="stat-label">Critical Sector Entities</div>
        </div>
        <div class="stat-card">
            <div class="stat-num">{len(canonical_ds.alerts)}</div>
            <div class="stat-label">Alert Records Analyzed</div>
        </div>
        <div class="stat-card">
            <div class="stat-num">{len(findings)}</div>
            <div class="stat-label">Total Supervisory Findings</div>
        </div>
        <div class="stat-card">
            <div class="stat-num" style="color:#ef4444;">{sum(1 for f in findings if f.priority_score >= 0.75)}</div>
            <div class="stat-label">High Priority Gaps</div>
        </div>
    </div>

    <h2>📋 Prioritized Supervisory Findings & Review Queue</h2>
    <table>
        <thead>
            <tr>
                <th style="width: 50px;">Rank</th>
                <th style="width: 180px;">Entity & Sector</th>
                <th style="width: 130px;">Priority Score</th>
                <th>Finding Title & Rationale</th>
                <th style="width: 250px;">Recommended Supervisory Action</th>
                <th style="width: 110px;">Disposition</th>
            </tr>
        </thead>
        <tbody>
            {findings_rows}
        </tbody>
    </table>

    <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; font-size: 11px; color: #94a3b8; display: flex; justify-content: space-between;">
        <div>National Critical Information Infrastructure Protection Centre (NCIIPC) — Confidential Supervisory Material</div>
        <div>Generated by SAT-SA Air-Gapped Analytics Engine (Zero Outbound Network Requests)</div>
    </div>
</body>
</html>
    """
    return HTMLResponse(content=html_content)
