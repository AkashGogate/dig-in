-- TEMPLATE ONLY: no live dashboard has been created or tested.
-- Every tile must display run_id and SIMULATED/REAL label. Never combine runs.
-- Replace :run_id with a bound dashboard parameter; don't concatenate user SQL.
SELECT run_id, simulated, COUNT(*) AS orders,
  COUNT(submit_to_ack_s) AS submit_ack_observed,
  COUNT(*)-COUNT(submit_to_ack_s) AS submit_ack_missing,
  median(submit_to_ack_s) AS median_submit_ack_s,
  COUNT(first_start_to_all_ready_s) AS cooking_observed,
  COUNT(*)-COUNT(first_start_to_all_ready_s) AS cooking_missing,
  median(first_start_to_all_ready_s) AS median_first_start_all_ready_s,
  COUNT(all_ready_to_all_pickup_s) AS pickup_observed,
  COUNT(*)-COUNT(all_ready_to_all_pickup_s) AS pickup_missing,
  median(all_ready_to_all_pickup_s) AS median_all_ready_all_pickup_s
FROM main.dig_in.order_timeline WHERE run_id=:run_id GROUP BY run_id,simulated;

SELECT run_id,simulated,COUNT(*) AS dish_units,COUNT(ready_to_pickup_s) AS observed,
  COUNT(*)-COUNT(ready_to_pickup_s) AS missing_or_censored,
  median(ready_to_pickup_s) AS median_ready_to_pickup_s
FROM main.dig_in.dish_timeline WHERE run_id=:run_id GROUP BY run_id,simulated;

SELECT run_id,simulated,COUNT(*) AS voice_submitted_orders,
  SUM(CAST(get_json_object(payload,'$.corrected_draft_lines') AS BIGINT)) AS corrected_lines,
  SUM(CAST(get_json_object(payload,'$.initial_voice_draft_line_count') AS BIGINT)) AS initial_voice_lines,
  SUM(CAST(get_json_object(payload,'$.corrected_draft_lines') AS DOUBLE)) /
    NULLIF(SUM(CAST(get_json_object(payload,'$.initial_voice_draft_line_count') AS DOUBLE)),0) AS corrections_per_initial_voice_line
FROM main.dig_in.events
WHERE run_id=:run_id AND outcome='accepted' AND type='order.submitted'
  AND get_json_object(payload,'$.capture_mode') IN ('mock_voice','live_voice')
GROUP BY run_id,simulated;

-- Ordinary mandatory Confirm and optional Delivered taps are NOT eligible.
-- Null automation availability reports manual use, not proof of sensor failure.
SELECT run_id,simulated,COUNT(*) AS eligible_actions,
  COUNT_IF(source='tap') AS tap_actions,
  COUNT_IF(source='tap')/CAST(COUNT(*) AS DOUBLE) AS manual_action_share,
  COUNT_IF(get_json_object(payload,'$.automation_available') IS NOT NULL) AS known_availability_actions,
  COUNT_IF(source='tap' AND get_json_object(payload,'$.automation_available')='false') AS known_unavailable_taps,
  COUNT_IF(source='tap' AND get_json_object(payload,'$.automation_available')='false') /
    NULLIF(CAST(COUNT_IF(get_json_object(payload,'$.automation_available') IS NOT NULL) AS DOUBLE),0) AS known_unavailable_tap_share,
  COUNT_IF(source='tap' AND get_json_object(payload,'$.automation_available') IS NULL) AS unknown_availability_taps
FROM main.dig_in.events
WHERE run_id=:run_id AND outcome='accepted'
  AND type IN ('order.acknowledged','dish.started','dish.ready','dish.picked_up')
GROUP BY run_id,simulated;

SELECT run_id,simulated,COUNT(*) AS waiting_orders,
  COUNT(zone_wait_s) AS wait_completed,COUNT(*)-COUNT(zone_wait_s) AS still_waiting_or_invalid,
  median(zone_wait_s) AS median_zone_wait_s
FROM main.dig_in.order_timeline WHERE run_id=:run_id AND zones_waiting_at IS NOT NULL
GROUP BY run_id,simulated;

SELECT run_id,simulated,
  COUNT_IF(type='zone.unexpected') AS unexpected_zone_events,
  COUNT_IF(type='camera.status' AND get_json_object(payload,'$.status')='blocked') AS blocked_status_events,
  COUNT_IF(type='camera.status' AND get_json_object(payload,'$.status')='offline') AS offline_status_events
FROM main.dig_in.events WHERE run_id=:run_id GROUP BY run_id,simulated;
-- Counts are event counts, not camera outage duration. A future outage-duration
-- tile needs device-scoped status intervals and censoring for no recovery event.
-- Inventory comparison intentionally omitted until stable ingredient sensing and
-- reconciled movements exist. Recipe expectations must not double-deduct stock.
