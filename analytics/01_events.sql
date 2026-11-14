-- TEMPLATE ONLY: Databricks SQL, not executed in a live workspace.
-- Replace main.dig_in with the reviewed catalog/schema. Payload stays JSON text.
CREATE SCHEMA IF NOT EXISTS main.dig_in;
CREATE TABLE IF NOT EXISTS main.dig_in.events (
  schema_version INT NOT NULL,
  event_id STRING NOT NULL,
  order_id STRING,
  dish_id STRING,
  type STRING NOT NULL,
  source STRING NOT NULL,
  actor STRING NOT NULL,
  time TIMESTAMP NOT NULL COMMENT 'Original source timestamp, never ingestion time',
  received_at TIMESTAMP NOT NULL COMMENT 'Core receipt time',
  run_id STRING,
  simulated BOOLEAN NOT NULL,
  outcome STRING NOT NULL COMMENT 'accepted transition or observed evidence',
  payload STRING NOT NULL COMMENT 'JSON; raw captures excluded'
) USING DELTA;

-- An adapter uploads a reviewed, parameterized staging batch with this schema.
-- Detect conflicting IDs before MERGE; do not silently rewrite source timestamps.
-- Delta does not enforce a primary key. A single designated writer and batch
-- deduplication are required here; concurrent writers need stronger coordination.
SELECT event_id, COUNT(DISTINCT to_json(struct(
  schema_version, order_id, dish_id, type, source, actor, time, received_at,
  run_id, simulated, outcome, payload))) AS distinct_versions
FROM main.dig_in.events_staging
GROUP BY event_id
HAVING distinct_versions > 1;

-- Abort the ingestion batch if conflicting identity rows above or a conflict
-- against events exists; the application outbox retains its original rows.
MERGE INTO main.dig_in.events AS target
USING (
  SELECT * EXCEPT (row_number)
  FROM (
    SELECT *, row_number() OVER (PARTITION BY event_id ORDER BY received_at) AS row_number
    FROM main.dig_in.events_staging
  ) WHERE row_number = 1
) AS incoming
ON target.event_id = incoming.event_id
WHEN NOT MATCHED THEN INSERT *;
