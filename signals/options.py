"""
Options trade signal generator for NSE indices (Nifty 50, Bank Nifty).
Based on the candlestick pattern detected on the index, suggests which
options contract (CE/PE) to look at and calculates approximate strike prices.

This is educational / rule-based logic — not a prediction engine.
"""
import math


# Nifty option strike gap is 50, Bank Nifty is 100
STRIKE_GAPS = {
    "^NSEI": 50,
    "^NSEBANK": 100,
}

# Index symbol to readable name mapping
INDEX_NAMES = {
    "^NSEI": "NIFTY",
    "^NSEBANK": "BANKNIFTY",
}


def round_to_strike(price, strike_gap):
    """Round a price to the nearest option strike price."""
    return int(round(price / strike_gap) * strike_gap)


def get_atm_strike(current_price, strike_gap):
    """Get the At-The-Money (ATM) strike price."""
    return round_to_strike(current_price, strike_gap)


def generate_option_signal(symbol, current_price, pattern_name, bias, score, note):
    """
    Generate an options trading signal based on the pattern detected on an index.

    Returns a dict with:
        index_name: readable name (NIFTY / BANKNIFTY)
        action: 'BUY CE' | 'BUY PE' | 'WAIT' | 'WATCH'
        option_type: 'CE' (Call) | 'PE' (Put) | None
        atm_strike: At-The-Money strike price
        suggested_strike: recommended strike to trade
        otm_strike: slightly Out-of-The-Money alternative (cheaper premium)
        stop_loss_index: index level to exit the trade
        target_index: index level target
        reason: human-readable explanation
    """
    strike_gap = STRIKE_GAPS.get(symbol, 50)
    index_name = INDEX_NAMES.get(symbol, symbol)
    atm_strike = get_atm_strike(current_price, strike_gap)

    # Neutral patterns (Doji) — always WATCH
    if bias == "neutral":
        return {
            "index_name": index_name,
            "action": "WATCH",
            "emoji": "👀",
            "option_type": None,
            "atm_strike": atm_strike,
            "suggested_strike": None,
            "otm_strike": None,
            "stop_loss_index": None,
            "target_index": None,
            "reason": f"{pattern_name} on {index_name} shows indecision. Avoid options, wait for clarity.",
        }

    # Weak signals — WAIT
    if score < 1:
        return {
            "index_name": index_name,
            "action": "WAIT",
            "emoji": "⏸️",
            "option_type": None,
            "atm_strike": atm_strike,
            "suggested_strike": None,
            "otm_strike": None,
            "stop_loss_index": None,
            "target_index": None,
            "reason": f"{pattern_name} detected on {index_name} but confirmation weak ({score}/3). Skip.",
        }

    # --- BULLISH → BUY CE (Call Option) ---
    if bias == "bullish":
        # ATM CE for moderate signals, slightly ITM for strong signals
        if score >= 2:
            suggested_strike = atm_strike  # ATM for strong signal
            otm_strike = atm_strike + strike_gap  # OTM alternative (cheaper)
        else:
            suggested_strike = atm_strike + strike_gap  # Slight OTM for moderate signal
            otm_strike = atm_strike + (2 * strike_gap)  # Further OTM

        # Index stop-loss and target
        risk_points = current_price * 0.005  # 0.5% of index as risk
        stop_loss_index = round(current_price - risk_points, 2)
        target_index = round(current_price + (risk_points * 2), 2)  # 1:2 R:R

        strength = "Strong" if score >= 2 else "Moderate"

        return {
            "index_name": index_name,
            "action": "BUY CE",
            "emoji": "📗",
            "option_type": "CE",
            "atm_strike": atm_strike,
            "suggested_strike": suggested_strike,
            "otm_strike": otm_strike,
            "stop_loss_index": stop_loss_index,
            "target_index": target_index,
            "reason": (
                f"{strength} bullish signal on {index_name}. "
                f"Consider buying {index_name} {suggested_strike} CE (or {otm_strike} CE for lower premium). "
                f"Index SL: {stop_loss_index}, Target: {target_index}. {note}"
            ),
        }

    # --- BEARISH → BUY PE (Put Option) ---
    if bias == "bearish":
        if score >= 2:
            suggested_strike = atm_strike
            otm_strike = atm_strike - strike_gap
        else:
            suggested_strike = atm_strike - strike_gap
            otm_strike = atm_strike - (2 * strike_gap)

        risk_points = current_price * 0.005
        stop_loss_index = round(current_price + risk_points, 2)
        target_index = round(current_price - (risk_points * 2), 2)

        strength = "Strong" if score >= 2 else "Moderate"

        return {
            "index_name": index_name,
            "action": "BUY PE",
            "emoji": "📕",
            "option_type": "PE",
            "atm_strike": atm_strike,
            "suggested_strike": suggested_strike,
            "otm_strike": otm_strike,
            "stop_loss_index": stop_loss_index,
            "target_index": target_index,
            "reason": (
                f"{strength} bearish signal on {index_name}. "
                f"Consider buying {index_name} {suggested_strike} PE (or {otm_strike} PE for lower premium). "
                f"Index SL: {stop_loss_index}, Target: {target_index}. {note}"
            ),
        }

    return {
        "index_name": index_name,
        "action": "WAIT",
        "emoji": "⏸️",
        "option_type": None,
        "atm_strike": atm_strike,
        "suggested_strike": None,
        "otm_strike": None,
        "stop_loss_index": None,
        "target_index": None,
        "reason": f"Unknown bias for {index_name}. Wait.",
    }
