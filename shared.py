
# Global mapping of usernames to chat IDs and their states
user_chat_mapping = {}  # username -> {"chat_id": int, "joined": bool}
poll_participants = {}  # poll_id -> set(user_id)
notified_winners_global = set()  # users who were notified as winners