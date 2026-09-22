from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
import asyncio

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=30,
    # BUG-17：远程库空闲连接可能在 1 小时内被中间链路断开；30 分钟主动回收 + 使用前探活，
    # 降低 ConnectionDoesNotExistError / asyncpg TimeoutError 的出现概率。
    # PERF：探活本身是每次 checkout 一次 SELECT 1 往返，本地连公网远程库时成本高，
    # 由 settings.db_pool_pre_ping 按「是否回环连接」自动判定（可用 DB_POOL_PRE_PING 覆盖）。
    pool_recycle=1800,
    pool_pre_ping=settings.db_pool_pre_ping,
    pool_timeout=30,
    connect_args={
        "server_settings": {
            "application_name": "efis_backend",
            "jit": "off",
        },
        "command_timeout": 60,
    }
)

_shared_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

# Event loop that the shared engine's pooled asyncpg connections belong to.
# Set lazily on first use; see :func:`_current_engine_loop`.
_BOUND_LOOP: asyncio.AbstractEventLoop | None = None

# Session factories for "foreign" event loops (one per loop), each backed by an
# isolated NullPool engine.  Empty in normal operation — a single-loop process
# (uvicorn) always resolves to the shared factory.
_ISOLATED_FACTORIES: dict[int, async_sessionmaker] = {}


def _isolated_engine():
    """Engine with ``NullPool``: connections never outlive their session."""
    return create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        connect_args={
            "server_settings": {
                "application_name": "efis_backend_isolated",
                "jit": "off",
            },
            "command_timeout": 60,
        },
    )


def _current_engine_loop() -> asyncio.AbstractEventLoop:
    """Return (and cache) the event loop the shared engine's pool belongs to.

    We cannot read this off the pool: SQLAlchemy 2.0's ``AsyncAdaptedQueuePool``
    exposes no ``_loop`` attribute, so probing it silently returned ``None`` and
    the loop guard never fired.  Instead we record the loop in use when the
    shared engine is first exercised — the loop asyncpg connections bind to.
    """
    global _BOUND_LOOP
    loop = asyncio.get_running_loop()
    if _BOUND_LOOP is None:
        _BOUND_LOOP = loop
    return _BOUND_LOOP


def _isolated_session_factory() -> async_sessionmaker:
    loop = asyncio.get_running_loop()
    factory = _ISOLATED_FACTORIES.get(id(loop))
    if factory is None:
        factory = async_sessionmaker(
            _isolated_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        _ISOLATED_FACTORIES[id(loop)] = factory
    return factory


class _LoopAwareSessionFactory:
    """Drop-in replacement for ``async_sessionmaker`` that is loop-safe.

    The module-level engine pools asyncpg connections on the loop that created
    them.  A second loop in the same process (every ``TestClient`` in a test
    run starts its own) must not reuse those connections, otherwise asyncpg
    raises ``RuntimeError: Event loop is closed`` or ``got Future attached to a
    different loop``.  Such loops get an isolated ``NullPool`` engine instead.

    Call sites keep writing ``async with AsyncSessionLocal() as db:``; the guard
    lives here so middleware, lifespan hooks, background tasks and route
    dependencies are all covered at once.
    """

    def __call__(self, **kwargs) -> AsyncSession:
        if _current_engine_loop() is asyncio.get_running_loop():
            return _shared_session_factory(**kwargs)
        return _isolated_session_factory()(**kwargs)


AsyncSessionLocal = _LoopAwareSessionFactory()


async def get_db():
    """FastAPI dependency that yields an AsyncSession bound to the current loop."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
