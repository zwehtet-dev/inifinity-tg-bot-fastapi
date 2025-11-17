"""
State manager service for conversation state management.
"""

import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta

from app.models.user_state import UserState
from app.models.conversation import ConversationState
from app.logging_config import get_logger


logger = get_logger(__name__)


class StateManager:
    """
    Manages user conversation states in memory.

    This service provides methods to get, set, update, and clear user states.
    It also includes a background task for cleaning up stale states.
    """

    def __init__(self, state_timeout_minutes: int = 30):
        """
        Initialize the state manager.

        Args:
            state_timeout_minutes: Minutes of inactivity before state is considered stale
        """
        self._states: Dict[int, UserState] = {}
        self._state_timeout = timedelta(minutes=state_timeout_minutes)
        self._cleanup_task: Optional[asyncio.Task] = None
        logger.info(
            "StateManager initialized",
            extra={"state_timeout_minutes": state_timeout_minutes},
        )

    def get_state(self, user_id: int) -> Optional[UserState]:
        """
        Get the current state for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            UserState if exists, None otherwise
        """
        state = self._states.get(user_id)

        if state:
            logger.debug(
                "Retrieved user state",
                extra={"user_id": user_id, "current_state": state.current_state.value},
            )

        return state

    def get_state_by_chat_id(self, chat_id: int) -> Optional[UserState]:
        """
        Get the current state for a user by chat ID.

        Args:
            chat_id: Telegram chat ID

        Returns:
            UserState if exists, None otherwise
        """
        for user_id, state in self._states.items():
            if state.chat_id == chat_id:
                logger.debug(
                    "Retrieved user state by chat_id",
                    extra={
                        "chat_id": chat_id,
                        "user_id": user_id,
                        "current_state": state.current_state.value,
                    },
                )
                return state

        return None

    def set_state(self, user_id: int, state: UserState):
        """
        Set the state for a user.

        Args:
            user_id: Telegram user ID
            state: UserState to set
        """
        state.update_timestamp()
        self._states[user_id] = state

        logger.info(
            "User state set",
            extra={
                "user_id": user_id,
                "current_state": state.current_state.value,
                "chat_id": state.chat_id,
            },
        )

    def update_state(
        self, user_id: int, new_state: Optional[ConversationState] = None, **kwargs
    ) -> Optional[UserState]:
        """
        Update an existing user state.

        Args:
            user_id: Telegram user ID
            new_state: New conversation state (optional)
            **kwargs: Additional fields to update on the UserState or OrderData

        Returns:
            Updated UserState if exists, None otherwise
        """
        state = self._states.get(user_id)

        if not state:
            logger.warning(
                "Attempted to update non-existent state", extra={"user_id": user_id}
            )
            return None

        # Update conversation state if provided
        if new_state:
            old_state = state.current_state
            state.current_state = new_state
            logger.info(
                "Conversation state updated",
                extra={
                    "user_id": user_id,
                    "old_state": old_state.value,
                    "new_state": new_state.value,
                },
            )

        # Update other fields
        for key, value in kwargs.items():
            # Check if it's an order_data field
            if hasattr(state.order_data, key):
                setattr(state.order_data, key, value)
                logger.debug(
                    "Order data updated", extra={"user_id": user_id, "field": key}
                )
            # Check if it's a state field
            elif hasattr(state, key):
                setattr(state, key, value)
                logger.debug(
                    "User state field updated", extra={"user_id": user_id, "field": key}
                )
            else:
                logger.warning(
                    "Attempted to update unknown field",
                    extra={"user_id": user_id, "field": key},
                )

        # Update timestamp
        state.update_timestamp()

        return state

    def clear_state(self, user_id: int) -> bool:
        """
        Clear the state for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            True if state was cleared, False if no state existed
        """
        if user_id in self._states:
            del self._states[user_id]
            logger.info("User state cleared", extra={"user_id": user_id})
            return True

        logger.debug("No state to clear", extra={"user_id": user_id})
        return False

    def get_all_states(self) -> Dict[int, UserState]:
        """
        Get all user states (for debugging/monitoring).

        Returns:
            Dictionary of all user states
        """
        return self._states.copy()

    def get_state_count(self) -> int:
        """
        Get the count of active states.

        Returns:
            Number of active user states
        """
        return len(self._states)

    async def cleanup_stale_states(self):
        """
        Background task to clean up stale states.
        Runs periodically to remove states that haven't been updated recently.
        """
        logger.info("Starting state cleanup background task")

        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes

                now = datetime.utcnow()
                stale_user_ids = []

                for user_id, state in self._states.items():
                    # Check if state is stale
                    time_since_update = now - state.last_updated

                    if time_since_update > self._state_timeout:
                        stale_user_ids.append(user_id)

                # Remove stale states
                for user_id in stale_user_ids:
                    del self._states[user_id]
                    logger.info("Removed stale state", extra={"user_id": user_id})

                if stale_user_ids:
                    logger.info(
                        "State cleanup completed",
                        extra={
                            "removed_count": len(stale_user_ids),
                            "remaining_count": len(self._states),
                        },
                    )

            except asyncio.CancelledError:
                logger.info("State cleanup task cancelled")
                break
            except Exception as e:
                logger.error(
                    "Error in state cleanup task",
                    extra={"error": str(e)},
                    exc_info=True,
                )

    def start_cleanup_task(self):
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self.cleanup_stale_states())
            logger.info("State cleanup task started")

    def stop_cleanup_task(self):
        """Stop the background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            logger.info("State cleanup task stopped")


# Global state manager instance
_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """
    Get the global state manager instance.
    Creates the instance on first call.

    Returns:
        StateManager instance
    """
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager
