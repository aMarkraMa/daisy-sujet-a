CREATE TABLE sessions(
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL CHECK (btrim(title) != ''),
    starts_at timestamptz NOT NULL,
    duration_minutes integer NOT NULL CHECK (duration_minutes > 0),
    capacity integer NOT NULL CHECK (capacity >= 0),
    booked_seats integer NOT NULL DEFAULT 0 CHECK (booked_seats >= 0),
    sales_state text NOT NULL DEFAULT 'open'
        CHECK (sales_state IN ('open', 'paused', 'cancelled'))
);

CREATE TABLE partner_sessions(
    session_id uuid NOT NULL REFERENCES sessions(id),
    partner_id text NOT NULL CHECK (btrim(partner_id) != ''),
    partner_session_id text NOT NULL CHECK (btrim(partner_session_id) != ''),
    observed_capacity integer CHECK (observed_capacity >= 0),
    observed_booked integer CHECK (observed_booked >= 0),
    observed_status text,
    observed_at timestamptz,
    last_pushed_at timestamptz,

    PRIMARY KEY (session_id, partner_id),
    UNIQUE(partner_id, partner_session_id)
);

CREATE TABLE reservations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES sessions(id),
    source text NOT NULL CHECK (btrim(source) != ''),
    source_ref text NOT NULL CHECK (btrim(source_ref) != ''),
    quantity integer NOT NULL CHECK (quantity > 0),
    status text NOT NULL CHECK (status IN ('confirmed', 'cancelled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(source, source_ref)
);

CREATE TABLE webhook_events(
    partner_id text NOT NULL CHECK (btrim(partner_id) != ''),
    event_id text NOT NULL CHECK (btrim(event_id) != ''),
    event_type text NOT NULL,
    occurred_at timestamptz NOT NULL,
    payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processed', 'blocked')),
    recieved_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz,
    PRIMARY KEY (partner_id, event_id),
    CHECK ((status = 'processed') = (processed_at IS NOT NULL))
);

CREATE TABLE outbox_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id uuid NOT NULL,
    partner_id text NOT NULL,
    partner_session_id text NOT NULL,
        status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processed', 'blocked')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz,
    FOREIGN KEY (session_id, partner_id) REFERENCES partner_sessions(session_id, partner_id),
    CHECK ((status = 'processed') = (processed_at IS NOT NULL))
);
