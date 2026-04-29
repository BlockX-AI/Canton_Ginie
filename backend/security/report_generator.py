"""
Enterprise Audit & Compliance Report Generator.

Generates reports in JSON, HTML, and Markdown formats
suitable for stakeholders, developers, and CI/CD pipelines.
"""

import json
from datetime import datetime, timezone
from html import escape


def generate_json_report(audit_result: dict, compliance_result: dict = None) -> str:
    """Generate machine-readable JSON report."""
    report = {
        "reportType": "enterprise-security-compliance",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "generator": "Ginie Enterprise Report Engine v2.0",
        "platform": "Canton",
        "language": "DAML",
    }

    if audit_result and audit_result.get("success"):
        report["securityAudit"] = {
            "score": audit_result.get("security_score", 0),
            "executiveSummary": audit_result.get("executive_summary", {}),
            "report": audit_result.get("audit_report", {}),
        }

    if compliance_result and compliance_result.get("success"):
        report["complianceAnalysis"] = {
            "score": compliance_result.get("compliance_score", 0),
            "profile": compliance_result.get("profile", "generic"),
            "executiveSummary": compliance_result.get("executive_summary", {}),
            "report": compliance_result.get("compliance_report", {}),
        }

    return json.dumps(report, indent=2, default=str)


def generate_markdown_report(audit_result: dict, compliance_result: dict = None) -> str:
    """Generate developer-friendly Markdown report."""
    lines = []
    lines.append("# Ginie Enterprise Security & Compliance Report")
    lines.append(f"\n**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("**Platform:** Canton | **Language:** DAML")
    lines.append("**Engine:** Ginie Enterprise Audit Engine v2.0\n")
    lines.append("---\n")

    # Security Audit Section
    if audit_result and audit_result.get("success"):
        es = audit_result.get("executive_summary", {})
        score = es.get("securityScore", 0)
        risk = es.get("overallRisk", "UNKNOWN")
        rec = es.get("recommendation", "UNKNOWN")

        lines.append("## Security Audit\n")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| **Security Score** | **{score}/100** |")
        lines.append(f"| **Overall Risk** | {risk} |")
        lines.append(f"| **Recommendation** | {rec} |")
        lines.append(f"| Critical Issues | {es.get('criticalIssues', 0)} |")
        lines.append(f"| High Issues | {es.get('highIssues', 0)} |")
        lines.append(f"| Medium Issues | {es.get('mediumIssues', 0)} |")
        lines.append(f"| Low Issues | {es.get('lowIssues', 0)} |")
        lines.append(f"| Informational | {es.get('informationalIssues', 0)} |")
        lines.append(f"| Optimizations | {es.get('optimizations', 0)} |\n")

        key_findings = es.get("keyFindings", [])
        if key_findings:
            lines.append("### Key Findings\n")
            for kf in key_findings:
                lines.append(f"- {kf}")
            lines.append("")

        findings = audit_result.get("audit_report", {}).get("findings", [])
        if findings:
            lines.append("### Detailed Findings\n")
            for f in findings:
                sev = f.get("severity", "INFO")
                icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵", "INFO": "ℹ️", "OPT": "⚡"}.get(sev, "❓")
                lines.append(f"#### {icon} [{sev}] {f.get('title', 'Untitled')}\n")
                if f.get("description"):
                    lines.append(f"{f['description']}\n")
                if f.get("location"):
                    loc = f["location"]
                    # Defensive: callers may pass ``{"template": None}``
                    # rather than omitting the key. ``dict.get(k, "")``
                    # returns ``None`` (not the default) when the value
                    # is explicitly None, so ``+= str`` would crash.
                    loc_str = loc.get("template") or ""
                    if loc.get("choice"):
                        loc_str += f"::{loc['choice']}"
                    lines.append(f"**Location:** `{loc_str}`\n")
                if f.get("impact"):
                    lines.append(f"**Impact:** {f['impact']}\n")
                if f.get("recommendation"):
                    lines.append(f"**Recommendation:** {f['recommendation']}\n")
                if f.get("references"):
                    lines.append(f"**References:** {', '.join(f['references'])}\n")
                if f.get("codeSnippet"):
                    lines.append(f"```daml\n{f['codeSnippet']}\n```\n")
                if f.get("fixedCode"):
                    lines.append(f"**Suggested Fix:**\n```daml\n{f['fixedCode']}\n```\n")

        roadmap = audit_result.get("audit_report", {}).get("remediationRoadmap", [])
        if roadmap:
            lines.append("### Remediation Roadmap\n")
            lines.append("| Priority | Category | Task | Effort | Impact |")
            lines.append("|----------|----------|------|--------|--------|")
            for item in sorted(roadmap, key=lambda x: x.get("priority", 99)):
                lines.append(
                    f"| {item.get('priority', '-')} | {item.get('category', '-')} "
                    f"| {item.get('task', '-')} | {item.get('effort', '-')} "
                    f"| {item.get('impact', '-')} |"
                )
            lines.append("")

    lines.append("---\n")

    # Compliance Section
    if compliance_result and compliance_result.get("success"):
        es = compliance_result.get("executive_summary", {})
        score = es.get("complianceScore", 0)
        overall = es.get("overallCompliance", "UNKNOWN")
        rec = es.get("recommendation", "UNKNOWN")
        profile = compliance_result.get("profile", "generic")

        lines.append("## Compliance Analysis\n")
        lines.append(f"**Profile:** {profile}\n")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| **Compliance Score** | **{score}/100** |")
        lines.append(f"| **Overall Status** | {overall} |")
        lines.append(f"| **Recommendation** | {rec} |")
        lines.append(f"| Controls Passed | {es.get('controlsPassed', 0)} |")
        lines.append(f"| Controls Failed | {es.get('controlsFailed', 0)} |")
        lines.append(f"| Controls Partial | {es.get('controlsPartial', 0)} |")
        lines.append(f"| Critical Gaps | {es.get('criticalGaps', 0)} |")
        lines.append(f"| High Gaps | {es.get('highGaps', 0)} |\n")

        assessments = compliance_result.get("compliance_report", {}).get("controlAssessments", [])
        if assessments:
            lines.append("### Control Assessments\n")
            lines.append("| Control ID | Title | Status | Coverage | Risk |")
            lines.append("|------------|-------|--------|----------|------|")
            for ctrl in assessments:
                lines.append(
                    f"| {ctrl.get('controlId', '-')} | {ctrl.get('controlTitle', '-')} "
                    f"| {ctrl.get('status', '-')} | {ctrl.get('coverage', '-')} "
                    f"| {ctrl.get('risk', '-')} |"
                )
            lines.append("")

        gap = compliance_result.get("compliance_report", {}).get("gapAnalysis", {})
        critical_gaps = gap.get("criticalGaps", [])
        high_gaps = gap.get("highGaps", [])
        if critical_gaps or high_gaps:
            lines.append("### Gap Analysis\n")
            for g in critical_gaps:
                lines.append(f"- 🔴 **CRITICAL** [{g.get('controlId', '')}]: {g.get('gap', '')}")
                if g.get("remediation"):
                    lines.append(f"  - Fix: {g['remediation']}")
            for g in high_gaps:
                lines.append(f"- 🟠 **HIGH** [{g.get('controlId', '')}]: {g.get('gap', '')}")
                if g.get("remediation"):
                    lines.append(f"  - Fix: {g['remediation']}")
            lines.append("")

    lines.append("---\n")
    lines.append("*This report was generated by the Ginie Enterprise Audit Engine. "
                 "LLM-based analysis may contain false positives. Critical contracts "
                 "should undergo additional human expert review.*\n")

    return "\n".join(lines)


def generate_html_report(audit_result: dict, compliance_result: dict = None) -> str:
    """Generate stakeholder-ready HTML report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Extract scores
    audit_score = 0
    audit_risk = "N/A"
    audit_rec = "N/A"
    audit_es = {}
    if audit_result and audit_result.get("success"):
        audit_es = audit_result.get("executive_summary", {})
        audit_score = audit_es.get("securityScore", 0)
        audit_risk = audit_es.get("overallRisk", "N/A")
        audit_rec = audit_es.get("recommendation", "N/A")

    compliance_score = 0
    compliance_status = "N/A"
    compliance_rec = "N/A"
    compliance_es = {}
    compliance_profile = "N/A"
    if compliance_result and compliance_result.get("success"):
        compliance_es = compliance_result.get("executive_summary", {})
        compliance_score = compliance_es.get("complianceScore", 0)
        compliance_status = compliance_es.get("overallCompliance", "N/A")
        compliance_rec = compliance_es.get("recommendation", "N/A")
        compliance_profile = compliance_result.get("profile", "generic")

    def _score_color(score):
        if score >= 85:
            return "#22c55e"
        elif score >= 70:
            return "#eab308"
        elif score >= 50:
            return "#f97316"
        return "#ef4444"

    def _severity_badge(sev):
        colors = {
            "CRITICAL": "#dc2626", "HIGH": "#ea580c", "MEDIUM": "#ca8a04",
            "LOW": "#2563eb", "INFO": "#6b7280", "OPT": "#8b5cf6",
        }
        bg = colors.get(sev, "#6b7280")
        return f'<span style="background:{bg};color:white;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600;">{escape(sev)}</span>'

    findings_html = ""
    if audit_result and audit_result.get("success"):
        findings = audit_result.get("audit_report", {}).get("findings", [])
        for f in findings:
            sev = f.get("severity", "INFO")
            findings_html += f"""
            <div style="border-left:4px solid {_score_color(100 if sev in ('INFO','OPT') else 50 if sev=='LOW' else 30)};
                        padding:12px 16px;margin:8px 0;background:#1a1a2e;border-radius:0 8px 8px 0;">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                    {_severity_badge(sev)}
                    <strong style="color:white;">{escape(f.get('title', 'Untitled'))}</strong>
                </div>
                <p style="color:#a0a0b0;margin:4px 0;">{escape(f.get('description', ''))}</p>
                {'<p style="color:#60a0d0;margin:4px 0;"><strong>Recommendation:</strong> ' + escape(f.get('recommendation', '')) + '</p>' if f.get('recommendation') else ''}
            </div>"""

    controls_html = ""
    if compliance_result and compliance_result.get("success"):
        assessments = compliance_result.get("compliance_report", {}).get("controlAssessments", [])
        for ctrl in assessments:
            status = ctrl.get("status", "N/A")
            status_color = {"PASS": "#22c55e", "FAIL": "#ef4444", "PARTIAL": "#eab308"}.get(status, "#6b7280")
            controls_html += f"""
            <tr style="border-bottom:1px solid #2a2a3e;">
                <td style="padding:8px;color:white;">{escape(ctrl.get('controlId', '-'))}</td>
                <td style="padding:8px;color:#a0a0b0;">{escape(ctrl.get('controlTitle', '-'))}</td>
                <td style="padding:8px;"><span style="color:{status_color};font-weight:600;">{escape(status)}</span></td>
                <td style="padding:8px;color:#a0a0b0;">{escape(ctrl.get('coverage', '-'))}</td>
            </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Ginie Enterprise Security Report</title>
<style>
body{{margin:0;padding:0;background:#0d0d1a;color:#e0e0f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;}}
.container{{max-width:900px;margin:0 auto;padding:32px 24px;}}
h1{{color:white;font-size:28px;margin-bottom:4px;}}
h2{{color:white;font-size:22px;margin-top:32px;border-bottom:1px solid #2a2a3e;padding-bottom:8px;}}
.subtitle{{color:#8080a0;font-size:14px;margin-bottom:24px;}}
.score-cards{{display:flex;gap:16px;margin:16px 0;flex-wrap:wrap;}}
.score-card{{flex:1;min-width:200px;background:#1a1a2e;border-radius:12px;padding:20px;text-align:center;border:1px solid #2a2a3e;}}
.score-value{{font-size:48px;font-weight:800;margin:8px 0;}}
.score-label{{color:#8080a0;font-size:14px;text-transform:uppercase;letter-spacing:1px;}}
.badge{{display:inline-block;padding:4px 12px;border-radius:6px;font-size:13px;font-weight:600;}}
table{{width:100%;border-collapse:collapse;background:#1a1a2e;border-radius:8px;overflow:hidden;margin:8px 0;}}
th{{background:#12122a;color:#8080a0;text-align:left;padding:10px;font-size:13px;text-transform:uppercase;letter-spacing:0.5px;}}
.disclaimer{{color:#606080;font-size:12px;margin-top:32px;padding-top:16px;border-top:1px solid #2a2a3e;}}
</style>
</head>
<body>
<div class="container">
<h1>Ginie Enterprise Security &amp; Compliance Report</h1>
<p class="subtitle">Generated {escape(now)} | Platform: Canton | Language: DAML</p>

<div class="score-cards">
  <div class="score-card">
    <div class="score-label">Security Score</div>
    <div class="score-value" style="color:{_score_color(audit_score)}">{audit_score}</div>
    <div class="badge" style="background:{_score_color(audit_score)}20;color:{_score_color(audit_score)}">
      {escape(audit_risk)} RISK
    </div>
  </div>
  <div class="score-card">
    <div class="score-label">Compliance Score</div>
    <div class="score-value" style="color:{_score_color(compliance_score)}">{compliance_score}</div>
    <div class="badge" style="background:{_score_color(compliance_score)}20;color:{_score_color(compliance_score)}">
      {escape(compliance_status)}
    </div>
  </div>
</div>

<div class="score-cards">
  <div class="score-card" style="text-align:left">
    <div class="score-label" style="margin-bottom:8px;">Issue Summary</div>
    <div style="color:white;">
      <span style="color:#dc2626;">●</span> Critical: {audit_es.get('criticalIssues', 0)} &nbsp;
      <span style="color:#ea580c;">●</span> High: {audit_es.get('highIssues', 0)} &nbsp;
      <span style="color:#ca8a04;">●</span> Medium: {audit_es.get('mediumIssues', 0)} &nbsp;
      <span style="color:#2563eb;">●</span> Low: {audit_es.get('lowIssues', 0)}
    </div>
  </div>
  <div class="score-card" style="text-align:left">
    <div class="score-label" style="margin-bottom:8px;">Recommendations</div>
    <div style="color:white;">
      Security: <strong>{escape(audit_rec)}</strong><br>
      Compliance ({escape(compliance_profile)}): <strong>{escape(compliance_rec)}</strong>
    </div>
  </div>
</div>

<h2>Security Findings</h2>
{findings_html if findings_html else '<p style="color:#8080a0;">No audit findings available.</p>'}

<h2>Compliance Controls ({escape(compliance_profile)})</h2>
{'<table><thead><tr><th>Control ID</th><th>Title</th><th>Status</th><th>Coverage</th></tr></thead><tbody>' + controls_html + '</tbody></table>' if controls_html else '<p style="color:#8080a0;">No compliance analysis available.</p>'}

<p class="disclaimer">
This report was generated by the Ginie Enterprise Audit Engine v2.0.
LLM-based analysis may contain false positives or miss edge cases.
Critical contracts should undergo additional human expert review.
This report does not constitute legal or regulatory approval.
</p>
</div>
</body>
</html>"""

    return html
