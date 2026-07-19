"""Factory for database clients and repositories."""

from app.core.config import Settings
from app.database.chroma_store import ChromaVectorStore
from app.database.repositories.memory_repository import InMemoryReportRepository
from app.database.repositories.supabase_repository import SupabaseReportRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


def create_report_repository(settings: Settings):
    if settings.uses_supabase:
        logger.info("Using Supabase report repository")
        return SupabaseReportRepository(
            url=settings.supabase_url,
            key=settings.supabase_anon_key,
        )

    logger.info("Supabase not configured – using in-memory report repository")
    return InMemoryReportRepository()


def create_vector_store(settings: Settings) -> ChromaVectorStore | None:
    if not settings.chroma_enabled:
        return None

    logger.info("ChromaDB vector store enabled at %s", settings.chroma_persist_directory)
    return ChromaVectorStore(
        persist_directory=settings.chroma_persist_directory,
        collection_name=settings.chroma_collection_name,
    )
