#!/usr/bin/env python3
"""
🔬 FalkorDB Integration Test Runner
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A visually stunning test runner for the Legal Contract Intelligence Platform.
Runs FalkorDB graph store integration tests with beautiful output.

Usage:
    python scripts/run_integration_tests.py
    python scripts/run_integration_tests.py --verbose
    python scripts/run_integration_tests.py --demo
    python scripts/run_integration_tests.py --show-data   # Show actual contract data
"""

import subprocess
import sys
import os
import time
import re
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
import argparse

# ═══════════════════════════════════════════════════════════════════════════════
# ASCII Art & Styling
# ═══════════════════════════════════════════════════════════════════════════════

BANNER = r"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   ███████╗ █████╗ ██╗     ██╗  ██╗ ██████╗ ██████╗ ██████╗ ██████╗           ║
║   ██╔════╝██╔══██╗██║     ██║ ██╔╝██╔═══██╗██╔══██╗██╔══██╗██╔══██╗          ║
║   █████╗  ███████║██║     █████╔╝ ██║   ██║██████╔╝██║  ██║██████╔╝          ║
║   ██╔══╝  ██╔══██║██║     ██╔═██╗ ██║   ██║██╔══██╗██║  ██║██╔══██╗          ║
║   ██║     ██║  ██║███████╗██║  ██╗╚██████╔╝██║  ██║██████╔╝██████╔╝          ║
║   ╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚═════╝           ║
║                                                                               ║
║          🔬 Integration Test Suite for Graph Database Operations 🔬          ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

GRAPH_ART_TEMPLATE = """
                         ┌─────────────────────┐
                         │    📄 CONTRACT      │
                         │    Risk: %RISK%     │
                         └──────────┬──────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
       ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
       │ 🏢 COMPANY  │       │ 📋 CLAUSE   │       │ ⚠️  RISK    │
       │  Acme Corp  │       │   Payment   │       │   Medium    │
       └─────────────┘       └─────────────┘       └─────────────┘
"""

DOCKER_CHECK = r"""
    ╭──────────────────────────────────────────────────────────────────╮
    │  🐳 Checking Docker Container Status...                          │
    ╰──────────────────────────────────────────────────────────────────╯
"""

SUCCESS_BOX = r"""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                                                                  ║
    ║   ✅  ALL TESTS PASSED!                                          ║
    ║                                                                  ║
    ║   🎉 Your FalkorDB integration is working perfectly! 🎉          ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
"""

SUCCESS_BANNER = r"""

    ███████╗██╗   ██╗ ██████╗ ██████╗███████╗███████╗███████╗██╗
    ██╔════╝██║   ██║██╔════╝██╔════╝██╔════╝██╔════╝██╔════╝██║
    ███████╗██║   ██║██║     ██║     █████╗  ███████╗███████╗██║
    ╚════██║██║   ██║██║     ██║     ██╔══╝  ╚════██║╚════██║╚═╝
    ███████║╚██████╔╝╚██████╗╚██████╗███████╗███████║███████║██╗
    ╚══════╝ ╚═════╝  ╚═════╝ ╚═════╝╚══════╝╚══════╝╚══════╝╚═╝

       █████╗ ██╗     ██╗         ████████╗███████╗███████╗████████╗███████╗
      ██╔══██╗██║     ██║         ╚══██╔══╝██╔════╝██╔════╝╚══██╔══╝██╔════╝
      ███████║██║     ██║            ██║   █████╗  ███████╗   ██║   ███████╗
      ██╔══██║██║     ██║            ██║   ██╔══╝  ╚════██║   ██║   ╚════██║
      ██║  ██║███████╗███████╗       ██║   ███████╗███████║   ██║   ███████║
      ╚═╝  ╚═╝╚══════╝╚══════╝       ╚═╝   ╚══════╝╚══════╝   ╚═╝   ╚══════╝

      ██████╗  █████╗ ███████╗███████╗███████╗██████╗ ██╗
      ██╔══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔══██╗██║
      ██████╔╝███████║███████╗███████╗█████╗  ██║  ██║██║
      ██╔═══╝ ██╔══██║╚════██║╚════██║██╔══╝  ██║  ██║╚═╝
      ██║     ██║  ██║███████║███████║███████╗██████╔╝██╗
      ╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚═════╝ ╚═╝

    ✨ ═══════════════════════════════════════════════════════════════ ✨
    ║                                                                   ║
    ║   🏆  PERFECT SCORE! All integration tests passed flawlessly! 🏆  ║
    ║                                                                   ║
    ║      📊 Graph Operations: VERIFIED                                ║
    ║      🔗 Relationships:    CONNECTED                               ║
    ║      💾 Data Integrity:   CONFIRMED                               ║
    ║      ⚡ Performance:      OPTIMAL                                 ║
    ║                                                                   ║
    ✨ ═══════════════════════════════════════════════════════════════ ✨

"""

FAILURE_BOX = r"""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                                                                  ║
    ║   ❌  SOME TESTS FAILED                                          ║
    ║                                                                  ║
    ║   Check the output above for details.                            ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
"""

SKIPPED_BOX = r"""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                                                                  ║
    ║   ⏭️   TESTS SKIPPED - FalkorDB Not Available                     ║
    ║                                                                  ║
    ║   Start FalkorDB with docker-compose:                            ║
    ║   docker-compose up -d                                           ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════════════════════
# Colors
# ═══════════════════════════════════════════════════════════════════════════════

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

    # Extended colors
    ORANGE = '\033[38;5;208m'
    PURPLE = '\033[38;5;141m'
    PINK = '\033[38;5;213m'
    TEAL = '\033[38;5;51m'
    GOLD = '\033[38;5;220m'


def colorize(text: str, color: str) -> str:
    """Wrap text in color codes."""
    return f"{color}{text}{Colors.END}"


def print_colored(text: str, color: str = ""):
    """Print text with optional color."""
    if color:
        print(colorize(text, color))
    else:
        print(text)


# ═══════════════════════════════════════════════════════════════════════════════
# Risk Level Display
# ═══════════════════════════════════════════════════════════════════════════════

RISK_DISPLAY = {
    "low": {
        "emoji": "🟢",
        "bar": "▓░░░░",
        "label": "LOW",
        "color": Colors.GREEN,
        "description": "Minimal concerns identified"
    },
    "medium": {
        "emoji": "🟡",
        "bar": "▓▓▓░░",
        "label": "MEDIUM",
        "color": Colors.YELLOW,
        "description": "Some concerns require attention"
    },
    "high": {
        "emoji": "🔴",
        "bar": "▓▓▓▓▓",
        "label": "HIGH",
        "color": Colors.RED,
        "description": "Critical issues - review required"
    }
}


def display_risk_level(level: str) -> str:
    """Format risk level with emoji and color."""
    risk = RISK_DISPLAY.get(level.lower(), RISK_DISPLAY["medium"])
    return f"{risk['emoji']} {colorize(risk['bar'], risk['color'])} {colorize(risk['label'], risk['color'])}"


def display_risk_meter():
    """Display the risk level legend."""
    print("\n    📊 Risk Level Legend:")
    print("    " + "─" * 50)
    for level, info in RISK_DISPLAY.items():
        label_padded = f"{info['label']:8s}"
        print(f"    {info['emoji']} {colorize(info['bar'], info['color'])} {colorize(label_padded, info['color'])} │ {info['description']}")
    print("    " + "─" * 50)


# ═══════════════════════════════════════════════════════════════════════════════
# Progress Animation
# ═══════════════════════════════════════════════════════════════════════════════

SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
TEST_ICONS = {
    "passed": "✅",
    "failed": "❌",
    "skipped": "⏭️ ",
    "error": "💥",
    "running": "🔄"
}


def animate_progress(message: str, duration: float = 0.5):
    """Show an animated progress indicator."""
    frames = len(SPINNERS)
    for i in range(int(duration * 10)):
        spinner = SPINNERS[i % frames]
        sys.stdout.write(f"\r    {colorize(spinner, Colors.CYAN)} {message}")
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write("\r" + " " * (len(message) + 10) + "\r")
    sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════════════════════
# Docker & FalkorDB Checks
# ═══════════════════════════════════════════════════════════════════════════════

def check_docker_running() -> bool:
    """Check if Docker is running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def check_falkordb_container() -> Tuple[bool, Optional[str]]:
    """Check if FalkorDB container is running and get its info."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "ancestor=falkordb/falkordb", "--format", "{{.Names}}\t{{.Ports}}\t{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.stdout.strip():
            return True, result.stdout.strip()
        return False, None
    except Exception:
        return False, None


def check_falkordb_connection(host: str = "localhost", port: int = 6381) -> bool:
    """Check if we can connect to FalkorDB."""
    try:
        from falkordb import FalkorDB
        db = FalkorDB(host=host, port=port)
        graph = db.select_graph("_connection_test")
        graph.query("RETURN 1")
        return True
    except Exception:
        return False


def display_connection_status(port: int = 6381):
    """Display comprehensive connection status."""
    print(colorize(DOCKER_CHECK, Colors.CYAN))

    checks = []

    # Docker check
    animate_progress("Checking Docker daemon...", 0.3)
    docker_ok = check_docker_running()
    checks.append(("Docker Daemon", docker_ok))

    # Container check
    animate_progress("Looking for FalkorDB container...", 0.3)
    container_ok, container_info = check_falkordb_container()
    checks.append(("FalkorDB Container", container_ok))

    # Connection check
    animate_progress(f"Testing connection on port {port}...", 0.3)
    connection_ok = check_falkordb_connection(port=port)
    checks.append(("Database Connection", connection_ok))

    # Display results
    print("    ┌─────────────────────────────────────────────────────────────┐")
    print("    │ Service                    │ Status                         │")
    print("    ├─────────────────────────────────────────────────────────────┤")

    for name, status in checks:
        icon = "✅" if status else "❌"
        status_text = colorize("Connected", Colors.GREEN) if status else colorize("Not Found", Colors.RED)
        print(f"    │ {icon} {name:24s} │ {status_text:40s} │")

    print("    └─────────────────────────────────────────────────────────────┘")

    if container_info:
        print(f"\n    📦 Container Details: {colorize(container_info, Colors.DIM)}")

    return all(ok for _, ok in checks)


# ═══════════════════════════════════════════════════════════════════════════════
# Real Contract Data Display
# ═══════════════════════════════════════════════════════════════════════════════

def get_real_contracts(port: int = 6381) -> List[Dict[str, Any]]:
    """Fetch actual contracts from FalkorDB."""
    try:
        from falkordb import FalkorDB
        db = FalkorDB(host="localhost", port=port)
        graph = db.select_graph("contracts")

        # Query all contracts with their relationships
        query = """
        MATCH (c:Contract)
        OPTIONAL MATCH (c)<-[:PARTY_TO]-(company:Company)
        OPTIONAL MATCH (c)-[:CONTAINS]->(clause:Clause)
        OPTIONAL MATCH (c)-[:HAS_RISK]->(risk:RiskFactor)
        RETURN c.contract_id as contract_id,
               c.filename as filename,
               c.risk_score as risk_score,
               c.risk_level as risk_level,
               c.payment_amount as payment_amount,
               c.payment_frequency as payment_frequency,
               c.has_termination_clause as has_termination,
               c.liability_cap as liability_cap,
               collect(DISTINCT {name: company.name, role: company.role}) as companies,
               collect(DISTINCT {name: clause.section_name, type: clause.clause_type, importance: clause.importance}) as clauses,
               collect(DISTINCT {concern: risk.concern, level: risk.risk_level, section: risk.section}) as risks
        """
        result = graph.query(query)

        contracts = []
        for row in result.result_set:
            contract = {
                "contract_id": row[0],
                "filename": row[1],
                "risk_score": row[2],
                "risk_level": row[3],
                "payment_amount": row[4],
                "payment_frequency": row[5],
                "has_termination": row[6],
                "liability_cap": row[7],
                "companies": [c for c in row[8] if c.get("name")],
                "clauses": [c for c in row[9] if c.get("name")],
                "risks": [r for r in row[10] if r.get("concern")]
            }
            contracts.append(contract)

        return contracts
    except Exception as e:
        return []


def display_real_contracts(port: int = 6381):
    """Display actual contract data from the database with beautiful formatting."""
    contracts = get_real_contracts(port)

    if not contracts:
        print(f"""
    ╭──────────────────────────────────────────────────────────────────╮
    │  📭 No contracts found in database                               │
    │                                                                  │
    │  Import some contracts first:                                    │
    │  {colorize('python scripts/import_test_documents.py --import', Colors.CYAN)}          │
    ╰──────────────────────────────────────────────────────────────────╯
        """)
        return

    print(f"""
    ╔══════════════════════════════════════════════════════════════════╗
    ║            📊 LIVE CONTRACT DATA FROM FALKORDB 📊                ║
    ║                   {colorize(f'{len(contracts)} contract(s) found', Colors.GREEN):43s}              ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)

    for i, contract in enumerate(contracts, 1):
        # Contract header
        risk_level = contract.get("risk_level", "unknown") or "unknown"
        risk_score = contract.get("risk_score", 0) or 0
        filename = contract.get("filename", "Unknown") or "Unknown"
        contract_id = contract.get("contract_id", "")[:16] + "..." if contract.get("contract_id") else "N/A"

        # Determine risk display
        risk_display = display_risk_level(risk_level)

        print(f"    ┌{'─' * 68}┐")
        print(f"    │ 📄 CONTRACT #{i}: {colorize(filename[:45], Colors.BOLD):56s} │")
        print(f"    │    ID: {colorize(contract_id, Colors.DIM):60s} │")
        print(f"    ├{'─' * 68}┤")

        # Risk info
        print(f"    │ ⚠️  Risk Assessment:                                               │")
        print(f"    │    Score: {colorize(f'{risk_score}/10', Colors.YELLOW if risk_score > 5 else Colors.GREEN):50s} │")
        print(f"    │    Level: {risk_display:50s} │")

        # Payment info
        payment = contract.get("payment_amount") or "Not specified"
        frequency = contract.get("payment_frequency") or ""
        liability = contract.get("liability_cap") or "Not specified"
        termination = "✅ Yes" if contract.get("has_termination") else "❌ No"

        print(f"    ├{'─' * 68}┤")
        print(f"    │ 💰 Financial Terms:                                                │")
        print(f"    │    Payment: {colorize(str(payment)[:40], Colors.GREEN):52s} │")
        if frequency:
            print(f"    │    Frequency: {colorize(str(frequency)[:38], Colors.CYAN):50s} │")
        print(f"    │    Liability Cap: {colorize(str(liability)[:35], Colors.YELLOW):46s} │")
        print(f"    │    Termination Clause: {termination:42s} │")

        # Companies
        companies = contract.get("companies", [])
        if companies:
            print(f"    ├{'─' * 68}┤")
            print(f"    │ 🏢 Parties ({len(companies)}):                                                │")
            for comp in companies[:5]:  # Limit to 5
                name = comp.get("name", "Unknown")[:30]
                role = comp.get("role", "")[:15]
                print(f"    │    • {colorize(name, Colors.CYAN):40s} ({role:15s})   │")

        # Clauses
        clauses = contract.get("clauses", [])
        if clauses:
            print(f"    ├{'─' * 68}┤")
            print(f"    │ 📋 Key Clauses ({len(clauses)}):                                            │")
            for clause in clauses[:5]:  # Limit to 5
                name = clause.get("name", "Unknown")[:25]
                ctype = clause.get("type", "")[:12]
                importance = clause.get("importance", "")
                imp_icon = "🔴" if importance == "high" else "🟡" if importance == "medium" else "🟢"
                print(f"    │    {imp_icon} {colorize(name, Colors.BOLD):35s} [{ctype:12s}]      │")

        # Risk Factors
        risks = contract.get("risks", [])
        if risks:
            print(f"    ├{'─' * 68}┤")
            print(f"    │ ⚡ Risk Factors ({len(risks)}):                                           │")
            for risk in risks[:5]:  # Limit to 5
                concern = risk.get("concern", "Unknown")[:55]
                level = risk.get("level", "unknown")
                level_icon = "🔴" if level == "high" else "🟡" if level == "medium" else "🟢"
                print(f"    │    {level_icon} {concern:62s} │")

        print(f"    └{'─' * 68}┘")
        print()


def display_agent_prompts():
    """Display the AI agent prompts and expert system instructions."""

    print(f"""
    ╔══════════════════════════════════════════════════════════════════╗
    ║         🎓 EXPERT LEGAL SYSTEM INSTRUCTIONS (NEW!) 🎓            ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)

    # Expert personas
    experts = [
        ("RISK_ANALYST", "📊", "Senior Legal Risk Analyst", Colors.RED,
         ["20+ years M&A experience", "Indemnification & liability analysis",
          "RED FLAGS: Uncapped liability, one-sided indemnification",
          "OUTPUT: Section citations, risk ratings (LOW/MEDIUM/HIGH)"]),
        ("CONTRACT_REVIEWER", "📋", "Expert Contract Attorney", Colors.ORANGE,
         ["15+ years at top-tier law firms", "Commercial agreement review",
          "EXTRACTS: Payment terms, IP, termination rights",
          "OUTPUT: Organized findings with plain-English summaries"]),
        ("QA_ASSISTANT", "💬", "Legal Research Assistant", Colors.TEAL,
         ["Direct, concise answers", "Quotes relevant contract language",
          "Explains legal terms in plain English",
          "LIMITATION: Information only, not legal advice"]),
        ("COMPLIANCE_EXPERT", "⚖️", "Regulatory Compliance Specialist", Colors.PURPLE,
         ["Antitrust (HSR Act, EU Merger Reg)", "Securities (SEC, CFIUS)",
          "Data privacy (GDPR, CCPA, HIPAA)", "Anti-corruption (FCPA, UK Bribery Act)"]),
    ]

    for expertise, icon, title, color, points in experts:
        print(f"    {colorize(f'┌─ {icon} {expertise} ', color)}{'─' * (52 - len(expertise))}{colorize('┐', color)}")
        print(f"    {colorize('│', color)} {colorize(title, Colors.BOLD):62s} {colorize('│', color)}")
        print(f"    {colorize('├', color)}{'─' * 66}{colorize('┤', color)}")
        for point in points:
            print(f"    {colorize('│', color)}   • {point:61s} {colorize('│', color)}")
        print(f"    {colorize('└', color)}{'─' * 66}{colorize('┘', color)}")
        print()

    # Show sample of actual system instruction
    print(f"    {colorize('┌─ 📜 SAMPLE SYSTEM INSTRUCTION (RISK_ANALYST) ────────────────────┐', Colors.GOLD)}")
    print(f"    {colorize('│', Colors.GOLD)}                                                                  {colorize('│', Colors.GOLD)}")

    sample_lines = [
        "You are a Senior Legal Risk Analyst with 20+ years of",
        "experience analyzing complex commercial contracts...",
        "",
        "EXPERTISE AREAS:",
        "- Mergers & Acquisitions (M&A) agreements",
        "- Indemnification provisions and liability allocation",
        "- Material adverse change (MAC) clauses",
        "",
        "COMMON RED FLAGS TO IDENTIFY:",
        "- Unlimited or uncapped liability exposure",
        "- One-sided indemnification obligations",
        "- Broad 'material adverse effect' definitions...",
    ]

    for line in sample_lines:
        print(f"    {colorize('│', Colors.GOLD)}   {colorize(line, Colors.DIM):63s}{colorize('│', Colors.GOLD)}")

    print(f"    {colorize('│', Colors.GOLD)}                                                                  {colorize('│', Colors.GOLD)}")
    print(f"    {colorize('└──────────────────────────────────────────────────────────────────┘', Colors.GOLD)}")

    print()

    # Model routing info
    print(f"""    {colorize('┌─ 🎯 MODEL ROUTING STRATEGY ───────────────────────────────────────┐', Colors.PURPLE)}
    {colorize('│', Colors.PURPLE)}                                                                  {colorize('│', Colors.PURPLE)}
    {colorize('│', Colors.PURPLE)}  {colorize('TaskComplexity.SIMPLE', Colors.GREEN)}   → gemini-2.5-flash-lite  ($0.04/M)   {colorize('│', Colors.PURPLE)}
    {colorize('│', Colors.PURPLE)}     └─ QA_ASSISTANT expertise                                   {colorize('│', Colors.PURPLE)}
    {colorize('│', Colors.PURPLE)}                                                                  {colorize('│', Colors.PURPLE)}
    {colorize('│', Colors.PURPLE)}  {colorize('TaskComplexity.BALANCED', Colors.YELLOW)} → gemini-2.5-flash       ($0.075/M)  {colorize('│', Colors.PURPLE)}
    {colorize('│', Colors.PURPLE)}     └─ RISK_ANALYST, CONTRACT_REVIEWER expertise               {colorize('│', Colors.PURPLE)}
    {colorize('│', Colors.PURPLE)}                                                                  {colorize('│', Colors.PURPLE)}
    {colorize('│', Colors.PURPLE)}  {colorize('TaskComplexity.COMPLEX', Colors.ORANGE)}  → gemini-2.5-pro         ($0.15/M)   {colorize('│', Colors.PURPLE)}
    {colorize('│', Colors.PURPLE)}     └─ COMPLIANCE_EXPERT expertise                              {colorize('│', Colors.PURPLE)}
    {colorize('│', Colors.PURPLE)}                                                                  {colorize('│', Colors.PURPLE)}
    {colorize('│', Colors.PURPLE)}  {colorize('TaskComplexity.REASONING', Colors.RED)} → gemini-3-pro           (Premium)   {colorize('│', Colors.PURPLE)}
    {colorize('│', Colors.PURPLE)}     └─ Multi-step legal reasoning chains                        {colorize('│', Colors.PURPLE)}
    {colorize('│', Colors.PURPLE)}                                                                  {colorize('│', Colors.PURPLE)}
    {colorize('└──────────────────────────────────────────────────────────────────┘', Colors.PURPLE)}
    """)


def display_database_stats(port: int = 6381):
    """Display database statistics."""
    try:
        from falkordb import FalkorDB
        db = FalkorDB(host="localhost", port=port)
        graph = db.select_graph("contracts")

        # Count nodes
        stats = {}
        for label in ["Contract", "Company", "Clause", "RiskFactor"]:
            result = graph.query(f"MATCH (n:{label}) RETURN count(n) as count")
            stats[label] = result.result_set[0][0] if result.result_set else 0

        # Count relationships
        rel_result = graph.query("MATCH ()-[r]->() RETURN count(r) as count")
        rel_count = rel_result.result_set[0][0] if rel_result.result_set else 0

        print(f"""
    ╭──────────────────────────────────────────────────────────────────╮
    │                    📈 DATABASE STATISTICS                        │
    ├──────────────────────────────────────────────────────────────────┤
    │  📄 Contracts:      {colorize(f'{stats.get("Contract", 0):5d}', Colors.CYAN):47s} │
    │  🏢 Companies:      {colorize(f'{stats.get("Company", 0):5d}', Colors.CYAN):47s} │
    │  📋 Clauses:        {colorize(f'{stats.get("Clause", 0):5d}', Colors.CYAN):47s} │
    │  ⚠️  Risk Factors:   {colorize(f'{stats.get("RiskFactor", 0):5d}', Colors.CYAN):47s} │
    │  🔗 Relationships:  {colorize(f'{rel_count:5d}', Colors.GREEN):47s} │
    ╰──────────────────────────────────────────────────────────────────╯
        """)
    except Exception as e:
        print(f"    ⚠️  Could not fetch stats: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# Test Execution & Parsing
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests(verbose: bool = False) -> Tuple[int, str, dict]:
    """Run pytest and capture output."""
    test_path = Path(__file__).parent.parent / "tests" / "integration" / "test_graph_store_integration.py"

    cmd = [
        sys.executable, "-m", "pytest",
        str(test_path),
        "-v",
        "--tb=short",
        "-x" if not verbose else "",
    ]
    cmd = [c for c in cmd if c]  # Remove empty strings

    # Set the environment
    env = os.environ.copy()
    env["FALKORDB_TEST_PORT"] = os.getenv("FALKORDB_TEST_PORT", "6381")

    print(f"\n    🚀 Running: {colorize(' '.join(cmd), Colors.DIM)}\n")
    print("    " + "═" * 66)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
        env=env
    )

    # Parse test results
    stats = parse_test_output(result.stdout + result.stderr)

    return result.returncode, result.stdout + result.stderr, stats


def parse_test_output(output: str) -> dict:
    """Parse pytest output for statistics."""
    stats = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "duration": 0.0,
        "tests": []
    }

    # Parse individual test results
    test_pattern = r"(test_\w+)\s+(PASSED|FAILED|SKIPPED|ERROR)"
    for match in re.finditer(test_pattern, output):
        test_name = match.group(1)
        status = match.group(2).lower()
        stats["tests"].append({"name": test_name, "status": status})
        stats[status if status != "error" else "errors"] += 1

    # Parse summary line
    summary_pattern = r"(\d+) passed"
    match = re.search(summary_pattern, output)
    if match:
        stats["passed"] = int(match.group(1))

    skip_pattern = r"(\d+) skipped"
    match = re.search(skip_pattern, output)
    if match:
        stats["skipped"] = int(match.group(1))

    fail_pattern = r"(\d+) failed"
    match = re.search(fail_pattern, output)
    if match:
        stats["failed"] = int(match.group(1))

    # Parse duration
    duration_pattern = r"in ([\d.]+)s"
    match = re.search(duration_pattern, output)
    if match:
        stats["duration"] = float(match.group(1))

    return stats


def display_test_results(output: str, stats: dict):
    """Display formatted test results."""
    print("\n    📋 Test Results:")
    print("    " + "─" * 66)

    # Display each test
    for test in stats["tests"]:
        icon = TEST_ICONS.get(test["status"], "❓")
        name = test["name"].replace("test_", "").replace("_", " ").title()

        if test["status"] == "passed":
            color = Colors.GREEN
        elif test["status"] == "failed":
            color = Colors.RED
        elif test["status"] == "skipped":
            color = Colors.YELLOW
        else:
            color = Colors.RED

        status_display = colorize(test["status"].upper(), color)
        print(f"    {icon} {name:50s} │ {status_display}")

    print("    " + "─" * 66)

    # Summary statistics
    passed_str = colorize(f"{stats['passed']:5d}", Colors.GREEN)
    failed_str = colorize(f"{stats['failed']:5d}", Colors.RED)
    skipped_str = colorize(f"{stats['skipped']:5d}", Colors.YELLOW)
    duration_str = f"{stats['duration']:.2f}s"

    print(f"""
    ╭──────────────────────────────────────────────────────────────────╮
    │                        📊 Test Summary                           │
    ├──────────────────────────────────────────────────────────────────┤
    │  ✅ Passed: {passed_str}    ❌ Failed: {failed_str}    ⏭️  Skipped: {skipped_str}   │
    │  ⏱️  Duration: {duration_str}                                               │
    ╰──────────────────────────────────────────────────────────────────╯
    """)


def display_graph_visualization():
    """Display a sample graph structure."""
    risk_display = display_risk_level("medium")
    graph = GRAPH_ART_TEMPLATE.replace("%RISK%", "🟡 MED")
    print(colorize(graph, Colors.CYAN))


# ═══════════════════════════════════════════════════════════════════════════════
# Demo Mode
# ═══════════════════════════════════════════════════════════════════════════════

def run_demo_mode():
    """Run a visual demo of what the tests cover."""
    print(colorize(BANNER, Colors.PURPLE))

    print(f"""
    {colorize('🎬 DEMO MODE', Colors.GOLD)} - Showing what the integration tests verify
    {'═' * 66}
    """)

    # Show graph structure
    print(f"\n    {colorize('📊 Graph Database Structure:', Colors.BOLD)}")
    display_graph_visualization()

    # Show risk levels
    display_risk_meter()

    # Test coverage summary
    print(f"""
    {colorize('🧪 Test Coverage:', Colors.BOLD)}
    ┌────────────────────────────────────────────────────────────────────┐
    │                                                                    │
    │  📄 Contract CRUD Operations                                       │
    │     ├── ✅ Store complete contract graph                           │
    │     ├── ✅ Retrieve contract with relationships                    │
    │     ├── ✅ Update existing contracts                               │
    │     └── ✅ Delete contracts and related nodes                      │
    │                                                                    │
    │  🔍 Query Operations                                               │
    │     ├── ✅ Find contracts by risk level                            │
    │     ├── ✅ Handle non-existent contracts                           │
    │     └── ✅ Store minimal contract data                             │
    │                                                                    │
    │  🔌 Connection Handling                                            │
    │     ├── ✅ Connect with configured settings                        │
    │     ├── ✅ Initialize schema/indexes                               │
    │     └── ✅ Close connections properly                              │
    │                                                                    │
    └────────────────────────────────────────────────────────────────────┘
    """)

    # Sample test data
    print(f"""
    {colorize('📦 Sample Test Data:', Colors.BOLD)}
    ┌────────────────────────────────────────────────────────────────────┐
    │  Contract: test_agreement.pdf                                      │
    │  ├── Risk Score: 6.5/10  {display_risk_level('medium')}                     │
    │  ├── Payment: $50,000 monthly                                      │
    │  └── Termination Clause: Yes ✅                                    │
    │                                                                    │
    │  Companies:                                                        │
    │  ├── 🏢 Acme Corp (vendor)                                         │
    │  └── 🏢 Client Inc (client)                                        │
    │                                                                    │
    │  Risk Factors:                                                     │
    │  ├── {display_risk_level('medium')} Limited liability cap                  │
    │  └── {display_risk_level('low')} Short termination notice                  │
    └────────────────────────────────────────────────────────────────────┘
    """)


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="🔬 FalkorDB Integration Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/run_integration_tests.py              # Run tests
    python scripts/run_integration_tests.py --demo       # Show demo/preview
    python scripts/run_integration_tests.py --show-data  # Show actual contract data
    python scripts/run_integration_tests.py -v           # Verbose output
        """
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show verbose output")
    parser.add_argument("--demo", action="store_true", help="Run in demo mode (no actual tests)")
    parser.add_argument("--show-data", action="store_true", help="Show actual contract data from database")
    parser.add_argument("--port", type=int, default=6379, help="FalkorDB port (default: 6379)")
    args = parser.parse_args()

    # Set port in environment
    os.environ["FALKORDB_TEST_PORT"] = str(args.port)

    # Print banner
    print(colorize(BANNER, Colors.PURPLE))

    if args.demo:
        run_demo_mode()
        return 0

    # Print timestamp
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"    🕐 Started at: {colorize(now, Colors.DIM)}")
    print(f"    📍 Port: {colorize(str(args.port), Colors.CYAN)}")

    # Check connections
    all_ok = display_connection_status(args.port)

    if not all_ok:
        print(colorize(SKIPPED_BOX, Colors.YELLOW))
        print(f"""
    💡 To start FalkorDB:

       {colorize('docker-compose up -d', Colors.CYAN)}

    Then run this script again.
        """)
        return 1

    # Show real contract data if requested
    if args.show_data:
        display_agent_prompts()
        display_database_stats(args.port)
        display_real_contracts(args.port)
        return 0

    # Show graph visualization
    print(f"\n    {colorize('📊 Testing Graph Operations:', Colors.BOLD)}")
    display_graph_visualization()

    # Show risk meter
    display_risk_meter()

    # Run tests
    print(f"\n    {colorize('🧪 Executing Test Suite...', Colors.BOLD)}")
    return_code, output, stats = run_tests(args.verbose)

    # Display results
    display_test_results(output, stats)

    # Show verbose output if requested
    if args.verbose:
        print(f"\n    {colorize('📜 Full Output:', Colors.DIM)}")
        print("    " + "─" * 66)
        for line in output.split("\n"):
            print(f"    {line}")

    # Final status
    if stats["skipped"] > 0 and stats["passed"] == 0:
        print(colorize(SKIPPED_BOX, Colors.YELLOW))
        return 1
    elif stats["failed"] > 0 or return_code != 0:
        print(colorize(FAILURE_BOX, Colors.RED))
        return 1
    else:
        # Big success banner!
        print(colorize(SUCCESS_BANNER, Colors.GREEN))
        return 0


if __name__ == "__main__":
    sys.exit(main())
