#!/usr/bin/env python3
"""Ingest Villa Luna emails"""
import requests
import glob
import time
from pathlib import Path

BASE_URL = "http://localhost:8001"

# Find all .eml files
emails = list(glob.glob("/Users/danielteckentrup/Documents/villa-luna/*.eml"))
print(f"📧 Found {len(emails)} Villa Luna emails to ingest\n")

successful = 0
failed = 0

for email_path in sorted(emails):
    filename = Path(email_path).name
    print(f"📧 Ingesting: {filename}...", end=" ", flush=True)

    try:
        with open(email_path, 'rb') as f:
            files = {'file': (filename, f)}
            data = {'generate_obsidian': 'true'}
            response = requests.post(
                f"{BASE_URL}/ingest/file",
                files=files,
                data=data,
                timeout=60
            )

        if response.status_code == 200:
            result = response.json()
            print(f"✅ {result.get('doc_id', 'success')[:8]}")
            successful += 1
        else:
            print(f"❌ HTTP {response.status_code}")
            failed += 1

    except Exception as e:
        print(f"❌ Error: {e}")
        failed += 1

    time.sleep(5)  # Rate limit (Groq: ~12 req/min, safe for 30 req/min limit)

print(f"\n📊 Summary: {successful} successful, {failed} failed")
