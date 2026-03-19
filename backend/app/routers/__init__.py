from .auth import router as auth_router
from .templates import router as templates_router
from .tasks import router as tasks_router
from .records import router as records_router
from .media import router as media_router
from .llm import router as llm_router
from .analytics import router as analytics_router
from .enterprises import router as enterprises_router
from .knowledge import router as knowledge_router
from .ai_extract import router as ai_extract_router
from .industries import router as industries_router
from .users import router as users_router
from .agent import router as agent_router
from .ai_enhanced import router as ai_enhanced_router
from .statistics import router as statistics_router

__all__ = [
    "auth_router",
    "templates_router",
    "tasks_router",
    "records_router",
    "media_router",
    "llm_router",
    "analytics_router",
    "enterprises_router",
    "knowledge_router",
    "ai_extract_router",
    "industries_router",
    "users_router",
    "agent_router",
    "ai_enhanced_router",
    "statistics_router",
]
