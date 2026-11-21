# Basket — Docker Setup (shared demo)

`deploy/docker-compose.shared-demo.yml` (Compose project `basket-shared-demo`) runs **only
the event and search infrastructure**. PostgreSQL stays on the Mac (Homebrew), and the API and
frontend run natively for speed on an 8 GB machine.

| Service | Image | Port (host) | Memory | Notes |
|---|---|---|---|---|
| kafka | `apache/kafka:3.7.0` | `127.0.0.1:9094` | heap 256–512 MB (~330 MB measured) | KRaft single node; listeners INTERNAL 19092, CONTROLLER 9093, HOST 9094; topics auto-created with 3 partitions; volume `kafka_data` |
| opensearch | `opensearchproject/opensearch:2.13.0` | `127.0.0.1:9201` | heap 512 MB (~880 MB measured) | single node, security plugin disabled (localhost-only); volume `opensearch_data` |

Both have health checks, `restart: unless-stopped`, and are bound to 127.0.0.1, so they are
never reachable from the network. Docker Desktop VM: 4 GB.

## Commands
```bash
scripts/shared-demo.sh up        # compose up --wait, create DB if missing, migrate, API, build+start web
scripts/shared-demo.sh status    # containers, processes, /ready
scripts/shared-demo.sh restart   # down + rebuild frontend + up (data kept)
scripts/shared-demo.sh tunnel    # Cloudflare quick tunnel + API restart for the tunnel origin
scripts/shared-demo.sh down      # stop tunnel, web, API, containers (data kept)
scripts/shared-demo.sh reset-db  # rebuild basket_shared_demo from the demo seed (asks first)
docker compose -f deploy/docker-compose.shared-demo.yml down -v   # remove containers AND Kafka/OpenSearch data
```

Health checks by hand:
```bash
curl -s localhost:9201/_cluster/health            # "status":"green"
docker exec basket-shared-demo-kafka-1 /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:19092 --describe --all-groups   # lag per consumer group
```

On start the API builds this database's OpenSearch index from PostgreSQL. It then keeps the
index current from Kafka; the log line is
`Search index '…' rebuilt from PostgreSQL (N products); Kafka indexing active`.
