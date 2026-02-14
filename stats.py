import json
import os
from aqt import mw

class StatsManager:
    def __init__(self):
        self.stats_file = os.path.join(os.path.dirname(__file__), "user_files", "stats.json")
        self.data = self._load_data()
        self.session_data = {} # Fallback if no history

    def _load_data(self):
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_data(self):
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.stats_file), exist_ok=True)
        with open(self.stats_file, 'w') as f:
            json.dump(self.data, f)

    def get_avg_time(self, deck_id, card_type="review"):
        str_did = str(deck_id)
        deck_stats = self.data.get(str_did, {})
        
        # Map string type to ensure consistency
        if isinstance(card_type, int):
            # Mapping from card.type to our keys
            mapping = {0: "new", 1: "learn", 2: "review", 3: "learn"}
            card_type = mapping.get(card_type, "review")
        
        return deck_stats.get(card_type, 10.0)

    def update_average(self, deck_id, card_type, time_taken):
        str_did = str(deck_id)
        # Ensure it's a dict
        if str_did not in self.data or not isinstance(self.data[str_did], dict):
            self.data[str_did] = {"new": 10.0, "learn": 10.0, "review": 10.0}
        
        # Mapping from card.type or string
        if isinstance(card_type, int):
            mapping = {0: "new", 1: "learn", 2: "review", 3: "learn"}
            card_type = mapping.get(card_type, "review")

        current_avg = self.get_avg_time(deck_id, card_type)
        
        # Exponential smoothing
        from .config import ConfigManager
        alpha = ConfigManager.get().get("smoothing_alpha", 0.2)
        new_avg = (alpha * time_taken) + ((1 - alpha) * current_avg)
        
        self.data[str_did][card_type] = new_avg
        self._save_data()
