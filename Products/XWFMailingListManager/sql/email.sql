SET CLIENT_ENCODING = 'UTF8';
SET CHECK_FUNCTION_BODIES = FALSE;
SET CLIENT_MIN_MESSAGES = WARNING;

CREATE TABLE BOUNCE (
    DATE              TIMESTAMP WITH TIME ZONE  NOT NULL,
    USER_ID           TEXT                      NOT NULL,       
    GROUP_ID          TEXT                      NOT NULL,
    SITE_ID           TEXT                      NOT NULL,       
    EMAIL             TEXT                      NOT NULL        
);

CREATE TABLE POST_TAG (
        POST_ID                   TEXT                     NOT NULL REFERENCES POST (POST_ID),
        TAG                               TEXT                                     NOT NULL
);

CREATE TABLE group_digest (
    site_id text not null,
    group_id text not null,
    sent_date timestamp with time zone not null
);

CREATE TABLE FILE (
    FILE_ID           TEXT                     NOT NULL,
    MIME_TYPE         TEXT                     NOT NULL,
    FILE_NAME         TEXT                     NOT NULL,
    FILE_SIZE         INTEGER                  NOT NULL,
    DATE              TIMESTAMP WITH TIME ZONE NOT NULL,
    POST_ID           TEXT                     NOT NULL REFERENCES POST (POST_ID),
    TOPIC_ID          TEXT                     NOT NULL REFERENCES TOPIC (TOPIC_ID)
);

-- A MAPPING FROM OLD POST ID STYLE TO NEW POST ID. THIS TABLE IS REALLY ONLY NEEDED
-- FOR BACKWARDS COMPATIBILITY OF GS EARLIER THAN 1.0
CREATE TABLE POST_ID_MAP (
    OLD_POST_ID           TEXT                                          NOT NULL,
    NEW_POST_ID       TEXT                                              NOT NULL REFERENCES POST (POST_ID)
);

CREATE UNIQUE INDEX OLD_POST_ID_PKEY ON POST_ID_MAP USING BTREE (OLD_POST_ID);
