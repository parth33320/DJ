import re
import time
import logging
from typing import Dict, Callable, Optional
from streaming.request_cooldown_manager import RequestCooldownManager

logging.basicConfig(level=logging.INFO, format='[ChatListener] %(asctime)s - %(message)s')

class ChatRequestListener:
    """
    Zero-friction live chat keyword listener for YouTube/Restream messages.
    Watches for plain text "play [Song Name]" or search term requests.
    """
    def __init__(self, config: Dict, queue_worker=None, chat_sender_callback: Optional[Callable[[str], None]] = None):
        self.config = config
        self.queue_worker = queue_worker
        self.chat_sender = chat_sender_callback or (lambda msg: logging.info(f"💬 [Chat Response]: {msg}"))
        self.cooldown_manager = RequestCooldownManager(config)

        # Regex pattern matching "play [song query]" or "!play [song query]"
        self.play_pattern = re.compile(r'^(?:!|\b)?play\b\s+(.+)', re.IGNORECASE)

    def parse_and_process_message(self, user_name: str, message_text: str) -> Optional[Dict]:
        """
        Parses incoming message text for song request keywords.
        Checks 2-hour cooldown and queues valid requests.
        """
        text = message_text.strip()
        match = self.play_pattern.search(text)

        query = None
        if match:
            query = match.group(1).strip()
        elif text.lower().startswith('req ') or text.lower().startswith('song '):
            query = text.split(' ', 1)[1].strip()

        if not query:
            return None

        logging.info(f"🔍 Received song request from {user_name}: '{query}'")

        success, response_msg, metadata = self.cooldown_manager.search_and_validate_request(query)

        # Send automatic feedback to chat
        self.chat_sender(f"@{user_name} {response_msg}")

        if success and metadata:
            if self.queue_worker:
                self.queue_worker.inject_request(metadata)
            return metadata

        return None
