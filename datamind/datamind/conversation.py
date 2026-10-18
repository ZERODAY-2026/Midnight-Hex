"""Session conversation state scoped to the active dataset."""

from typing import Any, MutableMapping


def reset_dataset_conversation(state: MutableMapping[str, Any], dataset_key: str) -> None:
    """Clear queued prompts, history, and answers when the selected dataset changes."""
    if state.get("active_dataset") == dataset_key:
        return

    state["active_dataset"] = dataset_key
    state["history"] = []
    state["responses"] = []
    state.pop("prompt_input", None)
