#!/usr/bin/env python3
"""Ingest all documents from data/input/ folder"""
import requests
import glob
import time
from pathlib import Path

BASE_URL = "http://localhost:8001"

# Find all documents
documents = list(glob.glob("data/input/*.pdf")) + list(glob.glob("data/input/*.md"))
documents = [f for f in documents if not f.endswith("README.md")]

print(f"📦 Found {len(documents)} documents to ingest\n")

successful = 0
failed = 0

for doc_path in sorted(documents):
    filename = Path(doc_path).name
    print(f"📄 Ingesting: {filename}...", end=" ", flush=True)

    try:
        with open(doc_path, 'rb') as f:
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
            print(f"✅ {result.get('status', 'success')}")
            successful += 1
        else:
            print(f"❌ HTTP {response.status_code}")
            failed += 1

    except Exception as e:
        print(f"❌ Error: {e}")
        failed += 1

    time.sleep(1)  # Rate limit

print(f"\n📊 Summary: {successful} successful, {failed} failed")
