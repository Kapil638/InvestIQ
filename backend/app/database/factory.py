"""Factory for database clients and repositories."""

from app.core.config import Settings
from app.database.pgvector_store import PgVectorStore
from app.database.repositories.memory_repository import InMemoryReportRepository
from app.database.repositories.supabase_repository import SupabaseReportRepository
from app.database.repositories.user_memory_repository import InMemoryUserRepository
from app.database.repositories.user_supabase_repository import SupabaseUserRepository
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


def create_user_repository(settings: Settings):
    """Build the owner-user/WebAuthn-credential repository.

    IMPORTANT: when this returns an InMemoryUserRepository, callers MUST cache
    and reuse the single instance (e.g. on app.state at startup, like
    report_storage) rather than calling this per-request — a fresh in-memory
    repo per call would silently lose all owner/credential data immediately.
    """
    if settings.uses_supabase:
        logger.info("Using Supabase user repository")
        return SupabaseUserRepository(
            url=settings.supabase_url,
            key=settings.supabase_anon_key,
        )

    logger.info("Supabase not configured – using in-memory user repository")
    return InMemoryUserRepository()


def create_vector_store(settings: Settings) -> PgVectorStore | None:
    if not settings.rag_enabled or not settings.uses_supabase:
        return None

    logger.info("pgvector RAG store enabled (Supabase)")
    return PgVectorStore(
        url=settings.supabase_url,
        key=settings.supabase_anon_key,
    )
