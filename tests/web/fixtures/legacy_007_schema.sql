-- Schema of a database at revision 007 produced by the pre-squash migration chain:
-- `create_all` of the web models at 942d32d^ (what API startup created before
-- revision 001 existed), then revisions 001-007 as of 3a8abcc, on PostgreSQL 17.
-- Generated with `pg_dump --schema-only --no-owner --no-privileges`; session SET
-- lines and comments removed. Do not regenerate from the current baseline: this
-- file is the independent evidence that baseline 007 equals the old chain.
CREATE TYPE public.pipelinestatus AS ENUM (
    'success',
    'failed',
    'interrupted'
);

CREATE TYPE public.submissionstatus AS ENUM (
    'pending',
    'processing',
    'completed',
    'failed'
);

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);

CREATE TABLE public.grading_attempts (
    id character varying(36) NOT NULL,
    submission_id integer NOT NULL,
    number integer NOT NULL,
    status character varying(20) NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone
);

CREATE TABLE public.grading_configurations (
    id integer NOT NULL,
    external_assignment_id character varying(255) NOT NULL,
    version integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    is_active boolean NOT NULL,
    definition json,
    definition_hash character varying(64),
    migration_error json
);

CREATE SEQUENCE public.grading_configurations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.grading_configurations_id_seq OWNED BY public.grading_configurations.id;

CREATE TABLE public.operation_receipts (
    id integer NOT NULL,
    principal character varying(80) NOT NULL,
    operation character varying(40) NOT NULL,
    idempotency_key character varying(255) NOT NULL,
    fingerprint character varying(64) NOT NULL,
    submission_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE public.operation_receipts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.operation_receipts_id_seq OWNED BY public.operation_receipts.id;

CREATE TABLE public.submission_results (
    id integer NOT NULL,
    submission_id integer NOT NULL,
    final_score double precision,
    result_tree json,
    feedback text,
    pipeline_execution json,
    execution_time_ms integer NOT NULL,
    pipeline_status public.pipelinestatus NOT NULL,
    error_message text,
    failed_at_step text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    focus json,
    score_vector json,
    comparison json,
    outcome json,
    diagnostics json
);

CREATE SEQUENCE public.submission_results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.submission_results_id_seq OWNED BY public.submission_results.id;

CREATE TABLE public.submissions (
    id integer NOT NULL,
    grading_config_id integer NOT NULL,
    external_user_id character varying(255) NOT NULL,
    username character varying(255) NOT NULL,
    submission_files json NOT NULL,
    language character varying(50),
    status public.submissionstatus NOT NULL,
    submitted_at timestamp without time zone DEFAULT now() NOT NULL,
    graded_at timestamp without time zone,
    submission_metadata json,
    definition_snapshot json,
    definition_hash character varying(64),
    configuration_version integer,
    locale character varying(32) DEFAULT 'en'::character varying NOT NULL,
    evaluation_scope json,
    attempt_id character varying(36),
    attempt_count integer DEFAULT 0 NOT NULL,
    lease_until timestamp with time zone
);

CREATE SEQUENCE public.submissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.submissions_id_seq OWNED BY public.submissions.id;

ALTER TABLE ONLY public.grading_configurations ALTER COLUMN id SET DEFAULT nextval('public.grading_configurations_id_seq'::regclass);

ALTER TABLE ONLY public.operation_receipts ALTER COLUMN id SET DEFAULT nextval('public.operation_receipts_id_seq'::regclass);

ALTER TABLE ONLY public.submission_results ALTER COLUMN id SET DEFAULT nextval('public.submission_results_id_seq'::regclass);

ALTER TABLE ONLY public.submissions ALTER COLUMN id SET DEFAULT nextval('public.submissions_id_seq'::regclass);

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);

ALTER TABLE ONLY public.grading_attempts
    ADD CONSTRAINT grading_attempts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.grading_configurations
    ADD CONSTRAINT grading_configurations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.operation_receipts
    ADD CONSTRAINT operation_receipts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.submission_results
    ADD CONSTRAINT submission_results_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.submissions
    ADD CONSTRAINT submissions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.operation_receipts
    ADD CONSTRAINT uq_operation_receipts_principal_operation_key UNIQUE (principal, operation, idempotency_key);

CREATE INDEX ix_grading_attempts_submission_id ON public.grading_attempts USING btree (submission_id);

CREATE UNIQUE INDEX ix_grading_configurations_external_assignment_id ON public.grading_configurations USING btree (external_assignment_id);

CREATE INDEX ix_operation_receipts_submission_id ON public.operation_receipts USING btree (submission_id);

CREATE UNIQUE INDEX ix_submission_results_submission_id ON public.submission_results USING btree (submission_id);

CREATE INDEX ix_submissions_external_user_id ON public.submissions USING btree (external_user_id);

CREATE INDEX ix_submissions_grading_config_id ON public.submissions USING btree (grading_config_id);

CREATE INDEX ix_submissions_lease_until ON public.submissions USING btree (lease_until);

CREATE INDEX ix_submissions_status ON public.submissions USING btree (status);

CREATE INDEX ix_submissions_submitted_at ON public.submissions USING btree (submitted_at);

ALTER TABLE ONLY public.grading_attempts
    ADD CONSTRAINT grading_attempts_submission_id_fkey FOREIGN KEY (submission_id) REFERENCES public.submissions(id);

ALTER TABLE ONLY public.operation_receipts
    ADD CONSTRAINT operation_receipts_submission_id_fkey FOREIGN KEY (submission_id) REFERENCES public.submissions(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.submission_results
    ADD CONSTRAINT submission_results_submission_id_fkey FOREIGN KEY (submission_id) REFERENCES public.submissions(id);

ALTER TABLE ONLY public.submissions
    ADD CONSTRAINT submissions_grading_config_id_fkey FOREIGN KEY (grading_config_id) REFERENCES public.grading_configurations(id);

INSERT INTO public.alembic_version (version_num) VALUES ('007');
