"""Betfury-style dice simulator (1% house edge).
Each strategy is a function that receives (bankroll, last_result) and returns (chance_pct, bet).
"""
import random

def play_round(chance_pct, rng):
    return rng.uniform(0, 100) < chance_pct

def simulate(name, make_strategy, bankroll=1000, max_bets=100_000, n_sessions=200, seed=42):
    rng = random.Random(seed)
    finals, busts, dds = [], 0, []
    for _ in range(n_sessions):
        bal, peak, max_dd, last = bankroll, bankroll, 0, None
        step = make_strategy(bankroll)
        busted = False
        for _ in range(max_bets):
            chance, bet = step(bal, last)
            if bet > bal: bet = bal
            if bet <= 0: busted = True; break
            bal -= bet
            last = play_round(chance, rng)
            if last:
                bal += bet * (99.0 / chance)
            peak = max(peak, bal)
            max_dd = max(max_dd, (peak - bal) / peak)
            if bal <= 0: busted = True; break
        finals.append(bal); busts += busted; dds.append(max_dd)
    finals.sort()
    return {
        "strategy": name,
        "bust_rate": f"{100*busts/n_sessions:.0f}%",
        "median_final": round(finals[len(finals)//2], 1),
        "best": round(finals[-1], 1),
        "worst": round(finals[0], 1),
        "avg_max_drawdown": f"{100*sum(dds)/len(dds):.0f}%",
        "end_in_profit": f"{100*sum(1 for f in finals if f > bankroll)/n_sessions:.0f}%",
    }

# ---- strategies ----

def flat(chance=49.5, bet_frac=0.01):
    return lambda bal, last: (chance, bal * bet_frac)

def martingale(chance=49.5, base_frac=0.002, max_steps=None):
    losses = {"n": 0}
    def step(bal, last):
        if last is None:
            losses["n"] = 0
        elif last:
            losses["n"] = 0
        else:
            losses["n"] += 1
        n = losses["n"] if max_steps is None else min(losses["n"], max_steps)
        return chance, bal * base_frac * (2 ** n)
    return step

def ladder(chance=60.0, bet_frac=0.01, up=1.5):
    mult = {"m": 1.0}
    def step(bal, last):
        if last is True: mult["m"] *= up
        elif last is False: mult["m"] = 1.0
        return chance, bal * bet_frac * mult["m"]
    return step

def tiny_flat(chance=49.5, bet_frac=0.005):
    return lambda bal, last: (chance, bal * bet_frac)

if __name__ == "__main__":
    strategies = [
        ("Flat 1% @ 49.5%", flat()),
        ("Tiny flat 0.5% @ 49.5%", tiny_flat()),
        ("Martingale uncapped @ 49.5%", martingale()),
        ("Martingale 6-step cap @ 49.5%", martingale(max_steps=6)),
        ("Ladder x1.5 on win @ 60%", ladder()),
    ]
    print(f"{'strategy':<32} {'bust':>5} {'median':>10} {'best':>10} {'worst':>9} {'avg DD':>7} {'profit':>7}")
    for view, bets in [("SESSION: 500 bets (one sitting)", 500), ("LONG RUN: 10,000 bets", 10_000)]:
        print(f"\n=== {view} ===")
        print(f"{'strategy':<32} {'bust':>5} {'median':>10} {'best':>10} {'worst':>9} {'avg DD':>7} {'profit':>7}")
        for name, s in strategies:
            r = simulate(name, lambda br, s=s: (lambda bal, last: s(bal, last)), max_bets=bets)
            print(f"{r['strategy']:<32} {r['bust_rate']:>5} {r['median_final']:>10} {r['best']:>10} {r['worst']:>9} {r['avg_max_drawdown']:>7} {r['end_in_profit']:>7}")
