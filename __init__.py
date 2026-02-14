from aqt import mw, gui_hooks
from aqt.utils import showInfo
import time
from .stats import StatsManager
from .ui import ProgressWidget
from . import config  # Registers menu item


# State
class State:
    start_time = 0.0
    card_start_time = 0.0
    history = []  # List of {result, time, ease}
    stats = StatsManager()


state = State()


def on_fw_did_show_question(card):
    # Update state
    if not state.start_time:
        state.start_time = time.time()

    state.card_start_time = time.time()

    # Update UI
    update_overlay()


def on_fw_did_answer_card(reviewer, card, ease):
    from .config import ConfigManager

    config = ConfigManager.get()

    raw_time_taken = time.time() - state.card_start_time
    # Hard cap to prevent AFK skewing
    max_time = config.get("max_time_per_card", 60)
    time_taken = min(raw_time_taken, max_time)

    # Logic for result
    # Ease 1 = Again (Incorrect)
    # Ease > 1 = Correct
    is_correct = ease > 1

    state.history.append(
        {
            "result": "correct" if is_correct else "incorrect",
            "time": time_taken,
            "type": card.type,
            "ease": ease,
        }
    )

    # Update Stats
    state.stats.update_average(card.did, card.type, time_taken)

    # UI update is triggered by standard Anki flow showing next question or finishing?
    # Actually we might want to update immediately to show the block?
    # But the card moves away instantly. The bar is persistent.
    # The next 'show_question' will re-render the overlay.


def on_fw_did_undo(*args):
    # Only if we are in reviewer
    if mw.state != "review":
        return

    if state.history:
        state.history.pop()
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
    if not mw.reviewer.web:
        return

    # Only show during review
    if mw.state != "review":
        mw.reviewer.web.eval(
            "let c = document.getElementById('anki-timer-overlay'); if(c) c.innerHTML = '';"
        )
        return

    # Calculate remaining
    counts = mw.col.sched.counts()
    # counts = (new, learning, review)
    new_c, learn_c, review_c = counts
    total_remaining = sum(counts)

    if total_remaining == 0:
        # Hide or just show zero
        avg_time = 10.0
    else:
        # Current deck averages (Historical)
        current_deck = mw.col.decks.current()["id"]
        avg_new = state.stats.get_avg_time(current_deck, "new")
        avg_learn = state.stats.get_avg_time(current_deck, "learn")
        avg_review = state.stats.get_avg_time(current_deck, "review")

        historical_weighted = (
            new_c * avg_new + learn_c * avg_learn + review_c * avg_review
        ) / total_remaining

        # Session Average (Blend)
        if state.history:
            session_times = [h["time"] for h in state.history]
            session_avg = sum(session_times) / len(session_times)
            # 2x session, 1x history (as previously tweaked by user)
            avg_time = (session_avg * 2 + historical_weighted) / 3
        else:
            avg_time = historical_weighted

        deck_averages = {"new": avg_new, "learn": avg_learn, "review": avg_review}

    # Load Config
    from .config import ConfigManager

    config = ConfigManager.get()

    # Calculate bias and prepare breakdown
    counts_dict = {"new": new_c, "learn": learn_c, "review": review_c}
    bias = avg_time / historical_weighted if historical_weighted > 0 else 1.0

    # Generate HTML & JS
    html = ProgressWidget.get_bar_html(
        state.history,
        total_remaining,
        avg_time,
        state.start_time,
        config,
        deck_averages,
        counts_dict,
        bias,
    )
    js_timer = ProgressWidget.get_timer_js(
        state.start_time, avg_time, total_remaining, counts_dict
    )

    # Inject via JS
    js = f"""
    (function(){{
        let container = document.getElementById('anki-timer-overlay');
        let pos = "{config.get("position", "top")}";
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
        container.innerHTML = `{html}`;
        {js_timer}
    }})();
    """
    mw.reviewer.web.eval(js)


# Register callback for live config updates
from .config import ConfigManager

ConfigManager.set_callback(update_overlay)
