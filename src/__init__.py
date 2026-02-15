from aqt import mw, gui_hooks
from aqt.utils import showInfo
import time
from .stats import StatsManager
from .ui import ProgressWidget
from . import config  # Registers menu item


# State
import os
import json

# State
class State:
    def __init__(self):
        self.session_file = os.path.join(
            os.path.dirname(__file__), "user_files", "current_sessions.json"
        )
        self.card_start_time = 0.0
        self.stats = StatsManager()
        self.sessions = {} # {str(deck_id): {"start_time": float, "history": list, "elapsed_seconds": 0.0, "last_resume_time": 0.0}}
        # Clear sessions on launch
        self._clear_persistence()

    def _clear_persistence(self):
        if os.path.exists(self.session_file):
            try:
                os.remove(self.session_file)
            except:
                pass
        self.sessions = {}

    def save_sessions(self):
        os.makedirs(os.path.dirname(self.session_file), exist_ok=True)
        with open(self.session_file, "w") as f:
            json.dump(self.sessions, f)

    def load_sessions(self):
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, "r") as f:
                    self.sessions = json.load(f)
            except:
                self.sessions = {}

    def get_session(self, deck_id):
        did = str(deck_id)
        if did not in self.sessions:
            self.sessions[did] = {
                "start_time": 0.0,
                "history": [],
                "elapsed_seconds": 0.0,
                "last_resume_time": 0.0
            }
        return self.sessions[did]

    def pause_all_sessions(self):
        now = time.time()
        changed = False
        for did, session in self.sessions.items():
            if session.get("last_resume_time", 0) > 0:
                session["elapsed_seconds"] += now - session["last_resume_time"]
                session["last_resume_time"] = 0.0
                changed = True
        if changed:
            self.save_sessions()

    def clear_deck_session(self, deck_id):
        did = str(deck_id)
        if did in self.sessions:
            self.sessions[did] = {
                "start_time": 0.0,
                "history": [],
                "elapsed_seconds": 0.0,
                "last_resume_time": 0.0
            }
            self.save_sessions()

state = State()


def on_fw_did_show_question(card):
    # Update state
    if not mw.col:
        return
        
    deck_obj = mw.col.decks.current()
    if not deck_obj:
        return
        
    state.pause_all_sessions()  # Ensure other decks are paused
    current_deck = deck_obj["id"]
    session = state.get_session(current_deck)
    now = time.time()
    
    if not session["start_time"]:
        session["start_time"] = now
        
    if session["last_resume_time"] == 0:
        session["last_resume_time"] = now
        state.save_sessions()

    state.card_start_time = now

    # Update UI (wrapped in try/except)
    update_overlay()


def on_fw_did_answer_card(reviewer, card, ease):
    if not mw.col:
        return
    deck_obj = mw.col.decks.current()
    if not deck_obj:
        return
    current_deck = deck_obj["id"]
        
    from .config import ConfigManager
    config = ConfigManager.get()

    raw_time_taken = time.time() - state.card_start_time
    # Hard cap to prevent AFK skewing
    max_time = config.get("max_time_per_card", 60)
    time_taken = min(raw_time_taken, max_time)

    # Logic for result
    is_correct = ease > 1

    session = state.get_session(current_deck)
    session["history"].append(
        {
            "result": "correct" if is_correct else "incorrect",
            "time": time_taken,
            "type": card.type,
            "ease": ease,
        }
    )
    state.save_sessions()

    # Update Stats
    state.stats.update_average(current_deck, card.type, time_taken)

    # UI update is triggered by standard Anki flow showing next question or finishing?
    # Actually we might want to update immediately to show the block?
    # But the card moves away instantly. The bar is persistent.
    # The next 'show_question' will re-render the overlay.


def on_fw_did_undo(*args):
    # Only if we are in reviewer
    if mw.state != "review" or not mw.col:
        return

    deck_obj = mw.col.decks.current()
    if not deck_obj:
        return
    current_deck = deck_obj["id"]
    
    session = state.get_session(current_deck)
    if session["history"]:
        session["history"].pop()
        state.save_sessions()
        update_overlay()


# Hooks
gui_hooks.reviewer_did_show_question.append(on_fw_did_show_question)
gui_hooks.reviewer_did_answer_card.append(on_fw_did_answer_card)
# Use state_did_undo for undo detection
if hasattr(gui_hooks, "state_did_undo"):
    gui_hooks.state_did_undo.append(on_fw_did_undo)
else:
    print("Anki Progress Bar: state_did_undo hook not found.")


def update_overlay():
    try:
        if not mw.reviewer or not mw.reviewer.web:
            return

        # Only show during review
        if mw.state != "review":
            mw.reviewer.web.eval(
                "let c = document.getElementById('anki-timer-overlay'); if(c) c.innerHTML = '';"
            )
            return

        # Calculate remaining
        counts = mw.col.sched.counts()
        new_c, learn_c, review_c = counts
        total_remaining = sum(counts)

        # Initial state data
        deck_obj = mw.col.decks.current()
        if not deck_obj:
            return
        current_deck = deck_obj["id"]
        
        session = state.get_session(current_deck)
        history = list(session["history"])
        start_time = float(session["start_time"])
        elapsed_total = float(session["elapsed_seconds"])
        last_resume = float(session["last_resume_time"])
        
        now = time.time()
        if last_resume > 0:
            elapsed_total += now - last_resume
        
        # Virtual start time for JS
        virtual_start_time = now - elapsed_total

        # Historical stats
        avg_new = state.stats.get_avg_time(current_deck, "new")
        avg_learn = state.stats.get_avg_time(current_deck, "learn")
        avg_review = state.stats.get_avg_time(current_deck, "review")
        deck_averages = {"new": avg_new, "learn": avg_learn, "review": avg_review}

        if total_remaining == 0:
            avg_time = 10.0
            historical_weighted = 10.0
        else:
            historical_weighted = (
                new_c * avg_new + learn_c * avg_learn + review_c * avg_review
            ) / total_remaining

            if history:
                session_times = [h["time"] for h in history]
                session_avg = sum(session_times) / len(session_times)
                avg_time = (session_avg * 2 + historical_weighted) / 3
            else:
                avg_time = historical_weighted
                if start_time == 0:
                    start_time = now
                    session["start_time"] = start_time
                    session["last_resume_time"] = now
                    state.save_sessions()

        # Config
        from .config import ConfigManager
        config = ConfigManager.get()

        # Calculate bias
        historical_weighted = max(0.1, historical_weighted)
        bias = avg_time / historical_weighted

        # Generate HTML & JS
        counts_dict = {"new": new_c, "learn": learn_c, "review": review_c}
        html = ProgressWidget.get_bar_html(
            history,
            total_remaining,
            avg_time,
            virtual_start_time,
            config,
            deck_averages,
            counts_dict,
            bias,
        )
        js_timer = ProgressWidget.get_timer_js(
            virtual_start_time, avg_time, total_remaining, counts_dict
        )

        import json
        html_json = json.dumps(html)
        pos = config.get("position", "top")
        
        # Simple injection without setTimeout
        js = f"""
        (function(){{
            let container = document.getElementById('anki-timer-overlay');
            let pos = "{pos}";
            if (!container) {{
                container = document.createElement('div');
                container.id = 'anki-timer-overlay';
                container.style.position = 'fixed';
                container.style.left = '0';
                container.style.width = '100%';
                container.style.zIndex = '9999';
                document.body.appendChild(container);
            }}
            container.style.top = pos === 'top' ? '0' : 'auto';
            container.style.bottom = pos === 'bottom' ? '0' : 'auto';
            container.innerHTML = {html_json};
            {js_timer}
        }})();
        """
        mw.reviewer.web.eval(js)
    except Exception as e:
        print(f"Anki Progress Bar Error: {e}")


def on_clear_session(handled, message, context):
    if message == "anki_timer_clear_session":
        current_deck = mw.col.decks.current()["id"]
        state.clear_deck_session(current_deck)
        update_overlay()
        return (True, None)
    return handled


def on_reviewer_will_end():
    # Pause session and stop the JS timer when leaving reviewer
    state.pause_all_sessions()
    if mw.reviewer.web:
        mw.reviewer.web.eval(ProgressWidget.get_stop_timer_js())


def on_state_did_change(next_state, previous_state):
    if next_state != "review":
        state.pause_all_sessions()


# New Hooks
gui_hooks.webview_did_receive_js_message.append(on_clear_session)
gui_hooks.reviewer_will_end.append(on_reviewer_will_end)
gui_hooks.state_did_change.append(on_state_did_change)


# Register callback for live config updates
from .config import ConfigManager

ConfigManager.set_callback(update_overlay)
