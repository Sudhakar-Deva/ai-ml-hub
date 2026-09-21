"""The four budgets — iterations, tokens, cost, wall-clock — enforced, not declared.

`Budget.check()` runs before every model call and `Budget.charge()` after it.
Tokens are summed over EVERY lap: the loop re-sends the whole message list each
time, so the last call's usage understates the run by a multiple of the lap count.
"""
import time
from dataclasses import dataclass, field

from .. import config


class BudgetExceeded(Exception):
    def __init__(self, which: str, detail: str):
        super().__init__(f"{which}: {detail}")
        self.which = which
        self.detail = detail


def price(model: str, input_tokens: int, output_tokens: int) -> float:
    if model not in config.PRICING:
        raise SystemExit(f"no price for {model} in config.PRICING — cost per claim would be a guess")
    p_in, p_out = config.PRICING[model]
    return (input_tokens * p_in + output_tokens * p_out) / 1_000_000


@dataclass
class Budget:
    max_iters: int = config.MAX_ITERS
    max_tokens: int = config.MAX_TOKENS
    max_cost_usd: float = config.MAX_COST_USD
    wall_clock_s: float = config.WALL_CLOCK_S

    iters: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    started: float = field(default_factory=time.perf_counter)

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def elapsed(self) -> float:
        return time.perf_counter() - self.started

    def remaining_s(self) -> float:
        return self.wall_clock_s - self.elapsed()

    def check(self) -> None:
        """Before a call: would making it break a budget we can already see?"""
        if self.iters >= self.max_iters:
            raise BudgetExceeded("max_iterations", f"{self.iters} laps used of {self.max_iters}")
        if self.tokens >= self.max_tokens:
            raise BudgetExceeded("max_tokens", f"{self.tokens} tokens used of {self.max_tokens}")
        if self.cost_usd >= self.max_cost_usd:
            raise BudgetExceeded("max_cost", f"${self.cost_usd:.4f} spent of ${self.max_cost_usd:.2f}")
        if self.remaining_s() <= 0:
            raise BudgetExceeded("wall_clock", f"{self.elapsed():.1f}s elapsed of {self.wall_clock_s:.0f}s")

    def charge(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """After a call: book it, then re-check tokens, cost and time."""
        self.iters += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cost_usd += price(model, input_tokens, output_tokens)
        if self.tokens > self.max_tokens:
            raise BudgetExceeded("max_tokens", f"{self.tokens} tokens used of {self.max_tokens}")
        if self.cost_usd > self.max_cost_usd:
            raise BudgetExceeded("max_cost", f"${self.cost_usd:.4f} spent of ${self.max_cost_usd:.2f}")
        if self.remaining_s() <= 0:
            raise BudgetExceeded("wall_clock", f"{self.elapsed():.1f}s elapsed of {self.wall_clock_s:.0f}s")

    def snapshot(self) -> dict:
        return {
            "iters": self.iters,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "tokens": self.tokens,
            "cost_usd": round(self.cost_usd, 6),
            "elapsed_s": round(self.elapsed(), 2),
        }

    def limits(self) -> dict:
        return {
            "max_iters": self.max_iters,
            "max_tokens": self.max_tokens,
            "max_cost_usd": self.max_cost_usd,
            "wall_clock_s": self.wall_clock_s,
        }
