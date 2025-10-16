# Obsidian Bases Templates

This directory contains template configurations for creating powerful database views in Obsidian using the **Bases** plugin.

**Important:** `.base` files are created and managed by Obsidian through its UI. The templates below show you exactly what filters and properties to configure when creating your bases manually.

---

## Quick Start

1. **Enable Bases Plugin** in Obsidian Settings → Core Plugins
2. **Create a new base** (right-click vault root → "New base")
3. **Follow one of the templates below** to configure filters and properties

---

## Template 1: All Documents (Master List)

**Purpose:** Browse all ingested documents with key metadata

**How to Create:**
1. Create new base: "All Documents.base"
2. **Filter:** None (leave empty to show all notes)
3. **Properties to Display:**
   - `title`
   - `doc_type`
   - `created_at`
   - `topics`
   - `people`
4. **Sort:** `created_at` descending
5. **Group By:** None

**Use Case:** "What did I ingest recently?"

---

## Template 2: Emails (Inbox View)

**Purpose:** Email database with sender filtering

**How to Create:**
1. Create new base: "Emails.base"
2. **Filter:**
   ```
   doc_type = "email"
   ```
3. **Properties to Display:**
   - `subject` (or `title`)
   - `sender`
   - `created_at`
   - `has_attachments`
   - `is_urgent`
   - `thread_id`
4. **Sort:** `created_at` descending
5. **Optional Views:** Create multiple views in same base:
   - **View 1:** "All Emails" (no additional filter)
   - **View 2:** "Urgent" (add filter: `is_urgent = true`)
   - **View 3:** "This Week" (add filter: `created_at > today - 7 days`)

**Use Cases:**
- "Show me urgent emails"
- "Emails from Alice Smith" (filter: `sender contains "alice"`)
- "Emails with attachments from last week"

---

## Template 3: People (Contact Database)

**Purpose:** All person entity stubs with contact details

**How to Create:**
1. Create new base: "People.base"
2. **Filter:**
   ```
   file.folder = "refs/people"
   ```
3. **Properties to Display:**
   - `file.name` (person's name)
   - `role`
   - `organization` (shown as wikilink)
   - `email`
   - `phone`
4. **Sort:** `file.name` ascending
5. **Group By:** `organization` (optional)

**Advanced Query:**
To show people from a specific organization, add filter:
```
Organization = [[Villa Luna]]
```

**Use Case:** "Who works at Villa Luna?"

---

## Template 4: Projects (Project Tracker)

**Purpose:** Documents grouped by project

**How to Create:**
1. Create new base: "Projects.base"
2. **Filter:**
   ```
   projects exists
   ```
3. **Properties to Display:**
   - `title`
   - `projects`
   - `created_at`
   - `doc_type`
   - `topics`
4. **Sort:** `created_at` descending
5. **Group By:** `projects`

**Use Case:** "All documents related to school-2026 project"

---

## Template 5: By Topic (Content Explorer)

**Purpose:** Browse documents by topic hierarchy

**How to Create:**
1. Create new base: "By Topic.base"
2. **Filter:**
   ```
   topics exists
   ```
3. **Properties to Display:**
   - `title`
   - `topics`
   - `doc_type`
   - `created_at`
   - `people`
4. **Sort:** `created_at` descending
5. **Group By:** `topics` (shows first topic)

**Advanced Filtering:**
To show only AI-related documents:
```
topics contains "technology/ai"
```

**Use Case:** "Show me all technology/ai documents"

---

## Template 6: Action Items (Task Tracker)

**Purpose:** Documents requiring action

**How to Create:**
1. Create new base: "Action Items.base"
2. **Filter:**
   ```
   has_action_items = true
   ```
   Optional additional filter:
   ```
   AND status != "completed"
   ```
3. **Properties to Display:**
   - `title`
   - `doc_type`
   - `created_at`
   - `is_urgent`
   - `priority` (if available)
   - `status` (if available)
4. **Sort:** `is_urgent` descending, then `created_at` descending
5. **Optional Views:**
   - **View 1:** "All" (show all action items)
   - **View 2:** "Urgent" (filter: `is_urgent = true`)
   - **View 3:** "High Priority" (filter: `priority = "high"`)

**Use Case:** "What needs my attention?"

---

## Advanced Filter Examples

### Emails from Specific Person
```
doc_type = "email"
AND sender contains "alice"
```

### Urgent Items This Week
```
is_urgent = true
AND created_at > today - 7 days
```

### Chat Logs About Python
```
doc_type = "llm_chat"
AND technologies_mentioned contains "Python"
```

### Documents with Multiple Attachments
```
has_attachments = true
AND attachment_count > 2
```

### Villa Luna Related Content
```
organizations contains "Villa Luna"
OR places contains "Villa Luna"
OR topics contains "education/kindergarten"
```

### Combining Conditions
```
(doc_type = "email" AND is_urgent = true)
OR
(has_action_items = true AND status = "pending")
```

---

## Property Reference Quick Guide

### Common Filterable Properties

| Property | Type | Operators | Example |
|----------|------|-----------|---------|
| `doc_type` | Text | `=`, `!=`, `contains` | `doc_type = "email"` |
| `created_at` | Date | `=`, `>`, `<`, `>=`, `<=` | `created_at > 2024-10-01` |
| `has_attachments` | Checkbox | `=`, `!=` | `has_attachments = true` |
| `is_urgent` | Checkbox | `=`, `!=` | `is_urgent = true` |
| `topics` | List | `contains`, `not contains` | `topics contains "ai"` |
| `people` | List | `contains` | `people contains "Alice"` |
| `attachment_count` | Number | `=`, `>`, `<`, `>=`, `<=` | `attachment_count > 3` |

### Operators

- `=` - Equals
- `!=` - Not equals
- `contains` - List/text contains value
- `not contains` - List/text doesn't contain
- `>` - Greater than
- `<` - Less than
- `>=` - Greater than or equal
- `<=` - Less than or equal
- `exists` - Property exists (any value)
- `not exists` - Property doesn't exist

### Logical Operators

- `AND` - All conditions must be true
- `OR` - Any condition can be true
- `NOT` - Condition must be false

---

## Tips for Creating Effective Bases

1. **Start Simple:** Create 1-2 bases first, then expand
2. **Use Clear Names:** "Urgent Emails" not "Base 1"
3. **Multiple Views:** Group related filters in one base file
4. **Test Filters:** Start broad, then add specific filters
5. **Property Selection:** Only show properties you actually need

---

## Creating a Dashboard

Combine multiple bases in one note for an overview:

**Create: "Dashboard.md"**

```markdown
# My Knowledge Dashboard

## 🔥 Urgent Action Items
![[Action Items.base#Urgent]]

## 📧 Recent Emails
![[Emails.base#This Week]]

## 💡 Current Projects
![[Projects.base]]

## 👥 Recent Contacts
![[People.base#Recently Added]]
```

---

## Need Help?

- See [OBSIDIAN_BASES_GUIDE.md](../../docs/guides/OBSIDIAN_BASES_GUIDE.md) for full documentation
- Check [Obsidian Bases Official Docs](https://help.obsidian.md/bases)
- Create an issue on [GitHub](https://github.com/dante4567/rag-provider/issues)

---

**Remember:** Your RAG-generated notes already have all the properties needed for these bases. Just create the base, configure the filters, and start exploring!
