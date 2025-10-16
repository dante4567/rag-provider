#!/usr/bin/env python3
"""
Ingest Villa Luna emails with robust retry logic

Handles:
- Rate limiting (HTTP 429) with exponential backoff
- Connection errors with retry
- Progress tracking and resumption
"""
import requests
import glob
import time
import sys
from pathlib import Path
from typing import Optional, Dict, Any

BASE_URL = "http://localhost:8001"

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 10  # seconds
MAX_BACKOFF = 120  # seconds
BASE_DELAY = 5  # seconds between successful requests


def ingest_with_retry(email_path: str, max_retries: int = MAX_RETRIES) -> Optional[Dict[str, Any]]:
    """
    Ingest a single email with exponential backoff retry logic.

    Returns:
        dict with result if successful, None if failed after retries
    """
    filename = Path(email_path).name

    for attempt in range(max_retries):
        try:
            with open(email_path, 'rb') as f:
                files = {'file': (filename, f)}
                data = {'generate_obsidian': 'true'}
                response = requests.post(
                    f"{BASE_URL}/ingest/file",
                    files=files,
                    data=data,
                    timeout=120  # Increased timeout for large files
                )

            if response.status_code == 200:
                result = response.json()
                return {
                    'status': 'success',
                    'doc_id': result.get('doc_id', 'unknown')[:8],
                    'filename': filename
                }

            elif response.status_code == 429:
                # Rate limit - exponential backoff
                backoff_time = min(INITIAL_BACKOFF * (2 ** attempt), MAX_BACKOFF)
                print(f"⏳ Rate limit hit, waiting {backoff_time}s (attempt {attempt+1}/{max_retries})...", end=" ", flush=True)
                time.sleep(backoff_time)
                continue

            else:
                # Other HTTP error - retry with backoff
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
            # Connection error - retry with backoff
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
            # Unexpected error - don't retry
            return {
                'status': 'failed',
                'error': f'Unexpected: {str(e)}',
                'filename': filename
            }

    # All retries exhausted
    return {
        'status': 'failed',
        'error': 'Max retries exceeded',
        'filename': filename
    }


def main():
    """Main ingestion loop with progress tracking"""

    # Find all .eml files
    emails = list(glob.glob("/Users/danielteckentrup/Documents/villa-luna/*.eml"))
    total = len(emails)
    print(f"📧 Found {total} Villa Luna emails to ingest\n")

    if not emails:
        print("❌ No emails found in /Users/danielteckentrup/Documents/villa-luna/")
        return

    successful = 0
    failed = 0
    failed_files = []

    # Progress tracking
    start_time = time.time()

    for i, email_path in enumerate(sorted(emails), 1):
        filename = Path(email_path).name

        # Progress indicator
        progress = f"[{i}/{total}]"
        print(f"{progress} 📧 {filename}...", end=" ", flush=True)

        # Ingest with retry
        result = ingest_with_retry(email_path)

        if result and result['status'] == 'success':
            print(f"✅ {result['doc_id']}")
            successful += 1
        else:
            error_msg = result.get('error', 'unknown') if result else 'unknown'
            print(f"❌ {error_msg}")
            failed += 1
            failed_files.append(filename)

        # Base delay between requests (even successful ones)
        if i < total:  # Don't delay after last file
            time.sleep(BASE_DELAY)

        # Progress update every 10 files
        if i % 10 == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed * 60  # docs per minute
            eta_seconds = (total - i) / rate * 60 if rate > 0 else 0
            eta_minutes = int(eta_seconds / 60)
            print(f"   ⏱️  Progress: {successful} ok, {failed} failed | {rate:.1f} docs/min | ETA: {eta_minutes}m")

    # Final summary
    elapsed = time.time() - start_time
    elapsed_minutes = int(elapsed / 60)
    success_rate = (successful / total * 100) if total > 0 else 0

    print(f"\n{'='*60}")
    print(f"📊 INGESTION SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Successful: {successful}/{total} ({success_rate:.1f}%)")
    print(f"❌ Failed:     {failed}/{total} ({100-success_rate:.1f}%)")
    print(f"⏱️  Duration:   {elapsed_minutes}m {int(elapsed % 60)}s")
    print(f"{'='*60}")

    # Save failed files for retry
    if failed_files:
        failed_log = Path("failed_ingestions.txt")
        with open(failed_log, 'w') as f:
            f.write('\n'.join(failed_files))
        print(f"\n📝 Failed files saved to: {failed_log}")
        print(f"   Re-run with: ./retry_failed.py")

    # Exit code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
