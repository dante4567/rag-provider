"""
Unit tests for Telegram RAG bot
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
import os

# Add telegram-bot to path
sys.path.insert(0, os.path.dirname(__file__))

# Mock telegram before importing rag_bot
sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()

import rag_bot


class TestStartCommand:
    """Tests for /start command"""

    @pytest.mark.asyncio
    async def test_start_sends_welcome_message(self):
        """Test that /start sends welcome message"""
        update = Mock()
        update.message.reply_text = AsyncMock()
        context = Mock()

        await rag_bot.start(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "RAG Service Bot" in call_args
        assert "/search" in call_args
        assert "/health" in call_args


class TestHealthCommand:
    """Tests for /health command"""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check"""
        update = Mock()
        update.message.reply_text = AsyncMock()
        context = Mock()

        # Mock aiohttp response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "status": "healthy",
            "chroma_connected": True
        })

        with patch('aiohttp.ClientSession.get', return_value=mock_response):
            # Create session
            rag_bot.http_session = AsyncMock()
            rag_bot.http_session.get = AsyncMock(return_value=mock_response)
            rag_bot.http_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            rag_bot.http_session.get.return_value.__aexit__ = AsyncMock()

            await rag_bot.health(update, context)

            update.message.reply_text.assert_called_once()
            call_args = update.message.reply_text.call_args[0][0]
            assert "✅" in call_args or "healthy" in call_args.lower()

    @pytest.mark.asyncio
    async def test_health_check_service_down(self):
        """Test health check when service is down"""
        update = Mock()
        update.message.reply_text = AsyncMock()
        context = Mock()

        # Mock connection error
        with patch('aiohttp.ClientSession.get', side_effect=Exception("Connection refused")):
            rag_bot.http_session = AsyncMock()
            rag_bot.http_session.get = AsyncMock(side_effect=Exception("Connection refused"))

            await rag_bot.health(update, context)

            update.message.reply_text.assert_called_once()
            call_args = update.message.reply_text.call_args[0][0]
            assert "❌" in call_args or "error" in call_args.lower()


class TestSearchCommand:
    """Tests for /search command"""

    @pytest.mark.asyncio
    async def test_search_no_query(self):
        """Test search without query text"""
        update = Mock()
        update.message.reply_text = AsyncMock()
        update.message.text = "/search"
        context = Mock()
        context.args = []

        await rag_bot.search_documents(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "Usage:" in call_args or "provide" in call_args.lower()

    @pytest.mark.asyncio
    async def test_search_with_query(self):
        """Test search with query text"""
        update = Mock()
        update.message.reply_text = AsyncMock()
        context = Mock()
        context.args = ["test", "query"]

        # Mock aiohttp response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "results": [
                {
                    "content": "Test content",
                    "metadata": {"title": "Test Doc"},
                    "score": 0.95
                }
            ]
        })

        rag_bot.http_session = AsyncMock()
        rag_bot.http_session.post = AsyncMock()
        rag_bot.http_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        rag_bot.http_session.post.return_value.__aexit__ = AsyncMock()

        await rag_bot.search_documents(update, context)

        update.message.reply_text.assert_called()
        # Should send at least one message (possibly "Searching..." then results)
        assert update.message.reply_text.call_count >= 1


class TestStatsCommand:
    """Tests for /stats command"""

    @pytest.mark.asyncio
    async def test_stats_success(self):
        """Test successful stats retrieval"""
        update = Mock()
        update.message.reply_text = AsyncMock()
        context = Mock()

        # Mock aiohttp response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "total_documents": 100,
            "total_cost_usd": 1.25,
            "collections": {"main": 100}
        })

        rag_bot.http_session = AsyncMock()
        rag_bot.http_session.get = AsyncMock()
        rag_bot.http_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        rag_bot.http_session.get.return_value.__aexit__ = AsyncMock()

        await rag_bot.stats(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "100" in call_args


class TestFileUpload:
    """Tests for file upload handling"""

    @pytest.mark.asyncio
    async def test_handle_document_upload(self):
        """Test document file upload"""
        update = Mock()
        update.message.reply_text = AsyncMock()
        update.message.document = Mock()
        update.message.document.file_name = "test.pdf"
        update.message.document.get_file = AsyncMock()

        mock_file = AsyncMock()
        mock_file.download_to_drive = AsyncMock()
        update.message.document.get_file.return_value = mock_file

        context = Mock()

        # Mock aiohttp response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "status": "success",
            "metadata": {"title": "Test"}
        })

        rag_bot.http_session = AsyncMock()
        rag_bot.http_session.post = AsyncMock()
        rag_bot.http_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        rag_bot.http_session.post.return_value.__aexit__ = AsyncMock()

        await rag_bot.handle_document(update, context)

        # Should send processing message and success message
        assert update.message.reply_text.call_count >= 1


class TestChatMessage:
    """Tests for natural language chat"""

    @pytest.mark.asyncio
    async def test_handle_message_chat_query(self):
        """Test handling natural language chat message"""
        update = Mock()
        update.message.reply_text = AsyncMock()
        update.message.text = "What is the capital of France?"
        context = Mock()

        # Mock aiohttp response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "answer": "Paris is the capital of France.",
            "sources": [],
            "cost_usd": 0.001
        })

        rag_bot.http_session = AsyncMock()
        rag_bot.http_session.post = AsyncMock()
        rag_bot.http_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        rag_bot.http_session.post.return_value.__aexit__ = AsyncMock()

        await rag_bot.handle_message(update, context)

        # Should send at least one message
        assert update.message.reply_text.call_count >= 1


class TestErrorHandling:
    """Tests for error handling"""

    @pytest.mark.asyncio
    async def test_error_handler(self):
        """Test global error handler"""
        update = Mock()
        context = Mock()
        context.error = Exception("Test error")

        # Should not raise exception
        await rag_bot.error_handler(update, context)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
