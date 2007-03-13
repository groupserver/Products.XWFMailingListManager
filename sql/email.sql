create table post (
    post_id           text                     PRIMARY KEY,
    topic_id          text                     NOT NULL,
    group_id          text                     NOT NULL,
    site_id           text                     NOT NULL,
    user_id           text                     NOT NULL,
    in_reply_to       text                     NOT NULL DEFAULT '',
    subject           text                     NOT NULL DEFAULT '',
    date              timestamp with time zone NOT NULL,
    body              text                     NOT NULL DEFAULT '',
    htmlbody          text                     NOT NULL DEFAULT '',
    header            text                     NOT NULL,
    has_attachments   boolean		       NOT NULL
);

create table topic (
    topic_id          text                     PRIMARY KEY,
    group_id          text                     NOT NULL,
    site_id           text                     NOT NULL,
    original_subject  text                     NOT NULL,
    first_post_id     text                     NOT NULL REFERENCES post (post_id),
    last_post_id      text                     NOT NULL REFERENCES post (post_id),
    last_post_date    timestamp with time zone NOT NULL,
    num_posts         integer                  NOT NULL CHECK (num_posts > 0)
);  

create table topic_word_count (
    topic_id          text                     NOT NULL REFERENCES topic (topic_id),
    word              text                     NOT NULL,
    count             integer                  NOT NULL CHECK (count > 0)
);

create table file (
    file_id           text                     NOT NULL,
    mime_type         text                     NOT NULL,
    file_name         text                     NOT NULL,
    file_size         integer                  NOT NULL,
    date              timestamp with time zone NOT NULL,
    post_id           text                     NOT NULL REFERENCES post (post_id),
    topic_id          text                     NOT NULL REFERENCES topic (topic_id)
);


    
