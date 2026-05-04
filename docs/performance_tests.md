# Performance Tests — URL Lookup Benchmark

Benchmarked three datastores for URL lookup latency using `GET /api/benchmark/lookup/{short_code}`.  
Each store is queried independently and results are returned in a single response.


**Steady-state averages (excluding cold first call):**

| Store | Avg latency |
|---|---|
| Redis | ~1.8 ms |
| Postgres | ~4.1 ms |
| DynamoDB | ~231 ms |

This is due to dynamo being the only one outside of the local network. Next tests should instead use
redis/postgress inside AWS + lambda functions or EC2

---

## Round 2 — EC2 (us-east-2), all stores co-located (2026-05-03)

Endpoint: `GET /api/benchmark/lookup/{short_code}`, 20 requests, run from local machine against EC2.  
Redis and Postgres running on the same EC2 instance. DynamoDB in the same AWS region (us-east-2).

**Run 1 — cold process (per-request DynamoDB context, old code):**

| Store | Avg latency (excl. first call) |
|---|---|
| Redis | ~1.13 ms |
| Postgres | ~1.10 ms |
| DynamoDB | ~33.86 ms |

Redis and Postgres are now neck-and-neck since both are local. DynamoDB dropped from 231 ms to ~34 ms
due to same-region placement, but still paid a connection setup cost on each request.

**Run 2 — warm process (aiohttp connection reuse kicked in + VPC):**

| Store | Avg latency (excl. first call) |
|---|---|
| Redis | ~1.12 ms |
| Postgres | ~1.12 ms |
| DynamoDB | ~2.64 ms |

After the HTTP connection to DynamoDB was reused across requests, latency dropped to ~2.6 ms — within
3× of local stores. This motivated a code change: `open_dynamo_table()` now enters the aioboto3
resource context once at startup so the connection is warm from the first request.

---

## Round 3 — EC2 (us-east-2), 20 rotating keys (2026-05-03)

Endpoint: `GET /api/benchmark/lookup/{short_code}`, 60 requests rotating across 20 distinct short codes.  
Tests key diversity — verifies results aren't inflated by a single hot key in the buffer cache.

**Steady-state averages (59 calls, excl. first):**

| Store | Avg latency | Win rate |
|---|---|---|
| Redis | ~1.15 ms | ~19% |
| Postgres | ~1.04 ms | ~81% |
| DynamoDB | ~2.75 ms | 0% |

Results held stable across all 20 keys. Postgres consistently wins — its shared buffer cache fits all
20 rows trivially and asyncpg's binary protocol edges out Redis's key hashing overhead. DynamoDB
remained at ~2.7 ms per key with a persistent HTTP connection, but still paid a 19.5 ms cold-start
on the first call (persistent client fix not yet deployed).



