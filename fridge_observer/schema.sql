-- Food items currently in inventory
CREATE TABLE IF NOT EXISTS food_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL CHECK(category IN ('fruits','vegetables','dairy','beverages','meat','packaged_goods')),
    quantity    INTEGER NOT NULL DEFAULT 1,
    expiry_date TEXT,           -- ISO 8601 date, NULL if unknown
    expiry_source TEXT NOT NULL DEFAULT 'estimated' CHECK(expiry_source IN ('estimated','manual')),
    added_at    TEXT NOT NULL DEFAULT (datetime('now')),
    thumbnail   TEXT,           -- relative path to JPEG thumbnail
    notes       TEXT
);

-- Timestamped activity log
CREATE TABLE IF NOT EXISTS activity_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id     INTEGER,        -- NULL if item was deleted
    item_name   TEXT NOT NULL,
    action      TEXT NOT NULL CHECK(action IN ('added','removed','updated','expired')),
    source      TEXT NOT NULL CHECK(source IN ('automatic','manual')),
    occurred_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Temperature readings
CREATE TABLE IF NOT EXISTS temperature_readings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    compartment   TEXT NOT NULL CHECK(compartment IN ('fridge','freezer')),
    value_celsius REAL NOT NULL,
    recorded_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Recipes (seeded from a bundled JSON file)
CREATE TABLE IF NOT EXISTS recipes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    description     TEXT,
    cuisine         TEXT,
    dietary_tags    TEXT,       -- JSON array: ["vegetarian","gluten-free",...]
    prep_minutes    INTEGER,
    instructions    TEXT NOT NULL,
    image_url       TEXT
);

-- Recipe ingredients (many-to-many with food categories/names)
CREATE TABLE IF NOT EXISTS recipe_ingredients (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id   INTEGER NOT NULL REFERENCES recipes(id),
    name        TEXT NOT NULL,
    category    TEXT,
    is_pantry_staple INTEGER NOT NULL DEFAULT 0  -- 1 = always assumed available
);

-- User-favorited recipes
CREATE TABLE IF NOT EXISTS recipe_favorites (
    recipe_id   INTEGER PRIMARY KEY REFERENCES recipes(id),
    saved_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Shopping list retry queue
CREATE TABLE IF NOT EXISTS shopping_queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name   TEXT NOT NULL,
    queued_at   TEXT NOT NULL DEFAULT (datetime('now')),
    attempts    INTEGER NOT NULL DEFAULT 0
);

-- System configuration (key-value)
CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);
