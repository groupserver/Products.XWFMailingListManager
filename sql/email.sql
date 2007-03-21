SET client_encoding = 'UTF8';
SET check_function_bodies = false;
SET client_min_messages = warning;

CREATE TABLE POST (
    POST_ID           TEXT                     PRIMARY KEY,
    TOPIC_ID          TEXT                     NOT NULL,
    GROUP_ID          TEXT                     NOT NULL,
    SITE_ID           TEXT                     NOT NULL,
    USER_ID           TEXT                     NOT NULL,
    IN_REPLY_TO       TEXT                     NOT NULL DEFAULT ''::text,
    SUBJECT           TEXT                     NOT NULL DEFAULT ''::text,
    DATE              TIMESTAMP WITH TIME ZONE NOT NULL,
    BODY              TEXT                     NOT NULL DEFAULT ''::text,
    HTMLBODY          TEXT                     NOT NULL DEFAULT ''::text,
    HEADER            TEXT                     NOT NULL,
    HAS_ATTACHMENTS   BOOLEAN		           NOT NULL
);

CREATE INDEX site_group_idx ON post USING btree (site_id, group_id);
CREATE INDEX topic_idx ON post USING btree (topic_id);

CREATE TABLE POST_TAG (
	POST_ID			  TEXT                     NOT NULL REFERENCES POST (POST_ID),
	TAG				  TEXT					   NOT NULL
);

CREATE TABLE TOPIC (
    TOPIC_ID          TEXT                     PRIMARY KEY,
    GROUP_ID          TEXT                     NOT NULL,
    SITE_ID           TEXT                     NOT NULL,
    ORIGINAL_SUBJECT  TEXT                     NOT NULL,
    FIRST_POST_ID     TEXT                     NOT NULL REFERENCES POST (POST_ID),
    LAST_POST_ID      TEXT                     NOT NULL REFERENCES POST (POST_ID),
    LAST_POST_DATE    TIMESTAMP WITH TIME ZONE NOT NULL,
    NUM_POSTS         INTEGER                  NOT NULL CHECK (NUM_POSTS > 0)
);  

CREATE INDEX group_id_site_id_idx ON topic USING btree (group_id, site_id);

CREATE TABLE TOPIC_WORD_COUNT (
    TOPIC_ID          TEXT                     NOT NULL REFERENCES TOPIC (TOPIC_ID),
    WORD              TEXT                     NOT NULL,
    COUNT             INTEGER                  NOT NULL CHECK (COUNT > 0)
);

CREATE UNIQUE INDEX topic_word_pkey ON topic_word_count USING btree (topic_id, word);

CREATE TABLE FILE (
    FILE_ID           TEXT                     NOT NULL,
    MIME_TYPE         TEXT                     NOT NULL,
    FILE_NAME         TEXT                     NOT NULL,
    FILE_SIZE         INTEGER                  NOT NULL,
    DATE              TIMESTAMP WITH TIME ZONE NOT NULL,
    POST_ID           TEXT                     NOT NULL REFERENCES POST (POST_ID),
    TOPIC_ID          TEXT                     NOT NULL REFERENCES TOPIC (TOPIC_ID)
);