SET CLIENT_ENCODING = 'UTF8';
SET CHECK_FUNCTION_BODIES = FALSE;
SET CLIENT_MIN_MESSAGES = WARNING;

CREATE TABLE BOUNCE (
    DATE	      TIMESTAMP WITH TIME ZONE	NOT NULL,
    USER_ID	      TEXT			NOT NULL,	
    GROUP_ID	      TEXT			NOT NULL,
    SITE_ID	      TEXT			NOT NULL,	
    EMAIL	      TEXT			NOT NULL	
);

CREATE TABLE POST_TAG (
	POST_ID			  TEXT                     NOT NULL REFERENCES POST (POST_ID),
	TAG				  TEXT					   NOT NULL
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
