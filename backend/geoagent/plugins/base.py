from abc import ABC, abstractmethod


class AnalysisPlugin(ABC):
    """Plugin SDK v1. All paths/artifacts are managed by the host workspace."""
    id: str
    name: str
    contract_version = 1

    @abstractmethod
    def status(self) -> dict:
        """Real runtime health and advertised operation names, never a static claim."""

    @abstractmethod
    def algorithms(self) -> list[dict]:
        """Discoverable parameter contracts, using plugin-qualified algorithm IDs."""

    @abstractmethod
    def execute(self, store, algorithm_id: str, arguments: dict, run_id: str, cancel):
        """Return published layers, files and/or scalar results with provenance."""

    def render(self, store, layout, fmt, dpi, layers):
        raise ValueError(f'{self.id} does not provide cartography.')

    def execute_code(self, store, code, inputs, run_id, cancel, timeout=60):
        raise ValueError(f'{self.id} does not provide a code runtime.')
