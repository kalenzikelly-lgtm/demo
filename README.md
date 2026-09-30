# Demo 🎲

Betfury-style dice simulator (1% house edge) with a casino-style live table.

## Run

```bash
python3 dice_sim.py          # batch stats for all 8 strategies
python3 dice_sim.py live     # live casino table (default: vault streak-10)
python3 dice_sim.py live 5   # live mode, strategy 5
python3 dice_sim.py live 5 500   # live mode, 500 bets
```

## Strategies

1. Flat 1% @49.5%
2. Tiny flat 0.5% @49.5%
3. Martingale uncapped
4. Martingale 6-step cap
5. **Vault streak-10** — base bet 0.1% of bankroll, roll every win forward, bank at a 10-win streak (~1 in 1024 attempts, pays ~926x base)
6. Ladder x1.5 @60%
7. D'Alembert
8. Fibonacci

Live mode shows ASCII dice, a roll track, streak counter and session stats.
