# CardDAV / CalDAV Sync Guide - RAG Provider

## Overview

The RAG Provider automatically generates:
- **vCard files** (.vcf) for people extracted from documents
- **iCalendar files** (.ics) for dates extracted from documents

This guide shows how to sync these files with your calendar and contacts apps.

---

## Quick Start

### What Gets Generated?

**vCards** (`data/contacts/`):
- One `.vcf` file per person mentioned in documents
- Includes name, role, organization, document sources
- Updates existing vCards when same person appears in multiple documents

**Calendar Events** (`data/calendar/`):
- One `.ics` file per date extracted from documents
- Auto-detects event type (deadline, meeting, court hearing, school event)
- Includes context from document, categories, and reminders
- Deadline events get 7-day advance reminders

---

## Sync Methods

### Method 1: Direct Import (One-Time)

#### iOS / macOS

**Contacts (vCards)**:
```bash
# Export all contacts to single file
curl http://localhost:8001/contacts/export > all_contacts.vcf

# Import to Contacts app
open all_contacts.vcf
```

**Calendar (iCal)**:
```bash
# Export all events to single calendar
curl http://localhost:8001/calendar/export > all_events.ics

# Import to Calendar app
open all_events.ics
```

#### Android

**Contacts**:
1. Download `all_contacts.vcf`
2. Open Contacts app → Settings → Import
3. Select VCF file

**Calendar**:
1. Download `all_events.ics`
2. Open Calendar app → Settings → Import
3. Select ICS file

#### Outlook / Thunderbird

**Import vCards**:
- Outlook: File → Import & Export → vCard (.vcf) file
- Thunderbird: Address Book → Tools → Import → vCard files

**Import Calendar**:
- Outlook: File → Import & Export → iCalendar (.ics) file
- Thunderbird: Calendar → Import → iCalendar (.ics) file

---

### Method 2: Automated Sync via WebDAV

#### Prerequisites

You'll need a WebDAV server to sync with calendar/contacts apps. Options:

1. **Nextcloud** (self-hosted or hosted)
2. **Google Calendar / Contacts** (via CalDAV/CardDAV)
3. **iCloud** (Apple devices)
4. **Radicale** (lightweight self-hosted)

#### Setup with Nextcloud

**Step 1: Install Nextcloud**
```bash
# Docker Nextcloud setup
docker run -d \
  --name nextcloud \
  -p 8080:80 \
  -v nextcloud_data:/var/www/html \
  nextcloud:latest
```

**Step 2: Configure Sync Script**

Create `/app/scripts/sync_to_nextcloud.sh`:
```bash
#!/bin/bash

NEXTCLOUD_URL="https://your-nextcloud.com"
NEXTCLOUD_USER="username"
NEXTCLOUD_PASS="password"

# Sync contacts
curl -X PUT \
  -u "$NEXTCLOUD_USER:$NEXTCLOUD_PASS" \
  --data-binary "@/app/data/contacts/all_contacts.vcf" \
  "$NEXTCLOUD_URL/remote.php/dav/addressbooks/users/$NEXTCLOUD_USER/contacts/rag-contacts.vcf"

# Sync calendar
curl -X PUT \
  -u "$NEXTCLOUD_USER:$NEXTCLOUD_PASS" \
  --data-binary "@/app/data/calendar/all_events.ics" \
  "$NEXTCLOUD_URL/remote.php/dav/calendars/users/$NEXTCLOUD_USER/rag-events.ics"
```

**Step 3: Automate with Cron**
```bash
# Add to crontab (sync every hour)
0 * * * * /app/scripts/sync_to_nextcloud.sh
```

**Step 4: Connect Apps to Nextcloud**

iOS/macOS:
1. Settings → Contacts → Accounts → Add Account → CardDAV
2. Server: `your-nextcloud.com`
3. Username/Password
4. Repeat for Calendar (CalDAV)

Android:
1. Install DAVx⁵ from Play Store
2. Add account → Nextcloud
3. Enter credentials
4. Select Contacts and Calendar to sync

---

### Method 3: Auto-Import with File Watching

#### macOS (Hazel)

**Contacts Auto-Import**:
```
Folder to watch: ~/Documents/rag-provider/data/contacts/
If all of the following conditions are met:
  Extension is vcf
Do the following:
  Open with: Contacts.app
```

**Calendar Auto-Import**:
```
Folder to watch: ~/Documents/rag-provider/data/calendar/
If all of the following conditions are met:
  Extension is ics
Do the following:
  Open with: Calendar.app
```

#### Linux (inotifywait)

Create `/app/scripts/auto_import.sh`:
```bash
#!/bin/bash

# Watch contacts directory
inotifywait -m /app/data/contacts -e create -e modify |
while read path action file; do
    if [[ "$file" == *.vcf ]]; then
        echo "New vCard: $file"
        # Import to system contacts
        # (command depends on your desktop environment)
    fi
done &

# Watch calendar directory
inotifywait -m /app/data/calendar -e create -e modify |
while read path action file; do
    if [[ "$file" == *.ics ]]; then
        echo "New calendar event: $file"
        # Import to system calendar
        # (command depends on your desktop environment)
    fi
done
```

Run as systemd service:
```ini
# /etc/systemd/system/rag-auto-import.service
[Unit]
Description=RAG Auto-Import Contacts and Calendar

[Service]
ExecStart=/app/scripts/auto_import.sh
Restart=always

[Install]
WantedBy=multi-user.target
```

---

### Method 4: Google Sync (via API)

#### Contacts (Google Contacts API)

Create `/app/scripts/sync_to_google_contacts.py`:
```python
from google.oauth2 import service_account
from googleapiclient.discovery import build
from pathlib import Path
import vobject

SCOPES = ['https://www.googleapis.com/auth/contacts']
SERVICE_ACCOUNT_FILE = 'credentials.json'

def sync_contacts():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)

    service = build('people', 'v1', credentials=creds)

    # Read all vCards
    contacts_dir = Path('/app/data/contacts')
    for vcard_file in contacts_dir.glob('*.vcf'):
        with open(vcard_file) as f:
            vcard = vobject.readOne(f.read())

        # Create contact in Google
        person = {
            'names': [{'givenName': vcard.n.value.given, 'familyName': vcard.n.value.family}],
            'emailAddresses': [{'value': str(vcard.email.value)}] if hasattr(vcard, 'email') else [],
            'organizations': [{'name': str(vcard.org.value[0])}] if hasattr(vcard, 'org') else []
        }

        service.people().createContact(body=person).execute()

if __name__ == '__main__':
    sync_contacts()
```

#### Calendar (Google Calendar API)

```python
from google.oauth2 import service_account
from googleapiclient.discovery import build
from icalendar import Calendar
from pathlib import Path

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'credentials.json'

def sync_calendar():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)

    service = build('calendar', 'v3', credentials=creds)

    # Read all iCal events
    calendar_dir = Path('/app/data/calendar')
    for ics_file in calendar_dir.glob('*.ics'):
        with open(ics_file, 'rb') as f:
            cal = Calendar.from_ical(f.read())

        for component in cal.walk():
            if component.name == "VEVENT":
                event = {
                    'summary': str(component.get('summary')),
                    'description': str(component.get('description')),
                    'start': {'date': component.get('dtstart').dt.isoformat()},
                    'end': {'date': component.get('dtend').dt.isoformat()}
                }

                service.events().insert(calendarId='primary', body=event).execute()

if __name__ == '__main__':
    sync_calendar()
```

---

## API Endpoints

The RAG Provider exposes endpoints to export contacts and calendar:

### Export All Contacts
```http
GET /contacts/export
```

Returns: Combined vCard file with all contacts

```bash
curl http://localhost:8001/contacts/export > all_contacts.vcf
```

### Export All Calendar Events
```http
GET /calendar/export
```

Returns: Combined iCalendar file with all events

```bash
curl http://localhost:8001/calendar/export > all_events.ics
```

### List Individual Files
```http
GET /contacts/list
GET /calendar/list
```

Returns: JSON list of all vCard/iCal files

```bash
curl http://localhost:8001/contacts/list | jq
curl http://localhost:8001/calendar/list | jq
```

---

## How It Works

### vCard Generation

**Triggered**: When a document is ingested with `generate_obsidian=true`

**Process**:
1. Enrichment service extracts people from document
2. ContactService creates/updates vCard for each person
3. Merges information if person appears in multiple documents

**vCard 3.0 Format**:
```
BEGIN:VCARD
VERSION:3.0
FN:Rechtsanwalt Dr. Schmidt
N:Schmidt;Dr.;;;
TITLE:Lawyer
ORG:Law Firm Name
NOTE:Mentioned in: court-decision.pdf, contract.pdf
CATEGORIES:RAG-Extracted,Lawyer
REV:20251008T160000Z
END:VCARD
```

### iCalendar Generation

**Triggered**: When a document is ingested with dates

**Process**:
1. Enrichment service extracts dates from document
2. CalendarService infers event type from context
3. Creates event with description, category, and reminder

**Event Types** (auto-detected):
- **Deadline**: Keywords like "deadline", "frist", "bis", "until"
- **Meeting**: Keywords like "meeting", "termin", "call"
- **Court Hearing**: Keywords like "hearing", "verhandlung", "gericht"
- **School Event**: Keywords like "anmeldung", "einschulung", "enrollment"

**iCal Format**:
```
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//RAG Provider//Calendar Service//EN
BEGIN:VEVENT
UID:abc123@rag-provider.local
DTSTART;VALUE=DATE:20251115
SUMMARY:Deadline: School Enrollment
DESCRIPTION:Source: school-info.md\nContext: Registration deadline November 15
CATEGORIES:RAG-Extracted,Deadline
BEGIN:VALARM
ACTION:DISPLAY
TRIGGER:-P7D
END:VALARM
END:VEVENT
END:VCALENDAR
```

---

## Troubleshooting

### No vCards/Events Generated

**Check**: Are people/dates being extracted?
```bash
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@document.pdf" \
  -F "generate_obsidian=true" | jq '.metadata.people, .metadata.entities.dates'
```

If null/empty:
- Enrichment may not be extracting entities properly
- Check document content (is there actually text with names/dates?)
- Review enrichment logs: `docker-compose logs rag-service | grep enrichment`

### Sync Not Working

**Nextcloud**:
- Verify credentials
- Check WebDAV URL (should end with `/remote.php/dav/`)
- Test manually: `curl -u user:pass https://nextcloud.com/remote.php/dav/`

**Google**:
- Verify API credentials
- Enable People API and Calendar API in Google Cloud Console
- Check service account permissions

### Duplicate Contacts

vCards are merged by name. If you see duplicates:
- Names must match exactly
- Check file: `cat data/contacts/person-name.vcf`
- Delete duplicates manually or clear directory: `rm data/contacts/*.vcf`

### Events Not Showing

**iOS/macOS**:
- Calendar must be set to "Show All Calendars"
- Check Calendar → Calendars → RAG Extracted Events (✓)

**Android**:
- Open Calendar app → Settings → Calendars to display
- Enable "RAG Extracted Events"

---

## Best Practices

### 1. Regular Sync

Set up automated sync (hourly or daily) rather than one-time import:
```bash
# Cron: Sync every 6 hours
0 */6 * * * /app/scripts/sync_to_nextcloud.sh
```

### 2. Separate Calendar

Create a dedicated "RAG Extracted" calendar to keep auto-generated events separate:
- Easier to filter
- Can delete/refresh without affecting personal events

### 3. Review Before Sync

Not all extracted people/dates may be relevant:
```bash
# List all vCards before syncing
ls data/contacts/*.vcf

# Preview a vCard
cat data/contacts/person-name.vcf
```

### 4. Privacy

vCards include document sources. If sharing contacts:
- Review NOTE field (contains document filenames)
- Remove sensitive sources before export

---

## Advanced: Custom Sync Workflows

### Selective Sync (Only Legal Contacts)

```bash
# Export only contacts with "Legal" category
for file in data/contacts/*.vcf; do
  if grep -q "CATEGORIES:.*Legal" "$file"; then
    cat "$file" >> legal_contacts.vcf
  fi
done
```

### Sync to Multiple Services

```bash
#!/bin/bash
# Sync to both Nextcloud and Google

# Export once
curl http://localhost:8001/contacts/export > all_contacts.vcf
curl http://localhost:8001/calendar/export > all_events.ics

# Sync to Nextcloud
curl -X PUT -u "$NC_USER:$NC_PASS" \
  --data-binary "@all_contacts.vcf" \
  "$NC_URL/remote.php/dav/addressbooks/users/$NC_USER/contacts/rag.vcf"

# Sync to Google (via API)
python sync_to_google_contacts.py
python sync_to_google_calendar.py
```

---

## Next Steps

1. **Choose sync method** - Direct import, WebDAV, or API
2. **Test with sample data** - Ingest a document with people/dates
3. **Verify export** - Check `data/contacts/` and `data/calendar/`
4. **Set up automation** - Cron job or file watcher
5. **Connect apps** - iOS/Android/Desktop calendar and contacts

See `DOCUMENT_INGESTION_GUIDE.md` for how to add documents and trigger entity extraction.
