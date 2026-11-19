-- =====================================================================
-- 031 — The record of applied migrations (Staging readiness plan P7, ADR-071, ADR-016 amendment 1)
-- One row per migration file applied to this database: its number, file name, the sha256 of its text (CRLF read as
-- LF, so a Windows and a Linux checkout give the same hash), when and by which login. Until now the owner applied
-- 001–030 by hand and the record was the ROADMAP; a deployment needs the database itself to say what it holds, so
-- `pipelines/scripts/ops/Migrate.py status` can list the pending files and `apply` (on the owner's approval) runs
-- them in order, each in its own transaction, and records them here.
-- 001–030 are recorded as applied (every database restored from the owner's has them: the stabilization audit
-- through §29). 031's own row has no hash (a file cannot hold its own hash): Migrate.py fills it on its next
-- `apply`, and `status` flags any recorded hash that no longer matches its file (an edited migration).
-- Applied as the owner account (postgres). SELECT for ports_readonly through migration 007's default privileges
-- (no secret in it); nothing for finance_bi, agent_writer or api_writer. Level 1 / IT (docs/rbac_mapping.md §2).
-- Never edited after applying.
-- =====================================================================
BEGIN;

CREATE TABLE public.schema_migrations (
    version    smallint    NOT NULL,
    filename   text        NOT NULL,
    sha256     char(64),
    applied_at timestamptz NOT NULL DEFAULT now(),
    applied_by text        NOT NULL DEFAULT current_user,
    note       text,
    CONSTRAINT schema_migrations_pkey PRIMARY KEY (version),
    CONSTRAINT schema_migrations_filename_key UNIQUE (filename),
    CONSTRAINT schema_migrations_version_check CHECK (version > 0),
    CONSTRAINT schema_migrations_filename_check CHECK (filename ~ '^[0-9]{3}_[a-z0-9_]+\.sql$'
                                                       AND left(filename, 3)::smallint = version),
    CONSTRAINT schema_migrations_sha256_check CHECK (sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$')
);

COMMENT ON TABLE public.schema_migrations IS
    'One row per db/migrations file applied to this database (migration 031, ADR-071): written by Migrate.py apply; '
    '001-030 recorded by 031 itself. The deploy reads it to find pending files.';
COMMENT ON COLUMN public.schema_migrations.version IS 'The migration number, the first three digits of the file name.';
COMMENT ON COLUMN public.schema_migrations.filename IS 'The file name in db/migrations/.';
COMMENT ON COLUMN public.schema_migrations.sha256 IS
    'sha256 of the file text with CRLF read as LF; NULL only for 031 until Migrate.py records it.';
COMMENT ON COLUMN public.schema_migrations.applied_at IS 'When the migration was applied or, for 001-030, recorded.';
COMMENT ON COLUMN public.schema_migrations.applied_by IS 'The database login that applied or recorded it.';
COMMENT ON COLUMN public.schema_migrations.note IS 'How it was applied (by hand before 031, by Migrate.py after).';

INSERT INTO public.schema_migrations (version, filename, sha256, note) VALUES
    (1,  '001_drop_accepted_currencies.sql',       '4ac676bd63c37b8bd544e8c49f1dfb1c1f75324a4accf9d789a3a9c6dd7bea1a', 'applied by hand before 031'),
    (2,  '002_create_documents.sql',               'b2cbe0103d58f23ee8ae36fb116b4545abd99df5c1501bbe5140b40429186dad', 'applied by hand before 031'),
    (3,  '003_drop_employees_status.sql',          '46d92eb8855328da04a2a56f358631143514376feb8fef1a64a9e31d1465006a', 'applied by hand before 031'),
    (4,  '004_add_vessels_mmsi.sql',               'd6a6790257f951e0bb9d9083f438a5c5fa1f1d1c814954e1449689333a98adbc', 'applied by hand before 031'),
    (5,  '005_fill_vessels_mmsi.sql',              '8fa91fff4bd775913a70e8e43112e24199bf54d9c31ac8b435226c1174e18df1', 'applied by hand before 031'),
    (6,  '006_constraints_and_indexes.sql',        '770f6f0bb031a5824a0c0d1d5826dab8a467c7cd95395d22116f0cacf399b6f8', 'applied by hand before 031'),
    (7,  '007_readonly_role.sql',                  '432e5bdcaad19000f93b97b17ba5eb2fe14870612f8ca1b2c9a18d2ad5b6b8b9', 'applied by hand before 031'),
    (8,  '008_comments.sql',                       'b462f96ba4534b0f5d15ab132437b9f05943d925b14169d556f5053275b893d2', 'applied by hand before 031'),
    (9,  '009_documents_comments.sql',             'c32fa1cd47f806d19c4c7899214ed969d07ebaa86a4bb30ecc580af9942f3f18', 'applied by hand before 031'),
    (10, '010_fill_documents.sql',                 '702cfc9c1a168e1d01e8259f0f95ffc07f9c2ce02a29b1b3077eebc588d73583', 'applied by hand before 031'),
    (11, '011_documents_ingested_at.sql',          '4774805777a511c7838908f05ac2d3b4718ebc3336e7efc5ecdcbb18010c6768', 'applied by hand before 031'),
    (12, '012_finance_data.sql',                   '26496ce7f9c87ded92cd587b3f77112a7a929214165313696c3a026d19885152', 'applied by hand before 031'),
    (13, '013_finance_views.sql',                  'f5093253c7e9f70144490f7ae2487f0e6d7cedc54e8a18aa7780115079d62e43', 'applied by hand before 031'),
    (14, '014_finance_trend_view.sql',             '8f80bf9131bb0db07789344d1ee3a9b8ccc30bdac6947d68422853e34818e028', 'applied by hand before 031'),
    (15, '015_invoice_audit_views.sql',            'ccbf34a3e834df488a719721123182fa6c9fba786c0b455a2b206d47cc20ad82', 'applied by hand before 031'),
    (16, '016_agent_state.sql',                    '1c9cae7e07d3eb46c44e1d6c09b07ef4afaf83ecafde6d1d5cc30eeaac0d0db7', 'applied by hand before 031'),
    (17, '017_finance_test_kpi.sql',               'd5928ed25f8f635ccc46d53e54064e148e9a264d74ac354f5e0b2db9000cafd2', 'applied by hand before 031'),
    (18, '018_finance_test_budget_miss.sql',       'ff1faf4a1563c1ba01ea6625e51c5126ae3bac274cd1ebf2bdeb281254c28d8d', 'applied by hand before 031'),
    (19, '019_invoice_audit_notes_rule.sql',       '686ed21d97a6bad64e5f375847dd2aa8d8170b6d73917300fc6cf6eb09943be3', 'applied by hand before 031'),
    (20, '020_vessel_performance.sql',             '76163a837e8337e19775575564c3a00167a2ff75b563064d1af07871585f0b24', 'applied by hand before 031'),
    (21, '021_weekly_pack_kpis.sql',               '9e2c8660bf484e681f065a688c13fbe77f668e8e246a4d1b0321f2169f0bedff', 'applied by hand before 031'),
    (22, '022_finance_test_weekly_pack_kpis.sql',  'e8a476bdc8916d5a0c0b7f8c44c6ff46329b18cf02b39176c3fe8b59891fee63', 'applied by hand before 031'),
    (23, '023_api.sql',                            'bf495777fdb61a366121769969d4bbb5759fa311e9c21c85c6c0f7bd1c85c80d', 'applied by hand before 031'),
    (24, '024_pack_approved.sql',                  '203ed4503523794804fa14341021fd27e6a486eb5e080c5c89283092afd28e1d', 'applied by hand before 031'),
    (25, '025_suez_transits.sql',                  '84355bc15446bb30ab6f7ae9c14f94f54db849b76ebcbb4d683282fad112bb10', 'applied by hand before 031'),
    (26, '026_finance_scenario.sql',               '6ed46b12cbf3da8edab8a0b8ea8d56ffdca834789ac5257f44b14b9b863d4f73', 'applied by hand before 031'),
    (27, '027_kpi_traffic_link.sql',               'bd14c1fbbac6b65c1d650af393dc793b50cf27c996505d454799f05475411b9b', 'applied by hand before 031'),
    (28, '028_pack_views_column_comments.sql',     'afdce4f7cc6602703f2e3d94121866ce0b3ed77238b10f26e5f5be00cbfd6900', 'applied by hand before 031'),
    (29, '029_kpi_weekly_breakdown.sql',           'e84e5ff22f4c034de1ea26744c904ae01d56707bf855d51cdd5e71768d0105b9', 'applied by hand before 031'),
    (30, '030_port_call_messages.sql',             'f387fde3aebdc66489616f0438e97ea4d12ce7e7b69010d4c95445274da2a982', 'applied by hand before 031'),
    (31, '031_schema_migrations.sql',              NULL,                                                               'applied by hand; hash recorded by Migrate.py');

COMMIT;
