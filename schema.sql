-- Mock WMS schema (PostgreSQL / AlloyDB)
DROP TABLE IF EXISTS olpns CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS tasks CASCADE;
DROP TABLE IF EXISTS shipments CASCADE;
DROP TABLE IF EXISTS users CASCADE;

CREATE TABLE users (
    user_id         SERIAL PRIMARY KEY,
    user_name       VARCHAR(100) NOT NULL,
    role            VARCHAR(50)  NOT NULL DEFAULT 'picker',
    site_id         VARCHAR(20)  NOT NULL DEFAULT 'SITE01',
    is_active_shift BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE TABLE shipments (
    shipment_id     VARCHAR(20) PRIMARY KEY,
    carrier         VARCHAR(50) NOT NULL,
    ship_type       VARCHAR(10) NOT NULL,
    dock_door       VARCHAR(10),
    status          VARCHAR(20) NOT NULL DEFAULT 'open',
    site_id         VARCHAR(20) NOT NULL DEFAULT 'SITE01',
    created_at      TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE TABLE tasks (
    task_id         VARCHAR(20) PRIMARY KEY,
    shipment_id     VARCHAR(20) NOT NULL REFERENCES shipments(shipment_id),
    user_id         INTEGER REFERENCES users(user_id),
    task_type       VARCHAR(20) NOT NULL DEFAULT 'pick',
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    assigned_at     TIMESTAMP,
    completed_at    TIMESTAMP,
    created_at      TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE TABLE olpns (
    olpn_id         VARCHAR(20) PRIMARY KEY,
    shipment_id     VARCHAR(20) NOT NULL REFERENCES shipments(shipment_id),
    task_id         VARCHAR(20) REFERENCES tasks(task_id),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE TABLE orders (
    order_id        VARCHAR(20) PRIMARY KEY,
    shipment_id     VARCHAR(20) NOT NULL REFERENCES shipments(shipment_id),
    status          VARCHAR(20) NOT NULL DEFAULT 'not_waved',
    created_at      TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tasks_shipment  ON tasks(shipment_id);
CREATE INDEX idx_tasks_user      ON tasks(user_id);
CREATE INDEX idx_tasks_status    ON tasks(status);
CREATE INDEX idx_olpns_shipment  ON olpns(shipment_id);
CREATE INDEX idx_olpns_status    ON olpns(status);
CREATE INDEX idx_orders_shipment ON orders(shipment_id);
CREATE INDEX idx_orders_status   ON orders(status);
