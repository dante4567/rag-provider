#!/usr/bin/env python3
"""
Model Pricing & Availability Checker

Run this script quarterly to:
1. Verify current pricing against known pricing
2. Check for new models available from providers
3. Generate a report of what needs updating

Usage:
    python scripts/check_model_pricing.py

Output:
    - Pricing comparison report
    - List of new models to consider
    - Suggested actions
"""

import sys
import re
from pathlib import Path
from datetime import datetime


def check_pricing_freshness():
    """Check when pricing was last updated"""
    print("=" * 80)
    print("MODEL PRICING FRESHNESS CHECK")
    print("=" * 80)
    print()

    # Read llm_service.py to find pricing update comment
    llm_service_path = Path(__file__).parent.parent / "src/services/llm_service.py"
    with open(llm_service_path) as f:
        content = f.read()

    # Look for pricing comment
    if "# Last updated:" in content:
        for line in content.split('\n'):
            if "# Last updated:" in line:
                print(f"✅ Found pricing update timestamp: {line}")
                break
    else:
        print("⚠️  No pricing update timestamp found in MODEL_PRICING")
        print("   Add comment: # Last updated: YYYY-MM-DD")

    print()


def get_model_pricing():
    """Parse MODEL_PRICING from llm_service.py"""
    llm_service_path = Path(__file__).parent.parent / "src/services/llm_service.py"
    with open(llm_service_path) as f:
        lines = f.readlines()

    # Find MODEL_PRICING block
    in_pricing = False
    pricing = {}

    for line in lines:
        if 'MODEL_PRICING = {' in line:
            in_pricing = True
            continue

        if in_pricing:
            # End of dict
            if line.strip() == '}':
                break

            # Parse line like: "groq/llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
            match = re.search(r'"([^"]+)":\s*{\s*"input":\s*([\d.]+),\s*"output":\s*([\d.]+)', line)
            if match:
                model_id = match.group(1)
                input_price = float(match.group(2))
                output_price = float(match.group(3))
                pricing[model_id] = {"input": input_price, "output": output_price}

    return pricing


def list_current_models():
    """List all models we currently use"""
    print("=" * 80)
    print("CURRENT MODEL INVENTORY")
    print("=" * 80)
    print()

    MODEL_PRICING = get_model_pricing()

    providers = {}
    for model_id, pricing in MODEL_PRICING.items():
        provider = model_id.split('/')[0]
        if provider not in providers:
            providers[provider] = []
        providers[provider].append({
            'model': model_id,
            'input': pricing['input'],
            'output': pricing['output']
        })

    for provider, models in sorted(providers.items()):
        print(f"**{provider.upper()}** ({len(models)} models)")
        for m in models:
            print(f"  - {m['model']}")
            print(f"    Input: ${m['input']}/1M tokens, Output: ${m['output']}/1M tokens")
        print()

    return providers


def check_hardcoded_models():
    """Find all hardcoded model references"""
    print("=" * 80)
    print("HARDCODED MODEL USAGE")
    print("=" * 80)
    print()

    enrichment_path = Path(__file__).parent.parent / "src/services/enrichment_service.py"
    with open(enrichment_path) as f:
        lines = f.readlines()

    hardcoded = []
    for i, line in enumerate(lines, 1):
        if 'model_id="' in line:
            # Extract model ID
            import re
            match = re.search(r'model_id="([^"]+)"', line)
            if match:
                model_id = match.group(1)
                hardcoded.append((i, model_id, line.strip()))

    if hardcoded:
        print(f"Found {len(hardcoded)} hardcoded model references:\n")
        for line_num, model_id, line in hardcoded:
            print(f"  Line {line_num}: {model_id}")
            print(f"    {line[:80]}...")
            print()
    else:
        print("⚠️  No hardcoded models found (unexpected)")

    return hardcoded


def generate_pricing_check_urls():
    """Generate URLs to check current pricing"""
    print("=" * 80)
    print("PRICING CHECK URLS")
    print("=" * 80)
    print()
    print("Visit these URLs to verify current pricing:\n")

    urls = {
        "Groq": "https://groq.com/pricing",
        "Anthropic": "https://www.anthropic.com/pricing",
        "OpenAI": "https://openai.com/pricing",
        "Google": "https://ai.google.dev/pricing"
    }

    for provider, url in urls.items():
        print(f"  {provider:12} {url}")

    print()
    print("Manual Steps:")
    print("  1. Visit each URL above")
    print("  2. Compare prices with MODEL_PRICING in src/services/llm_service.py")
    print("  3. Update pricing if changed")
    print("  4. Update timestamp comment: # Last updated: YYYY-MM-DD")
    print("  5. Run: pytest tests/unit/test_model_choices.py")
    print("  6. Commit: git commit -m 'Update pricing - [Provider] changed'")
    print()


def check_for_new_models():
    """Suggest checking for new model releases"""
    print("=" * 80)
    print("NEW MODEL AVAILABILITY CHECK")
    print("=" * 80)
    print()

    print("Check provider blogs/docs for new models:\n")

    suggestions = {
        "Groq": [
            "https://console.groq.com/docs/models",
            "Look for: Llama 3.2, Llama 3.3, newer Mixtral variants"
        ],
        "Anthropic": [
            "https://docs.anthropic.com/en/docs/about-claude/models",
            "Look for: Newer Claude 3.5 versions, Claude 4"
        ],
        "OpenAI": [
            "https://platform.openai.com/docs/models",
            "Look for: GPT-4.5, GPT-5, cheaper GPT-4o variants"
        ],
        "Google": [
            "https://ai.google.dev/gemini-api/docs/models/gemini",
            "Look for: Gemini 2.5, Gemini Ultra"
        ]
    }

    for provider, (url, suggestion) in suggestions.items():
        print(f"  {provider:12}")
        print(f"    Docs: {url}")
        print(f"    {suggestion}")
        print()

    print("If new models found:")
    print("  1. Add to MODEL_PRICING in src/services/llm_service.py")
    print("  2. Update MODEL_DECISION_MATRIX.md with comparison")
    print("  3. Consider if it should replace current hardcoded choice")
    print()


def generate_monthly_checklist():
    """Generate monthly maintenance checklist"""
    print("=" * 80)
    print("MONTHLY MAINTENANCE CHECKLIST")
    print("=" * 80)
    print()
    print("Philosophy: Quality first - willing to pay 2-3x more for quality gains")
    print()

    checklist = [
        ("Verify Pricing", [
            "Visit all 4 provider pricing pages",
            "Compare against MODEL_PRICING dict",
            "Update if changed",
            "Update timestamp comment"
        ]),
        ("Check New Models", [
            "Check provider docs for new models",
            "Add new models to MODEL_PRICING",
            "Evaluate if better than current choices"
        ]),
        ("Run Tests", [
            "pytest tests/unit/test_model_choices.py -v",
            "Verify all 14 tests still pass",
            "Update cost thresholds if pricing changed"
        ]),
        ("Review Actual Usage", [
            "curl http://localhost:8001/cost/stats",
            "Verify Groq is majority of calls",
            "Check for unexpected cost patterns"
        ]),
        ("Update Documentation", [
            "Update MODEL_DECISION_MATRIX.md if choices changed",
            "Update README.md cost estimates",
            "Note changes in CHANGELOG.md"
        ]),
        ("Commit Changes", [
            "git add src/services/llm_service.py MODEL_DECISION_MATRIX.md",
            "git commit -m 'Quarterly model review - [summary]'",
            "git push"
        ])
    ]

    for i, (task, steps) in enumerate(checklist, 1):
        print(f"{i}. {task}")
        for step in steps:
            print(f"   [ ] {step}")
        print()

    print(f"Next review due: {get_next_month()}")
    print()


def get_next_month():
    """Calculate next monthly review date (1st of next month)"""
    from datetime import datetime
    from calendar import monthrange

    today = datetime.now()

    # Next month's 1st
    if today.month == 12:
        next_review = datetime(today.year + 1, 1, 1)
    else:
        next_review = datetime(today.year, today.month + 1, 1)

    return next_review.strftime("%Y-%m-%d")


def main():
    """Run all checks"""
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "MODEL PRICING & AVAILABILITY CHECKER" + " " * 22 + "║")
    print("║" + f" Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" + " " * 54 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    check_pricing_freshness()
    providers = list_current_models()
    hardcoded = check_hardcoded_models()
    generate_pricing_check_urls()
    check_for_new_models()
    generate_monthly_checklist()

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  - {sum(len(m) for m in providers.values())} models in MODEL_PRICING")
    print(f"  - {len(hardcoded)} hardcoded model selections")
    print(f"  - Next review: {get_next_month()}")
    print()
    print("✅ Monthly checklist generated above")
    print("✅ Philosophy: Quality first - willing to pay more for improvements")
    print()


if __name__ == "__main__":
    main()
