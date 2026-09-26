# Cost-Aware Model Router

The cost-aware router selects the cheapest **verified** model path that remains
inside explicit capability, quality, risk, and total-cost constraints.

It reuses the same provenance-backed recent-performance trust calculation as the
unified model router. A candidate without enough recent verified evidence is not
treated as a cheap trusted path.

Projected total cost is:

`generation cost + independent-verification reserve`

This prevents a superficially cheap model from winning when it predictably needs
an expensive verification path.

For provider models with known local price tables, generation cost is estimated
from projected input/output tokens. OpenAI-compatible or local workers with an
unknown price must provide an explicit generation-cost override; unknown cost is
never silently treated as zero.

Selection order is deterministic:

1. required capabilities must match;
2. recent provenance-backed trust must exist;
3. trust must meet the quality floor;
4. projected risk (`1 - trust`) must remain inside the risk ceiling;
5. total projected generation + verification cost must fit the route budget;
6. among eligible candidates, choose lowest total cost, then higher trust, then
   configured priority.

This module only selects a route. Provider execution, spend enforcement, and
independent output verification remain in the existing governed model gateway,
cost governor, and verifier layers.
