"""Base class for step executors."""
from abc import ABC, abstractmethod


class BaseExecutor(ABC):
    @abstractmethod
    async def execute(self, config: dict, variables: dict) -> str:
        """Execute the step and return output string.

        Args:
            config: Step configuration dict (type-specific fields).
            variables: Accumulated variables from previous steps.

        Returns:
            Output string to be stored as the step's output_var value.
        """
        pass
