-- TEMPLATE ONLY; always filter by run_id and simulated in dashboard controls.
-- A source observation is never promoted into an accepted dish transition here.
CREATE OR REPLACE VIEW main.dig_in.order_timeline AS
WITH timestamps AS (
  SELECT run_id, simulated, order_id,
    MIN(CASE WHEN type='order.submitted' THEN time END) AS submitted_at,
    MIN(CASE WHEN type='order.acknowledged' THEN time END) AS acknowledged_at,
    MIN(CASE WHEN type='zones.waiting' THEN time END) AS zones_waiting_at,
    MIN(CASE WHEN type='zones.assigned' THEN time END) AS zones_assigned_at,
    MIN(CASE WHEN type='dish.started' THEN time END) AS first_started_at,
    MIN(CASE WHEN type='order.ready' THEN time END) AS all_ready_at,
    MIN(CASE WHEN type='order.picked_up' THEN time END) AS all_picked_up_at,
    MIN(CASE WHEN type='order.delivered' THEN time END) AS delivered_at
  FROM main.dig_in.events
  WHERE outcome='accepted' AND order_id IS NOT NULL
  GROUP BY run_id, simulated, order_id
)
SELECT *,
  CASE WHEN acknowledged_at >= submitted_at THEN timestampdiff(MILLISECOND, submitted_at, acknowledged_at)/1000.0 END AS submit_to_ack_s,
  CASE WHEN first_started_at >= acknowledged_at THEN timestampdiff(MILLISECOND, acknowledged_at, first_started_at)/1000.0 END AS ack_to_first_start_s,
  CASE WHEN all_ready_at >= first_started_at THEN timestampdiff(MILLISECOND, first_started_at, all_ready_at)/1000.0 END AS first_start_to_all_ready_s,
  CASE WHEN all_picked_up_at >= all_ready_at THEN timestampdiff(MILLISECOND, all_ready_at, all_picked_up_at)/1000.0 END AS all_ready_to_all_pickup_s,
  CASE WHEN zones_assigned_at >= zones_waiting_at THEN timestampdiff(MILLISECOND, zones_waiting_at, zones_assigned_at)/1000.0 END AS zone_wait_s,
  delivered_at IS NULL AS delivery_censored
FROM timestamps;

CREATE OR REPLACE VIEW main.dig_in.dish_timeline AS
WITH declared_dishes AS (
  SELECT run_id, simulated, order_id, dish.dish_id AS dish_id
  FROM main.dig_in.events,
    LATERAL explode(from_json(get_json_object(payload, '$.dishes'), 'ARRAY<STRUCT<dish_id:STRING,menu_id:STRING,name:STRING>>')) AS t(dish)
  WHERE type='order.submitted' AND outcome='accepted'
), actual_dishes AS (
  SELECT DISTINCT run_id, simulated, order_id, dish_id
  FROM main.dig_in.events WHERE dish_id IS NOT NULL AND outcome='accepted'
), dishes AS (
  SELECT * FROM declared_dishes UNION SELECT * FROM actual_dishes
), timestamps AS (
  SELECT d.run_id, d.simulated, d.order_id, d.dish_id,
    MIN(CASE WHEN e.type='dish.started' THEN e.time END) AS started_at,
    MIN(CASE WHEN e.type='dish.ready' THEN e.time END) AS ready_at,
    MIN(CASE WHEN e.type='dish.picked_up' THEN e.time END) AS picked_up_at
  FROM dishes d LEFT JOIN main.dig_in.events e
    ON d.dish_id=e.dish_id AND d.order_id=e.order_id
       AND d.run_id <=> e.run_id AND d.simulated=e.simulated AND e.outcome='accepted'
  GROUP BY d.run_id,d.simulated,d.order_id,d.dish_id
)
SELECT *,
  CASE WHEN ready_at >= started_at THEN timestampdiff(MILLISECOND,started_at,ready_at)/1000.0 END AS started_to_ready_s,
  CASE WHEN picked_up_at >= ready_at THEN timestampdiff(MILLISECOND,ready_at,picked_up_at)/1000.0 END AS ready_to_pickup_s,
  ready_at IS NULL AS ready_censored,
  picked_up_at IS NULL AS pickup_censored,
  (ready_at < started_at OR picked_up_at < ready_at) AS invalid_chronology
FROM timestamps;
