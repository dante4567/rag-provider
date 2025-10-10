#!/usr/bin/env python3
"""
Analyze scale testing results after uploading 100 PDFs
"""

import requests
import json
from collections import Counter
from pathlib import Path

RAG_URL = "http://localhost:8001"

def analyze_results():
    print("=" * 80)
    print("🔥 SCALE TESTING ANALYSIS - 100 PDF Upload")
    print("=" * 80)
    print()

    # Get stats
    try:
        response = requests.get(f"{RAG_URL}/stats", timeout=10)
        if response.status_code == 200:
            stats = response.json()

            print("📊 **PROCESSING SUMMARY**")
            print(f"  • Total Documents: {stats.get('total_documents', 0)}")
            print(f"  • Total Chunks: {stats.get('total_chunks', 0)}")
            print(f"  • Avg Chunks/Doc: {stats.get('total_chunks', 0) / max(stats.get('total_documents', 1), 1):.1f}")
            print(f"  • Storage Used: {stats.get('storage_used_mb', 0):.2f} MB")
            print()

            # LLM Providers
            print("🤖 **LLM PROVIDERS**")
            for provider, status in stats.get('llm_provider_status', {}).items():
                status_icon = "✅" if status else "❌"
                print(f"  {status_icon} {provider}")
            print()
    except Exception as e:
        print(f"❌ Error getting stats: {e}")
        print()

    # Analyze Obsidian exports
    obsidian_dir = Path("/Users/danielteckentrup/Documents/my-git/rag-provider/obsidian")
    if obsidian_dir.exists():
        obsidian_files = list(obsidian_dir.glob("*.md"))
        print(f"📝 **OBSIDIAN EXPORTS**")
        print(f"  • Total Files: {len(obsidian_files)}")

        if obsidian_files:
            # Analyze tags
            all_tags = []
            all_domains = []
            all_significance = []
            all_quality_tiers = []

            for md_file in obsidian_files[:50]:  # Sample first 50
                try:
                    content = md_file.read_text()
                    lines = content.split('\n')

                    # Extract tags
                    for line in lines:
                        if line.startswith('tags:'):
                            tags_str = line.replace('tags:', '').strip()
                            if tags_str.startswith('['):
                                tags = eval(tags_str)  # Parse list
                                all_tags.extend(tags)
                        elif 'domain:' in line:
                            domain = line.split('domain:')[1].strip()
                            all_domains.append(domain)
                        elif 'significance_score:' in line:
                            try:
                                score = float(line.split('significance_score:')[1].strip())
                                all_significance.append(score)
                            except:
                                pass
                        elif 'quality_tier:' in line:
                            tier = line.split('quality_tier:')[1].strip()
                            all_quality_tiers.append(tier)
                except Exception as e:
                    pass

            # Tag analysis
            if all_tags:
                tag_counts = Counter(all_tags)
                print(f"\n  📌 **TAG ANALYSIS** ({len(all_tags)} total tags, {len(tag_counts)} unique)")
                print(f"  • Most common tags:")
                for tag, count in tag_counts.most_common(10):
                    print(f"    - {tag}: {count}x")

            # Domain analysis
            if all_domains:
                domain_counts = Counter(all_domains)
                print(f"\n  🌐 **DOMAIN ANALYSIS**")
                for domain, count in domain_counts.most_common(10):
                    print(f"    - {domain}: {count} docs")

            # Quality analysis
            if all_significance:
                avg_sig = sum(all_significance) / len(all_significance)
                print(f"\n  ⭐ **QUALITY SCORES**")
                print(f"    - Avg Significance: {avg_sig:.3f}")
                print(f"    - Min: {min(all_significance):.3f}")
                print(f"    - Max: {max(all_significance):.3f}")

            if all_quality_tiers:
                tier_counts = Counter(all_quality_tiers)
                print(f"    - Quality Tiers:")
                for tier, count in tier_counts.items():
                    print(f"      • {tier}: {count}")

        print()

    # Check for duplicates in logs
    print("🔍 **DUPLICATE DETECTION**")
    try:
        import subprocess
        result = subprocess.run(
            ['docker-compose', 'logs', 'rag-service'],
            capture_output=True,
            text=True,
            timeout=10
        )
        logs = result.stdout + result.stderr
        duplicate_count = logs.count('Skip processing - duplicate')
        print(f"  • Duplicates Detected: {duplicate_count}")
    except Exception as e:
        print(f"  • Could not check logs: {e}")

    print()
    print("=" * 80)
    print("✅ Analysis complete")
    print("=" * 80)

if __name__ == "__main__":
    analyze_results()
