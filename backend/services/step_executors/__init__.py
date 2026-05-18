from backend.services.step_executors.base import BaseExecutor
from backend.services.step_executors.llm_executor import LLMExecutor
from backend.services.step_executors.datatable_insert_executor import DataTableInsertExecutor
from backend.services.step_executors.datatable_update_executor import DataTableUpdateExecutor
from backend.services.step_executors.datatable_read_executor import DataTableReadExecutor
from backend.services.step_executors.nova_voice_executor import NovaVoiceExecutor
from backend.services.step_executors.nova_video_executor import NovaVideoExecutor
from backend.services.step_executors.fb_post_executor import FBPostExecutor
from backend.services.step_executors.fb_comment_executor import FBCommentExecutor
from backend.services.step_executors.gen_image_executor import GenImageExecutor
from backend.services.step_executors.http_download_executor import HTTPDownloadExecutor
from backend.services.step_executors.http_request_executor import HTTPRequestExecutor
from backend.services.step_executors.code_executor import CodeExecutor
from backend.services.step_executors.loop_executor import LoopExecutor

EXECUTOR_MAP: dict[str, type[BaseExecutor]] = {
    "llm": LLMExecutor,
    "datatable_insert": DataTableInsertExecutor,
    "datatable_update": DataTableUpdateExecutor,
    "datatable_read": DataTableReadExecutor,
    "nova_voice": NovaVoiceExecutor,
    "nova_video": NovaVideoExecutor,
    "fb_post": FBPostExecutor,
    "fb_comment": FBCommentExecutor,
    "gen_image": GenImageExecutor,
    "http_download": HTTPDownloadExecutor,
    "http_request": HTTPRequestExecutor,
    "code": CodeExecutor,
    "loop": LoopExecutor,
}

# Types that need a DB session injected
DB_EXECUTOR_TYPES = {
    "llm", "datatable_insert", "datatable_update", "datatable_read",
    "nova_voice", "nova_video", "fb_post", "fb_comment",
    "gen_image", "http_request", "loop",
}

__all__ = ["BaseExecutor", "EXECUTOR_MAP", "DB_EXECUTOR_TYPES"]
