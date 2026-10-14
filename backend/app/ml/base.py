from abc import ABC, abstractmethod
from typing import Callable
from app.schemas.contracts import AnalysisResult
from .schemas import ProviderRequest, Capabilities, ProviderHealth

ProgressCallback = Callable[[str, float], None]


class SpeechAnalysisProvider(ABC):
    @abstractmethod
    def get_capabilities(self) -> Capabilities: ...
    @abstractmethod
    def analyze(
        self,
        request: ProviderRequest,
        progress_callback: ProgressCallback | None = None,
    ) -> AnalysisResult: ...
    @abstractmethod
    def health_check(self) -> ProviderHealth: ...
