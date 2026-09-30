from abc import ABC, abstractmethod
from backend.core.models import UserInput, Intent


class BaseIntentRouter(ABC):
    """
    Abstract Base Class for Intent Routing.
    Takes a UserInput and determines the appropriate Intent without
    containing tool execution details.
    """

    @abstractmethod
    def route(self, user_input: UserInput) -> Intent:
        """Classifies the user input and returns an Intent."""
        pass
