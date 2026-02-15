import time


class ProgressWidget:
    @staticmethod
    def get_bar_html(
        history,
        remaining_count,
        avg_time,
        start_time,
        config,
        deck_averages=None,
        counts=None,
        bias=1.0,
    ):

        position = config.get("position", "top")
        color_mode = config.get("color_mode", "dynamic")

        # Mapping for type-aware opacity
        type_mapping = {0: "new", 1: "learn", 2: "review", 3: "learn"}

        # Calculate totals for initial render
        elapsed_time = time.time() - start_time
        est_remaining_time = remaining_count * avg_time
        total_est_time = elapsed_time + est_remaining_time

        def format_time(seconds):
            h, rem = divmod(int(seconds), 3600)
            m, s = divmod(rem, 60)
            if h > 0:
                return f"{h}:{m:02d}:{s:02d}"
            return f"{m}:{s:02d}"

        css = f"""
        <style>
            #anki-timer-bar {{
                display: flex !important;
                width: 100% !important;
                height: 20px !important;
                background-color: transparent !important;
                position: fixed !important;
                {position}: 0 !important;
                left: 0 !important;
                z-index: 9999 !important;
                font-family: sans-serif !important;
                font-size: 12px !important;
                line-height: 20px !important;
                color: {config.get("text_color", "#333")} !important;
                border-{"bottom" if position == "top" else "top"}: 1px solid rgba(0,0,0,0.1) !important;
                box-sizing: border-box !important;
            }}
            .block {{
                height: 100% !important;
                box-sizing: border-box !important;
                border-right: 1px solid rgba(255,255,255,0.2) !important;
            }}
            .block.correct {{ background-color: {config.get("correct_color", "#4CAF50")} !important; }}
            .block.incorrect {{ background-color: {config.get("incorrect_color", "#F44336")} !important; }}
            .block.ghost {{ 
                background-color: transparent !important; 
            }}
            .block.ghost-new {{ background-color: {config.get("ghost_new_color", "#0066FF")} !important; opacity: 0.15 !important; }}
            .block.ghost-learn {{ background-color: {config.get("ghost_learn_color", "#FF0000")} !important; opacity: 0.15 !important; }}
            .block.ghost-review {{ background-color: {config.get("ghost_review_color", "#009900")} !important; opacity: 0.15 !important; }}
            .overlay-text {{
                position: absolute !important;
                top: 0 !important;
                left: 0 !important;
                width: 100% !important;
                text-align: center !important;
                pointer-events: none !important;
                font-weight: bold !important;
                text-shadow: 0 0 2px {config.get("text_shadow_color", "#f7f7f7")} !important;
            }}
        </style>
        """

        blocks_html = ""

        # Render History Blocks
        for item in history:
            # Determine which average to use for opacity
            target_avg = avg_time  # Fallback to blended session/hist average
            if deck_averages and "type" in item:
                t_str = type_mapping.get(item["type"], "review")
                target_avg = deck_averages.get(t_str, avg_time)

            # Opacity Logic
            if color_mode == "simple":
                opacity = 1.0
            else:
                ratio = item["time"] / target_avg
                if ratio <= 0.5:
                    opacity = 1.0
                elif ratio >= 1.5:
                    opacity = 0.3
                else:
                    opacity = 1.0 + (-0.7 * (ratio - 0.5))

                opacity = max(0.3, min(1.0, opacity))

            cls = item["result"]
            flex = item["time"]
            blocks_html += f"<div class='block {cls}' style='flex-grow: {flex}; opacity: {opacity};'></div>"

        if remaining_count > 0:
            if counts:
                # Individual ghost blocks for each type
                for t, count in counts.items():
                    if count > 0:
                        avg_t = (
                            deck_averages.get(t, avg_time)
                            if deck_averages
                            else avg_time
                        )
                        flex = count * avg_t * bias
                        blocks_html += f"<div class='block ghost-{t}' style='flex-grow: {flex};' title='{t.capitalize()}: {count}'></div>"
            else:
                total_ghost_flex = remaining_count * avg_time
                blocks_html += f"<div class='block ghost' style='flex-grow: {total_ghost_flex};'></div>"

        initial_labels = f"Time: {format_time(elapsed_time)} | Rem: {format_time(est_remaining_time)} | Tot: {format_time(total_est_time)}"

        html = f"""
        {css}
        <div id='anki-timer-bar'>
            {blocks_html}
            <div class='overlay-text'>{initial_labels}</div>
        </div>
        """
        return html

    @staticmethod
    def get_timer_js(start_time, avg_time, remaining_count, counts=None):
        return f"""
            (function() {{
                const startTimestamp = {start_time};
                const avgTime = {avg_time};
                const remainingCount = {remaining_count};
                const textElement = document.querySelector('.overlay-text');
                
                function fmt(seconds) {{
                    const h = Math.floor(seconds / 3600);
                    const m = Math.floor((seconds % 3600) / 60);
                    const s = Math.floor(seconds % 60);
                    if (h > 0) return h + ":" + String(m).padStart(2, '0') + ":" + String(s).padStart(2, '0');
                    return m + ":" + String(s).padStart(2, '0');
                }}

                function update() {{
                    const now = Date.now() / 1000;
                    const elapsed = now - startTimestamp;
                    const remaining = remainingCount * avgTime;
                    const total = elapsed + remaining;
                    if (textElement) {{
                        textElement.innerText = "Time: " + fmt(elapsed) + " | Rem: " + fmt(remaining) + " | Tot: " + fmt(total);
                    }}
                }}
                
                if (window.ankiTimerInterval) clearInterval(window.ankiTimerInterval);
                window.ankiTimerInterval = setInterval(update, 1000);
                // No immediate update here to avoid jitter if initial render was close
            }})();
        """
