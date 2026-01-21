## 2024-05-23 - Nested Async Calls in Combinatorial Logic
**Learning:** Found a nested loop O(N*M) generating flight combinations where an external API call for currency conversion was scheduled for every iteration. This resulted in hundreds of duplicate requests. The conversion rate was constant for the entire batch.
**Action:** Always check loop invariants in async tasks. If an async operation depends on parameters that don't change per iteration (like currency pair), hoist it out of the loop.
