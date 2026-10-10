# Follow-ups on the AiStackE2E PRD (2026-10-08)

PRD doc (private until shared): https://claude.ai/code/artifact/64ee7cae-5412-4e19-a472-baa9e06a424e

## Verify before external publication
- [ ] Gemma licence (sources conflict: Gemma Terms of Use vs reported Apache-2.0 for Gemma 4)
- [ ] Mem0, Letta, Supermemory licences (secondary sources conflict)
- [ ] MultiOn operating status (reported transition to AGI, Inc.)
- [ ] Manus ownership after the reported Meta unwind
- [ ] Whether Check Point's Lakera acquisition closed
- [ ] n8n licence wording (Sustainable Use License)
- [ ] Gemini 3.5 Flash pricing (aggregator only: $1.50 / $9.00 per 1M tokens)
- [ ] OpenAI caching discount for gpt-6.1-sol
- [ ] USDA FoodData Central API terms

## Decisions to challenge
- P0 = 133 engineer-weeks, 28 calendar weeks for 6 engineers; CLI-first alpha at week 16
- JEV treated as an optional `DecisionModel` port (P1); not recommended for the diabetes recipe example (~$2/month saving)
- MCP only at ecosystem boundaries; typed in-process adapters elsewhere
- Postgres-only storage at P0 (JSONB, job queue, partitioned eval tables)

## Data to replace
- Cost tables use verified list prices (claude.com/pricing and developers.openai.com pricing, 2026-10-08), but token profiles and success rates are illustrative. Replace them with real eval runs.

## Open product questions (PRD section 28)
1. Can evidence be shared across customers in anonymised form, legally?
2. Seat pricing vs value-based pricing?
3. Is Python-only acceptable to the first 10 design partners?
4. What minimum eval size will an enterprise risk officer accept for a `compatible` verdict?

## Housekeeping
- [ ] Share the PRD doc with reviewers (Share menu on the page)
