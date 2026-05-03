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



