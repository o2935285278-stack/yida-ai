from __future__ import annotations

from collections import deque

from yida_ai.core.models import CaptionEvent, ConversationTurn, ReplySuggestion, new_id


class ConversationManager:
    def __init__(self, context_turns: int = 15) -> None:
        self._turns: deque[ConversationTurn] = deque(maxlen=context_turns)
        self.context_turns = context_turns
        self.session_id = new_id("session")
        self.generation = 0
        self.paused = False

    @property
    def turns(self) -> tuple[ConversationTurn, ...]:
        return tuple(self._turns)

    @property
    def events(self) -> tuple[CaptionEvent, ...]:
        return tuple(turn.event for turn in self._turns)

    def add_event(self, event: CaptionEvent) -> ConversationTurn:
        turn = ConversationTurn(event=event)
        self._turns.append(turn)
        return turn

    def restore(self, turns: list[tuple[CaptionEvent, ReplySuggestion | None]]) -> None:
        """Restore only the bounded set supplied by HistoryStore."""
        for event, suggestion in turns[-self.context_turns :]:
            turn = self.add_event(event)
            turn.suggestion = suggestion

    def attach_suggestion(self, event_id: str, suggestion: ReplySuggestion) -> bool:
        for turn in self._turns:
            if turn.event.event_id == event_id:
                turn.suggestion = suggestion
                return True
        return False

    def set_context_turns(self, value: int) -> None:
        if not 1 <= value <= 50:
            raise ValueError("context_turns must be between 1 and 50")
        existing = list(self._turns)[-value:]
        self._turns = deque(existing, maxlen=value)
        self.context_turns = value

    def clear(self) -> None:
        self._turns.clear()
        self.session_id = new_id("session")
        self.generation += 1

    def new_session(self) -> None:
        self.clear()

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        return self.paused
