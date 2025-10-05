# Telegram Bot for RAG Service

Standalone Telegram bot for testing the RAG provider.

## Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Get Telegram Bot Token:**
- Open Telegram
- Search for @BotFather
- Send `/newbot`
- Follow instructions to create bot
- Copy the token

3. **Set environment variable:**
```bash
export TELEGRAM_BOT_TOKEN="your_token_from_botfather"
```

4. **Make sure RAG service is running:**
```bash
cd .. && docker-compose up -d
```

5. **Run the bot:**
```bash
python rag_bot.py
```

## Usage

### Commands

- `/start` - Welcome message with instructions
- `/health` - Check RAG service health
- `/stats` - View service statistics
- `/search <query>` - Search documents

### Document Upload

Just send any file to the bot:
- PDF
- TXT
- MD
- DOCX
- EML

The bot will process it and show enrichment results.

### Natural Chat

Ask questions naturally:
- "What are my documents about?"
- "Summarize the ADHD research"
- "What did the tax document say?"

## Configuration

By default, the bot connects to `http://localhost:8001` (RAG service).

To change this:
```bash
export RAG_SERVICE_URL="http://your-server:8001"
```

## Testing

Try these tests:

1. **Upload test:**
   - Send a PDF to the bot
   - Check for success message with metadata

2. **Search test:**
   - Send: `/search AI`
   - Should return relevant documents

3. **Chat test:**
   - Send: "What topics do my documents cover?"
   - Should get AI-generated answer

4. **Duplicate test:**
   - Upload same file twice
   - Second upload should say "DUPLICATE DETECTED"

## Troubleshooting

**Bot doesn't respond:**
- Check TELEGRAM_BOT_TOKEN is set
- Check bot is running (`python rag_bot.py`)

**Upload fails:**
- Check RAG service is running: `curl http://localhost:8001/health`
- Check Docker containers: `docker-compose ps`

**Search returns nothing:**
- Upload some documents first
- Try simpler search terms
