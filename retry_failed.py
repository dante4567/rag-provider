#!/usr/bin/env python3
"""
Retry failed ingestions from failed_ingestions.txt

This script reads the list of failed files and attempts to re-ingest them
with the same retry logic as the main ingestion script.
"""
import requests
import time
import sys
from pathlib import Path
from typing import Optional, Dict, Any

BASE_URL = "http://localhost:8001"
VILLA_LUNA_DIR = Path("/Users/danielteckentrup/Documents/villa-luna")
FAILED_LOG = Path("failed_ingestions.txt")

# Retry configuration (more aggressive for retry script)
MAX_RETRIES = 5
INITIAL_BACKOFF = 15  # seconds
MAX_BACKOFF = 180  # seconds
BASE_DELAY = 8  # seconds between successful requests


def ingest_with_retry(email_path: Path, max_retries: int = MAX_RETRIES) -> Optional[Dict[str, Any]]:
    """Ingest a single email with exponential backoff retry logic."""
    filename = email_path.name

    for attempt in range(max_retries):
        try:
            with open(email_path, 'rb') as f:
                files = {'file': (filename, f)}
                data = {'generate_obsidian': 'true'}
                response = requests.post(
                    f"{BASE_URL}/ingest/file",
                    files=files,
                    data=data,
                    timeout=120
                )

            if response.status_code == 200:
                result = response.json()
                return {
                    'status': 'success',
                    'doc_id': result.get('doc_id', 'unknown')[:8],
                    'filename': filename
                }

            elif response.status_code == 429:
                backoff_time = min(INITIAL_BACKOFF * (2 ** attempt), MAX_BACKOFF)
                print(f"⏳ Rate limit, waiting {backoff_time}s (attempt {attempt+1}/{max_retries})...", end=" ", flush=True)
                time.sleep(backoff_time)
                continue

            else:
                if attempt < max_retries - 1:
                    backoff_time = INITIAL_BACKOFF * (2 ** attempt)
                    print(f"⚠️  HTTP {response.status_code}, retrying in {backoff_time}s...", end=" ", flush=True)
                    time.sleep(backoff_time)
                    continue
                else:
                    return {
                        'status': 'failed',
                        'error': f'HTTP {response.status_code}',
                        'filename': filename
                    }

        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                ConnectionResetError) as e:
            if attempt < max_retries - 1:
                backoff_time = INITIAL_BACKOFF * (2 ** attempt)
                print(f"🔌 Connection error, retrying in {backoff_time}s...", end=" ", flush=True)
                time.sleep(backoff_time)
                continue
            else:
                return {
                    'status': 'failed',
                    'error': str(e),
                    'filename': filename
                }

        except Exception as e:
            return {
                'status': 'failed',
                'error': f'Unexpected: {str(e)}',
                'filename': filename
            }

    return {
        'status': 'failed',
        'error': 'Max retries exceeded',
        'filename': filename
    }


def main():
    """Retry failed ingestions"""

    if not FAILED_LOG.exists():
        print(f"❌ No failed ingestions file found: {FAILED_LOG}")
        print(f"   Run ./ingest_villa_luna.py first to generate this file")
        return

    # Read failed files
    with open(FAILED_LOG, 'r') as f:
        failed_filenames = [line.strip() for line in f if line.strip()]

    total = len(failed_filenames)
    print(f"🔄 Retrying {total} failed ingestions\n")

    if total == 0:
        print("✅ No failed files to retry!")
        return

    successful = 0
    still_failed = 0
    still_failed_files = []

    start_time = time.time()

    for i, filename in enumerate(failed_filenames, 1):
        email_path = VILLA_LUNA_DIR / filename

        if not email_path.exists():
            print(f"[{i}/{total}] ⚠️  File not found: {filename}")
            still_failed += 1
            still_failed_files.append(filename)
            continue

        progress = f"[{i}/{total}]"
        print(f"{progress} 📧 {filename}...", end=" ", flush=True)

        result = ingest_with_retry(email_path)

        if result and result['status'] == 'success':
            print(f"✅ {result['doc_id']}")
            successful += 1
        else:
            error_msg = result.get('error', 'unknown') if result else 'unknown'
            print(f"❌ {error_msg}")
            still_failed += 1
            still_failed_files.append(filename)

        # Delay between requests
        if i < total:
            time.sleep(BASE_DELAY)

        # Progress update every 5 files
        if i % 5 == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed * 60
            eta_seconds = (total - i) / rate * 60 if rate > 0 else 0
            eta_minutes = int(eta_seconds / 60)
            print(f"   ⏱️  Progress: {successful} recovered, {still_failed} still failed | ETA: {eta_minutes}m")

    # Final summary
    elapsed = time.time() - start_time
    elapsed_minutes = int(elapsed / 60)
    recovered_rate = (successful / total * 100) if total > 0 else 0

    print(f"\n{'='*60}")
    print(f"📊 RETRY SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Recovered:     {successful}/{total} ({recovered_rate:.1f}%)")
    print(f"❌ Still failed:  {still_failed}/{total} ({100-recovered_rate:.1f}%)")
    print(f"⏱️  Duration:      {elapsed_minutes}m {int(elapsed % 60)}s")
    print(f"{'='*60}")

    # Update failed files list
    if still_failed_files:
        with open(FAILED_LOG, 'w') as f:
            f.write('\n'.join(still_failed_files))
        print(f"\n📝 {still_failed} files still failed, list updated in: {FAILED_LOG}")
        print(f"   Run ./retry_failed.py again to retry")
    else:
        # All recovered - delete failed log
        FAILED_LOG.unlink()
        print(f"\n🎉 All files recovered! Deleted {FAILED_LOG}")

    sys.exit(0 if still_failed == 0 else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
