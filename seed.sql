-- seed.sql: run AFTER schema.sql. Deterministic mock data for the 6 supervisor questions.
INSERT INTO users (user_name, role, is_active_shift) VALUES
 ('Ravi Kumar','picker',TRUE),('Anita Sharma','picker',TRUE),('Suresh Patel','picker',TRUE),
 ('Meena Iyer','picker',TRUE),('Arjun Reddy','picker',TRUE),('Priya Nair','picker',TRUE),
 ('Vikram Singh','picker',TRUE),('Deepa Menon','picker',TRUE),
 ('Karthik Rao','picker',TRUE),   -- id 9: on shift, no open work  -> idle
 ('Sunita Das','picker',TRUE),    -- id 10: on shift, no work at all -> idle
 ('Imran Khan','picker',FALSE),   -- id 11: not on shift
 ('Lakshmi Pillai','picker',FALSE),
 ('Rahul Verma','loader',TRUE),('Neha Gupta','loader',TRUE),('Amit Joshi','supervisor',TRUE);

INSERT INTO shipments (shipment_id, carrier, ship_type, dock_door, status) VALUES
 ('SHP10001','FedEx','PD','D01','open'),
 ('SHP10002','UPS','PD','D02','open'),
 ('SHP10003','FedEx','SPD','D03','open'),
 ('SHP10004','UPS','SPD','D04','open'),
 ('SHP10005','FedEx','PD','D05','staged');   -- fully done: good "zero results" case

-- 12 tasks per shipment (progress increases with shipment number)
INSERT INTO tasks (task_id, shipment_id, user_id, task_type, status, assigned_at, completed_at)
SELECT 'TSK' || (500000 + s_no*100 + n_no)::text,
       'SHP' || (10000 + s_no)::text,
       CASE WHEN status='pending' AND n_no % 2 = 0 THEN NULL ELSE 1 + ((s_no*3 + n_no) % 8) END,
       'pick', status,
       CASE WHEN NOT (status='pending' AND n_no % 2 = 0) THEN NOW() - INTERVAL '3 hours' END,
       CASE WHEN status='completed' THEN NOW() - make_interval(mins => n_no*10) END
FROM (
  SELECT s_no, n_no,
         CASE WHEN n_no <= s_no*2+2 THEN 'completed'
              WHEN n_no <= s_no*2+5 THEN 'in_progress'
              ELSE 'pending' END AS status
  FROM generate_series(1,5) AS s(s_no), generate_series(1,12) AS n(n_no)
) b;

-- Karthik Rao finished his only task 47 min ago -> shows up as idle with context
UPDATE tasks SET user_id = 9, completed_at = NOW() - INTERVAL '47 minutes' WHERE task_id = 'TSK500101';

-- 10 orders per shipment
INSERT INTO orders (order_id, shipment_id, status)
SELECT 'ORD' || (700000 + s_no*100 + n_no)::text,
       'SHP' || (10000 + s_no)::text,
       CASE WHEN n_no <= s_no*2 THEN 'processed'
            WHEN n_no <= s_no*2+2 THEN 'waved'
            ELSE 'not_waved' END
FROM generate_series(1,5) AS s(s_no), generate_series(1,10) AS n(n_no);

-- 3 OLPNs per task
INSERT INTO olpns (olpn_id, shipment_id, task_id, status)
SELECT 'OLPN' || (900000 + row_number() OVER (ORDER BY t.task_id, k.k_no))::text,
       t.shipment_id, t.task_id,
       CASE t.status
         WHEN 'completed'   THEN CASE WHEN sh.status='staged' OR k.k_no=1 THEN 'loaded' ELSE 'picked' END
         WHEN 'in_progress' THEN CASE WHEN k.k_no=1 THEN 'picked' ELSE 'pending' END
         ELSE 'pending' END
FROM tasks t
JOIN shipments sh ON sh.shipment_id = t.shipment_id
CROSS JOIN generate_series(1,3) AS k(k_no);

-- Read-only role for the chatbot (least privilege). Change the password outside local dev.
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='wms_reader') THEN
    CREATE ROLE wms_reader LOGIN PASSWORD 'reader_pw';
  END IF;
END $$;
GRANT SELECT ON users, shipments, tasks, olpns, orders TO wms_reader;
