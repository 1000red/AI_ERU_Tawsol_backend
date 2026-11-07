CREATE TABLE public.announcement_reads (
    id integer NOT NULL,
    user_id integer NOT NULL,
    announcement_id integer NOT NULL,
    read_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE public.announcement_reads_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.announcement_reads_id_seq OWNED BY public.announcement_reads.id;

CREATE TABLE public.announcement_target_users (
    id integer NOT NULL,
    announcement_id integer NOT NULL,
    user_id integer NOT NULL
);

CREATE SEQUENCE public.announcement_target_users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.announcement_target_users_id_seq OWNED BY public.announcement_target_users.id;

CREATE TABLE public.announcements (
    announcement_id integer NOT NULL,
    author_id integer NOT NULL,
    title character varying(200) NOT NULL,
    content text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone,
    material_id integer NOT NULL
);

CREATE SEQUENCE public.announcements_announcement_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.announcements_announcement_id_seq OWNED BY public.announcements.announcement_id;

CREATE TABLE public.app_notifications (
    id integer NOT NULL,
    user_id integer NOT NULL,
    title character varying(200) NOT NULL,
    body text,
    notif_type character varying(30) NOT NULL,
    ref_id integer,
    is_read boolean NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE public.app_notifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.app_notifications_id_seq OWNED BY public.app_notifications.id;

CREATE TABLE public.assignment_submissions (
    submission_id integer NOT NULL,
    assignment_id integer NOT NULL,
    student_id integer NOT NULL,
    file_path character varying(500),
    link_url character varying(500),
    file_type character varying(20),
    submitted_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone,
    description text,
    title character varying(200)
);

CREATE SEQUENCE public.assignment_submissions_submission_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.assignment_submissions_submission_id_seq OWNED BY public.assignment_submissions.submission_id;

CREATE TABLE public.assignments (
    assignment_id integer NOT NULL,
    material_id integer NOT NULL,
    author_id integer NOT NULL,
    title character varying(200) NOT NULL,
    description text,
    file_type character varying(20),
    file_path character varying(500),
    link_url character varying(500),
    deadline timestamp without time zone NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone
);

CREATE SEQUENCE public.assignments_assignment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.assignments_assignment_id_seq OWNED BY public.assignments.assignment_id;

CREATE TABLE public.chat_history (
    chat_id integer NOT NULL,
    sender_id integer NOT NULL,
    receiver_id integer NOT NULL,
    message text NOT NULL,
    sent_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE public.chat_history_chat_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.chat_history_chat_id_seq OWNED BY public.chat_history.chat_id;

CREATE TABLE public.complaints (
    complaint_id integer NOT NULL,
    material_id integer NOT NULL,
    student_id integer NOT NULL,
    teacher_id integer NOT NULL,
    complaint_text text NOT NULL,
    send_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE public.complaints_complaint_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.complaints_complaint_id_seq OWNED BY public.complaints.complaint_id;

CREATE TABLE public.device_tokens (
    id integer NOT NULL,
    user_id integer NOT NULL,
    token character varying(512) NOT NULL,
    platform character varying(10),
    active boolean,
    created_at timestamp without time zone DEFAULT now()
);

CREATE SEQUENCE public.device_tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.device_tokens_id_seq OWNED BY public.device_tokens.id;

CREATE TABLE public.material (
    material_id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    duration integer
);

CREATE TABLE public.material_files (
    file_id integer NOT NULL,
    material_id integer NOT NULL,
    author_id integer NOT NULL,
    title character varying(200) NOT NULL,
    description text,
    file_type character varying(20) NOT NULL,
    file_path character varying(500),
    link_url character varying(500),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone
);

CREATE SEQUENCE public.material_files_file_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.material_files_file_id_seq OWNED BY public.material_files.file_id;

CREATE TABLE public.material_student (
    id integer NOT NULL,
    material_id integer NOT NULL,
    user_id integer NOT NULL
);

CREATE SEQUENCE public.material_student_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.material_student_id_seq OWNED BY public.material_student.id;

CREATE TABLE public.material_teacher (
    id integer NOT NULL,
    material_id integer NOT NULL,
    user_id integer NOT NULL
);

CREATE SEQUENCE public.material_teacher_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.material_teacher_id_seq OWNED BY public.material_teacher.id;

CREATE TABLE public.pinned_conversations (
    id integer NOT NULL,
    user_id integer NOT NULL,
    partner_id integer NOT NULL,
    pinned_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE public.pinned_conversations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.pinned_conversations_id_seq OWNED BY public.pinned_conversations.id;

CREATE TABLE public.user_type (
    code character varying(5) NOT NULL,
    description character varying(50) NOT NULL
);

CREATE TABLE public.users (
    user_id integer NOT NULL,
    uni_code character varying(20) NOT NULL,
    name character varying(100) NOT NULL,
    email character varying(100) NOT NULL,
    password character varying(255) NOT NULL,
    level integer,
    department character varying(100),
    type_code character varying(5) NOT NULL,
    must_change_password boolean NOT NULL,
    profile_picture character varying(255),
    total_hours integer DEFAULT 0
);

CREATE SEQUENCE public.users_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.users_user_id_seq OWNED BY public.users.user_id;

ALTER TABLE ONLY public.announcement_reads ALTER COLUMN id SET DEFAULT nextval('public.announcement_reads_id_seq'::regclass);

ALTER TABLE ONLY public.announcement_target_users ALTER COLUMN id SET DEFAULT nextval('public.announcement_target_users_id_seq'::regclass);

ALTER TABLE ONLY public.announcements ALTER COLUMN announcement_id SET DEFAULT nextval('public.announcements_announcement_id_seq'::regclass);

ALTER TABLE ONLY public.app_notifications ALTER COLUMN id SET DEFAULT nextval('public.app_notifications_id_seq'::regclass);

ALTER TABLE ONLY public.assignment_submissions ALTER COLUMN submission_id SET DEFAULT nextval('public.assignment_submissions_submission_id_seq'::regclass);

ALTER TABLE ONLY public.assignments ALTER COLUMN assignment_id SET DEFAULT nextval('public.assignments_assignment_id_seq'::regclass);

ALTER TABLE ONLY public.chat_history ALTER COLUMN chat_id SET DEFAULT nextval('public.chat_history_chat_id_seq'::regclass);

ALTER TABLE ONLY public.complaints ALTER COLUMN complaint_id SET DEFAULT nextval('public.complaints_complaint_id_seq'::regclass);

ALTER TABLE ONLY public.device_tokens ALTER COLUMN id SET DEFAULT nextval('public.device_tokens_id_seq'::regclass);

ALTER TABLE ONLY public.material_files ALTER COLUMN file_id SET DEFAULT nextval('public.material_files_file_id_seq'::regclass);

ALTER TABLE ONLY public.material_student ALTER COLUMN id SET DEFAULT nextval('public.material_student_id_seq'::regclass);

ALTER TABLE ONLY public.material_teacher ALTER COLUMN id SET DEFAULT nextval('public.material_teacher_id_seq'::regclass);

ALTER TABLE ONLY public.pinned_conversations ALTER COLUMN id SET DEFAULT nextval('public.pinned_conversations_id_seq'::regclass);

ALTER TABLE ONLY public.users ALTER COLUMN user_id SET DEFAULT nextval('public.users_user_id_seq'::regclass);

ALTER TABLE ONLY public.announcement_reads
    ADD CONSTRAINT announcement_reads_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.announcement_target_users
    ADD CONSTRAINT announcement_target_users_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT announcements_pkey PRIMARY KEY (announcement_id);

ALTER TABLE ONLY public.app_notifications
    ADD CONSTRAINT app_notifications_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.assignment_submissions
    ADD CONSTRAINT assignment_submissions_pkey PRIMARY KEY (submission_id);

ALTER TABLE ONLY public.assignments
    ADD CONSTRAINT assignments_pkey PRIMARY KEY (assignment_id);

ALTER TABLE ONLY public.chat_history
    ADD CONSTRAINT chat_history_pkey PRIMARY KEY (chat_id);

ALTER TABLE ONLY public.complaints
    ADD CONSTRAINT complaints_pkey PRIMARY KEY (complaint_id);

ALTER TABLE ONLY public.device_tokens
    ADD CONSTRAINT device_tokens_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.device_tokens
    ADD CONSTRAINT device_tokens_token_key UNIQUE (token);

ALTER TABLE ONLY public.material_files
    ADD CONSTRAINT material_files_pkey PRIMARY KEY (file_id);

ALTER TABLE ONLY public.material
    ADD CONSTRAINT material_pkey PRIMARY KEY (material_id);

ALTER TABLE ONLY public.material_student
    ADD CONSTRAINT material_student_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.material_teacher
    ADD CONSTRAINT material_teacher_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.pinned_conversations
    ADD CONSTRAINT pinned_conversations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.announcement_target_users
    ADD CONSTRAINT uq_ann_target_user UNIQUE (announcement_id, user_id);

ALTER TABLE ONLY public.announcement_reads
    ADD CONSTRAINT uq_announcement_reads_user_ann UNIQUE (user_id, announcement_id);

ALTER TABLE ONLY public.pinned_conversations
    ADD CONSTRAINT uq_pinned_user_partner UNIQUE (user_id, partner_id);

ALTER TABLE ONLY public.user_type
    ADD CONSTRAINT user_type_pkey PRIMARY KEY (code);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_uni_code_key UNIQUE (uni_code);

CREATE INDEX ix_announcements_announcement_id ON public.announcements USING btree (announcement_id);

CREATE INDEX ix_app_notifications_id ON public.app_notifications USING btree (id);

CREATE INDEX ix_assignment_submissions_submission_id ON public.assignment_submissions USING btree (submission_id);

CREATE INDEX ix_assignments_assignment_id ON public.assignments USING btree (assignment_id);

CREATE INDEX ix_chat_history_chat_id ON public.chat_history USING btree (chat_id);

CREATE INDEX ix_complaints_complaint_id ON public.complaints USING btree (complaint_id);

CREATE INDEX ix_device_tokens_id ON public.device_tokens USING btree (id);

CREATE INDEX ix_material_files_file_id ON public.material_files USING btree (file_id);

CREATE INDEX ix_material_material_id ON public.material USING btree (material_id);

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);

CREATE INDEX ix_users_user_id ON public.users USING btree (user_id);

ALTER TABLE ONLY public.announcement_reads
    ADD CONSTRAINT announcement_reads_announcement_id_fkey FOREIGN KEY (announcement_id) REFERENCES public.announcements(announcement_id);

ALTER TABLE ONLY public.announcement_reads
    ADD CONSTRAINT announcement_reads_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);

ALTER TABLE ONLY public.announcement_target_users
    ADD CONSTRAINT announcement_target_users_announcement_id_fkey FOREIGN KEY (announcement_id) REFERENCES public.announcements(announcement_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.announcement_target_users
    ADD CONSTRAINT announcement_target_users_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT announcements_author_id_fkey FOREIGN KEY (author_id) REFERENCES public.users(user_id);

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT announcements_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.material(material_id);

ALTER TABLE ONLY public.app_notifications
    ADD CONSTRAINT app_notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.assignment_submissions
    ADD CONSTRAINT assignment_submissions_assignment_id_fkey FOREIGN KEY (assignment_id) REFERENCES public.assignments(assignment_id);

ALTER TABLE ONLY public.assignment_submissions
    ADD CONSTRAINT assignment_submissions_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.users(user_id);

ALTER TABLE ONLY public.assignments
    ADD CONSTRAINT assignments_author_id_fkey FOREIGN KEY (author_id) REFERENCES public.users(user_id);

ALTER TABLE ONLY public.assignments
    ADD CONSTRAINT assignments_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.material(material_id);

ALTER TABLE ONLY public.chat_history
    ADD CONSTRAINT chat_history_receiver_id_fkey FOREIGN KEY (receiver_id) REFERENCES public.users(user_id);

ALTER TABLE ONLY public.chat_history
    ADD CONSTRAINT chat_history_sender_id_fkey FOREIGN KEY (sender_id) REFERENCES public.users(user_id);

ALTER TABLE ONLY public.complaints
    ADD CONSTRAINT complaints_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.material(material_id);

ALTER TABLE ONLY public.complaints
    ADD CONSTRAINT complaints_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.users(user_id);

ALTER TABLE ONLY public.complaints
    ADD CONSTRAINT complaints_teacher_id_fkey FOREIGN KEY (teacher_id) REFERENCES public.users(user_id);

ALTER TABLE ONLY public.device_tokens
    ADD CONSTRAINT device_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);

ALTER TABLE ONLY public.material_files
    ADD CONSTRAINT material_files_author_id_fkey FOREIGN KEY (author_id) REFERENCES public.users(user_id);

ALTER TABLE ONLY public.material_files
    ADD CONSTRAINT material_files_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.material(material_id);

ALTER TABLE ONLY public.material_student
    ADD CONSTRAINT material_student_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.material(material_id);

ALTER TABLE ONLY public.material_student
    ADD CONSTRAINT material_student_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);

ALTER TABLE ONLY public.material_teacher
    ADD CONSTRAINT material_teacher_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.material(material_id);

ALTER TABLE ONLY public.material_teacher
    ADD CONSTRAINT material_teacher_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);

ALTER TABLE ONLY public.pinned_conversations
    ADD CONSTRAINT pinned_conversations_partner_id_fkey FOREIGN KEY (partner_id) REFERENCES public.users(user_id);

ALTER TABLE ONLY public.pinned_conversations
    ADD CONSTRAINT pinned_conversations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_type_code_fkey FOREIGN KEY (type_code) REFERENCES public.user_type(code);

CREATE SEQUENCE public.blacklisted_tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE public.blacklisted_tokens (
    id integer NOT NULL DEFAULT nextval('public.blacklisted_tokens_id_seq'::regclass),
    jti character varying(36) NOT NULL,
    expires_at timestamp with time zone NOT NULL
);

ALTER SEQUENCE public.blacklisted_tokens_id_seq OWNED BY public.blacklisted_tokens.id;

ALTER TABLE ONLY public.blacklisted_tokens
    ADD CONSTRAINT blacklisted_tokens_pkey PRIMARY KEY (id);

CREATE UNIQUE INDEX ix_blacklisted_tokens_jti ON public.blacklisted_tokens USING btree (jti);
