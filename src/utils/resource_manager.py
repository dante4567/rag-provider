"""
Resource management for temporary files, memory, and connections
"""
import os
import shutil
import tempfile
import logging
import asyncio
import psutil
from pathlib import Path
from typing import Set, Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class ResourceManager:
    """Manages temporary files, memory usage, and cleanup"""

    def __init__(self, max_temp_files: int = 100, max_temp_size_mb: int = 1000):
        self.temp_files: Set[str] = set()
        self.temp_directories: Set[str] = set()
        self.max_temp_files = max_temp_files
        self.max_temp_size_mb = max_temp_size_mb
        self._cleanup_task: Optional[asyncio.Task] = None

    def create_temp_file(self, suffix: str = "", prefix: str = "rag_") -> str:
        """Create a temporary file and track it for cleanup"""
        try:
            fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
            os.close(fd)  # Close the file descriptor, keep the path

            self.temp_files.add(temp_path)
            self._check_temp_limits()

            logger.debug(f"Created temporary file: {temp_path}")
            return temp_path

        except Exception as e:
            logger.error(f"Failed to create temporary file: {e}")
            raise

    def create_temp_directory(self, prefix: str = "rag_") -> str:
        """Create a temporary directory and track it for cleanup"""
        try:
            temp_dir = tempfile.mkdtemp(prefix=prefix)
            self.temp_directories.add(temp_dir)

            logger.debug(f"Created temporary directory: {temp_dir}")
            return temp_dir

        except Exception as e:
            logger.error(f"Failed to create temporary directory: {e}")
            raise

    def cleanup_file(self, file_path: str) -> bool:
        """Clean up a specific temporary file"""
        try:
            if file_path in self.temp_files:
                if os.path.exists(file_path):
                    os.unlink(file_path)
                    logger.debug(f"Cleaned up temporary file: {file_path}")

                self.temp_files.discard(file_path)
                return True

        except Exception as e:
            logger.warning(f"Failed to cleanup file {file_path}: {e}")

        return False

    def cleanup_directory(self, dir_path: str) -> bool:
        """Clean up a specific temporary directory"""
        try:
            if dir_path in self.temp_directories:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
                    logger.debug(f"Cleaned up temporary directory: {dir_path}")

                self.temp_directories.discard(dir_path)
                return True

        except Exception as e:
            logger.warning(f"Failed to cleanup directory {dir_path}: {e}")

        return False

    def cleanup_all(self) -> None:
        """Clean up all tracked temporary files and directories"""
        cleaned_files = 0
        cleaned_dirs = 0

        # Clean up files
        for file_path in list(self.temp_files):
            if self.cleanup_file(file_path):
                cleaned_files += 1

        # Clean up directories
        for dir_path in list(self.temp_directories):
            if self.cleanup_directory(dir_path):
                cleaned_dirs += 1

        logger.info(f"Cleaned up {cleaned_files} files and {cleaned_dirs} directories")

    def _check_temp_limits(self) -> None:
        """Check if temporary file limits are exceeded"""
        if len(self.temp_files) > self.max_temp_files:
            logger.warning(f"Temporary file limit exceeded: {len(self.temp_files)}")
            self._cleanup_oldest_files()

        total_size_mb = self._get_total_temp_size() / (1024 * 1024)
        if total_size_mb > self.max_temp_size_mb:
            logger.warning(f"Temporary storage limit exceeded: {total_size_mb:.1f}MB")
            self._cleanup_oldest_files()

    def _get_total_temp_size(self) -> int:
        """Get total size of tracked temporary files in bytes"""
        total_size = 0
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    total_size += os.path.getsize(file_path)
            except Exception:
                continue
        return total_size

    def _cleanup_oldest_files(self) -> None:
        """Clean up oldest temporary files to free space"""
        files_with_time = []

        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    mtime = os.path.getmtime(file_path)
                    files_with_time.append((mtime, file_path))
            except Exception:
                continue

        # Sort by modification time (oldest first)
        files_with_time.sort()

        # Clean up oldest 25% of files
        cleanup_count = max(1, len(files_with_time) // 4)
        for _, file_path in files_with_time[:cleanup_count]:
            self.cleanup_file(file_path)

    @asynccontextmanager
    async def temp_file_context(self, suffix: str = "", prefix: str = "rag_"):
        """Context manager for temporary files with automatic cleanup"""
        temp_path = self.create_temp_file(suffix=suffix, prefix=prefix)
        try:
            yield temp_path
        finally:
            self.cleanup_file(temp_path)

    @asynccontextmanager
    async def temp_directory_context(self, prefix: str = "rag_"):
        """Context manager for temporary directories with automatic cleanup"""
        temp_dir = self.create_temp_directory(prefix=prefix)
        try:
            yield temp_dir
        finally:
            self.cleanup_directory(temp_dir)

    def get_memory_usage(self) -> dict:
        """Get current memory usage statistics"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()

            return {
                "rss_mb": memory_info.rss / (1024 * 1024),  # Resident memory
                "vms_mb": memory_info.vms / (1024 * 1024),  # Virtual memory
                "percent": process.memory_percent(),
                "temp_files_count": len(self.temp_files),
                "temp_dirs_count": len(self.temp_directories),
                "temp_size_mb": self._get_total_temp_size() / (1024 * 1024)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory usage: {e}")
            return {}

    def start_periodic_cleanup(self, interval_minutes: int = 30) -> None:
        """Start periodic cleanup task"""
        if self._cleanup_task and not self._cleanup_task.done():
            return

        async def periodic_cleanup():
            while True:
                try:
                    await asyncio.sleep(interval_minutes * 60)
                    self._cleanup_oldest_files()

                    # Log memory usage
                    memory_stats = self.get_memory_usage()
                    if memory_stats:
                        logger.info(f"Memory usage: {memory_stats}")

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in periodic cleanup: {e}")

        self._cleanup_task = asyncio.create_task(periodic_cleanup())
        logger.info(f"Started periodic cleanup task (interval: {interval_minutes} minutes)")

    def stop_periodic_cleanup(self) -> None:
        """Stop periodic cleanup task"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            logger.info("Stopped periodic cleanup task")

    def __del__(self):
        """Cleanup on destruction"""
        try:
            self.cleanup_all()
            self.stop_periodic_cleanup()
        except Exception:
            pass  # Ignore errors during destruction


# Global resource manager instance
resource_manager = ResourceManager()