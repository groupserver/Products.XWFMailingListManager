SET CLIENT_ENCODING = 'UTF8';
SET CHECK_FUNCTION_BODIES = FALSE;
SET CLIENT_MIN_MESSAGES = WARNING;

CREATE TABLE POST (
    POST_ID           TEXT                     PRIMARY KEY,
    TOPIC_ID          TEXT                     NOT NULL,
    GROUP_ID          TEXT                     NOT NULL,
    SITE_ID           TEXT                     NOT NULL,
    USER_ID           TEXT                     NOT NULL,
    IN_REPLY_TO       TEXT                     NOT NULL DEFAULT ''::TEXT,
    SUBJECT           TEXT                     NOT NULL DEFAULT ''::TEXT,
    DATE              TIMESTAMP WITH TIME ZONE NOT NULL,
    BODY              TEXT                     NOT NULL DEFAULT ''::TEXT,
    HTMLBODY          TEXT                     NOT NULL DEFAULT ''::TEXT,
    HEADER            TEXT                     NOT NULL,
    HAS_ATTACHMENTS   BOOLEAN		           NOT NULL
);

CREATE INDEX SITE_GROUP_IDX ON POST USING BTREE (SITE_ID, GROUP_ID);
CREATE INDEX TOPIC_IDX ON POST USING BTREE (TOPIC_ID);

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

CREATE INDEX GROUP_ID_SITE_ID_IDX ON TOPIC USING BTREE (GROUP_ID, SITE_ID);

CREATE TABLE TOPIC_WORD_COUNT (
    TOPIC_ID          TEXT                     NOT NULL REFERENCES TOPIC (TOPIC_ID),
    WORD              TEXT                     NOT NULL,
    COUNT             INTEGER                  NOT NULL CHECK (COUNT > 0)
);

CREATE UNIQUE INDEX TOPIC_WORD_PKEY ON TOPIC_WORD_COUNT USING BTREE (TOPIC_ID, WORD);

CREATE TABLE word_count (
    word text NOT NULL,
    count integer NOT NULL
);

CREATE UNIQUE INDEX WORD_COUNT_PKEY ON WORD_COUNT USING BTREE (word);

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
    OLD_POST_ID		  TEXT						NOT NULL,
    NEW_POST_ID       TEXT						NOT NULL REFERENCES POST (POST_ID)
);

CREATE UNIQUE INDEX OLD_POST_ID_PKEY ON POST_ID_MAP USING BTREE (OLD_POST_ID);

CREATE TABLE rowcount (
    table_name  text NOT NULL,
    total_rows  bigint,
    PRIMARY KEY (table_name)
);

CREATE OR REPLACE FUNCTION count_rows()
RETURNS TRIGGER AS
'
   BEGIN
      IF TG_OP = ''INSERT'' THEN
         UPDATE rowcount
            SET total_rows = total_rows + 1
            WHERE table_name = TG_RELNAME;
      ELSIF TG_OP = ''DELETE'' THEN
         UPDATE rowcount
            SET total_rows = total_rows - 1
            WHERE table_name = TG_RELNAME;
      END IF;
      RETURN NULL;
   END;
' LANGUAGE plpgsql;

--
-- Initialise trigger and rowcount for the topic table
--

BEGIN;
   -- Make sure no rows can be added to topic until we have finished
   LOCK TABLE topic IN SHARE ROW EXCLUSIVE MODE;

   create TRIGGER count_topic_rows
      AFTER INSERT OR DELETE on topic
      FOR EACH ROW EXECUTE PROCEDURE count_rows();
   
   -- Initialise the row count record
   DELETE FROM rowcount WHERE table_name = 'topic';

   INSERT INTO rowcount (table_name, total_rows)
   VALUES  ('topic',  (SELECT COUNT(*) FROM topic));

COMMIT;

--
-- Initialise the trigger and rowcount for the post table
--

BEGIN;
   -- Make sure no rows can be added to post until we have finished
   LOCK TABLE post IN SHARE ROW EXCLUSIVE MODE;

   create TRIGGER count_post_rows
      AFTER INSERT OR DELETE on post
      FOR EACH ROW EXECUTE PROCEDURE count_rows();
   
   -- Initialise the row count record
   DELETE FROM rowcount WHERE table_name = 'post';

   INSERT INTO rowcount (table_name, total_rows)
   VALUES  ('post',  (SELECT COUNT(*) FROM post));

COMMIT;

--
-- Initialise the trigger and rowcount for the word_count table
--

BEGIN;
   -- Make sure no rows can be added to word_count until we have finished
   LOCK TABLE word_count IN SHARE ROW EXCLUSIVE MODE;
   
   create TRIGGER count_word_count_rows
      AFTER INSERT OR DELETE on word_count
      FOR EACH ROW EXECUTE PROCEDURE count_rows();
   
   -- Initialise the row count record
   DELETE FROM rowcount WHERE table_name = 'word_count';
   
   INSERT INTO rowcount (table_name, total_rows)
   VALUES  ('word_count',  (SELECT COUNT(*) FROM word_count));
   
COMMIT;
