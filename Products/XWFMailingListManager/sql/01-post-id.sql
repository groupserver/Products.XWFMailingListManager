SET CLIENT_ENCODING = 'UTF8';
SET CHECK_FUNCTION_BODIES = FALSE;
SET CLIENT_MIN_MESSAGES = WARNING;

-- A mapping from old post ID style to new post ID. this table is
-- really only needed for backwards compatibility of GS earlier
-- than 1.0
CREATE TABLE post_id_map (
    old_post_id  TEXT  NOT NULL,
    new_post_id  TEXT  NOT NULL REFERENCES post(post_id)
);

CREATE UNIQUE INDEX old_post_id_pkey 
    ON post_id_map 
    USING BTREE (old_post_id);
