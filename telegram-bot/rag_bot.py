#!/usr/bin/env python3
"""
RAG Telegram Bot - Direct connection to RAG service (localhost:8001)

This is a standalone bot for testing the RAG provider.
For unified ecosystem bot, see ai-ecosystem-integrated repo.
"""

import os
import logging
import aiohttp
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load .env from parent directory
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://localhost:8001")

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Session for HTTP requests
http_session = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "🤖 RAG Service Bot Ready!\n\n"
        "**Commands:**\n"
        "/search <query> - Search documents\n"
        "/stats - View service statistics\n"
        "/health - Check service health\n\n"
        "**Document Upload:**\n"
        "Just send me a file (PDF, TXT, MD, DOCX) and I'll process it!\n\n"
        "**Natural Chat:**\n"
        "Ask me anything about your documents!"
    )

async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check RAG service health"""
    try:
        async with http_session.get(f"{RAG_SERVICE_URL}/health", timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                await update.message.reply_text(
                    f"✅ Service Healthy\n\n"
                    f"Status: {data.get('status', 'unknown')}\n"
                    f"ChromaDB: {'✅' if data.get('chromadb_connected') else '❌'}"
                )
            else:
                await update.message.reply_text(f"❌ Service returned {response.status}")
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get service statistics"""
    try:
        async with http_session.get(f"{RAG_SERVICE_URL}/stats", timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                stats_text = "📊 Service Statistics\n\n"

                # Document counts
                if 'collections' in data:
                    stats_text += "**Collections:**\n"
                    for coll_name, coll_data in data['collections'].items():
                        count = coll_data.get('count', 0)
                        stats_text += f"  • {coll_name}: {count} documents\n"

                # Total costs (if available)
                if 'total_cost' in data:
                    stats_text += f"\n**Total Cost:** ${data['total_cost']:.4f}"

                await update.message.reply_text(stats_text)
            else:
                await update.message.reply_text(f"❌ Failed to get stats: {response.status}")
    except Exception as e:
        logger.error(f"Stats failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search documents"""
    if not context.args:
        await update.message.reply_text("Usage: /search <query>")
        return

    query = " ".join(context.args)
    await update.message.reply_text(f"🔍 Searching for: {query}...")

    try:
        payload = {"text": query, "top_k": 5}
        async with http_session.post(
            f"{RAG_SERVICE_URL}/search",
            json=payload,
            timeout=30
        ) as response:
            if response.status == 200:
                data = await response.json()
                results = data.get('results', [])

                if not results:
                    await update.message.reply_text("No results found.")
                    return

                response_text = f"Found {len(results)} results:\n\n"
                for i, result in enumerate(results[:3], 1):
                    title = result.get('metadata', {}).get('title', 'Untitled')
                    score = result.get('score', 0)
                    content = result.get('content', '')[:150]
                    tags = result.get('metadata', {}).get('tags', [])[:3]

                    response_text += f"**{i}. {title}**\n"
                    response_text += f"Score: {score:.3f}\n"
                    response_text += f"{content}...\n"
                    if tags:
                        response_text += f"Tags: {', '.join(tags)}\n"
                    response_text += "\n"

                await update.message.reply_text(response_text)
            else:
                await update.message.reply_text(f"❌ Search failed: {response.status}")
    except Exception as e:
        logger.error(f"Search failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document upload"""
    document = update.message.document

    await update.message.reply_text(f"📄 Processing {document.file_name}...")

    try:
        # Download file
        file = await context.bot.get_file(document.file_id)
        file_path = f"/tmp/{document.file_name}"
        await file.download_to_drive(file_path)

        # Upload to RAG service
        data = aiohttp.FormData()
        data.add_field('file',
                      open(file_path, 'rb'),
                      filename=document.file_name)

        async with http_session.post(
            f"{RAG_SERVICE_URL}/ingest/file",
            data=data,
            timeout=120
        ) as response:
            if response.status == 200:
                result = await response.json()

                # Extract key metadata
                metadata = result.get('metadata', {})
                title = metadata.get('title', 'Untitled')
                chunks = result.get('chunks', 0)
                tags = metadata.get('tags', [])[:5]
                domain = metadata.get('domain', 'N/A')
                significance = metadata.get('significance_score', 0)
                quality = metadata.get('quality_tier', 'N/A')

                response_text = (
                    f"✅ Document processed!\n\n"
                    f"**Title:** {title}\n"
                    f"**Chunks:** {chunks}\n"
                    f"**Domain:** {domain}\n"
                    f"**Significance:** {significance:.2f}\n"
                    f"**Quality:** {quality}\n"
                )

                if tags:
                    response_text += f"**Tags:** {', '.join(tags)}\n"

                # Show if duplicate
                if metadata.get('is_duplicate'):
                    response_text += "\n⚠️ **Duplicate detected!**"

                await update.message.reply_text(response_text)
            else:
                error_text = await response.text()
                await update.message.reply_text(f"❌ Upload failed: {response.status}\n{error_text[:200]}")

        # Clean up temp file
        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle natural language messages (chat with documents)"""
    # Skip if no text message (photo, video, etc.)
    if not update.message or not update.message.text:
        return

    question = update.message.text

    # Send thinking message and save it for editing
    thinking_msg = await update.message.reply_text("💬 Thinking...")

    try:
        payload = {
            "question": question,
            "llm_model": "anthropic/claude-3-5-sonnet-20241022",  # High quality (use specific version)
            "max_context_chunks": 10  # Get more context for better answers
        }

        async with http_session.post(
            f"{RAG_SERVICE_URL}/chat",
            json=payload,
            timeout=60
        ) as response:
            if response.status == 200:
                data = await response.json()
                answer = data.get('answer', 'No answer generated')
                cost = data.get('cost', 0)
                sources = data.get('sources', [])

                # Build response
                response_text = f"💬 **Answer:**\n\n{answer}\n\n"
                response_text += f"💰 Cost: ${cost:.6f}\n"

                # Show actual source documents
                if sources:
                    response_text += f"\n📚 **Sources ({len(sources)}):**\n"
                    for i, source in enumerate(sources[:5], 1):  # Show top 5
                        title = source.get('title', 'Untitled')
                        # Truncate long titles
                        if len(title) > 50:
                            title = title[:47] + "..."
                        response_text += f"{i}. {title}\n"
                    if len(sources) > 5:
                        response_text += f"... and {len(sources) - 5} more"

                # Split if too long (Telegram limit: 4096 chars)
                if len(response_text) > 4000:
                    # Send answer in chunks
                    chunks = [response_text[i:i+4000] for i in range(0, len(response_text), 4000)]
                    await thinking_msg.edit_text(chunks[0])
                    for chunk in chunks[1:]:
                        await update.message.reply_text(chunk)
                else:
                    # Edit the thinking message with the answer
                    await thinking_msg.edit_text(response_text)
            else:
                await thinking_msg.edit_text(f"❌ Chat failed: {response.status}")
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        await thinking_msg.edit_text(f"❌ Error: {str(e)[:200]}")

async def post_init(application: Application):
    """Initialize HTTP session"""
    global http_session
    http_session = aiohttp.ClientSession()

async def post_shutdown(application: Application):
    """Cleanup HTTP session"""
    global http_session
    if http_session:
        await http_session.close()

def main():
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        return

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("health", health))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Setup lifecycle hooks
    application.post_init = post_init
    application.post_shutdown = post_shutdown

    # Start bot
    logger.info(f"Bot starting... Connected to RAG service at {RAG_SERVICE_URL}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
