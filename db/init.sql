DROP TABLE IF EXISTS narrative_jobs;
DROP TABLE IF EXISTS adverse_events;

CREATE TABLE adverse_events (
  id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  studyid text NOT NULL,
  domain text NOT NULL DEFAULT 'AE',
  usubjid text NOT NULL,
  aeseq integer NOT NULL,
  aespid text NOT NULL,
  aeterm text NOT NULL,
  aemodify text,
  aedecod text NOT NULL,
  aebodsys text NOT NULL,
  aesoc text NOT NULL,
  aeloc text,
  aesev text NOT NULL,
  aeser text NOT NULL,
  aescat text,
  aescat2 text,
  aestdtc date NOT NULL,
  aeendtc date,
  aeongo text NOT NULL,
  aerel text NOT NULL,
  aeacn text NOT NULL,
  aeout text NOT NULL,
  aedth text NOT NULL DEFAULT 'N',
  aehosp text NOT NULL DEFAULT 'N',
  aecong text NOT NULL DEFAULT 'N',
  narrative text
);

CREATE TABLE narrative_jobs (
  id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  adverse_event_id integer NOT NULL REFERENCES adverse_events(id),
  status text NOT NULL DEFAULT 'queued',
  created_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  completed_at timestamptz,
  error text
);

CREATE UNIQUE INDEX narrative_jobs_one_active_per_event
ON narrative_jobs (adverse_event_id) WHERE status IN ('queued', 'running');

INSERT INTO adverse_events (studyid, usubjid, aeseq, aespid, aeterm, aemodify, aedecod, aebodsys, aesoc, aeloc, aesev, aeser, aescat, aescat2, aestdtc, aeendtc, aeongo, aerel, aeacn, aeout, aedth, aehosp, aecong)
SELECT
  'AGENT-AE-001', 'AE-' || lpad(n::text, 4, '0'), 1, 'AE-' || lpad(n::text, 4, '0'),
  (ARRAY['headache', 'nausea', 'fatigue', 'dizziness', 'rash', 'insomnia'])[1 + (n - 1) % 6],
  (ARRAY['Headache', 'Nausea', 'Fatigue', 'Dizziness', 'Rash', 'Insomnia'])[1 + (n - 1) % 6],
  (ARRAY['HEADACHE', 'NAUSEA', 'FATIGUE', 'DIZZINESS', 'RASH', 'INSOMNIA'])[1 + (n - 1) % 6],
  (ARRAY['Nervous system disorders', 'Gastrointestinal disorders', 'General disorders and administration site conditions', 'Skin and subcutaneous tissue disorders'])[1 + (n - 1) % 4],
  (ARRAY['Nervous system disorders', 'Gastrointestinal disorders', 'General disorders and administration site conditions', 'Skin and subcutaneous tissue disorders'])[1 + (n - 1) % 4],
  (ARRAY['Head', 'Gastrointestinal tract', NULL, NULL, 'Skin', NULL])[1 + (n - 1) % 6],
  (ARRAY['MILD', 'MODERATE', 'SEVERE'])[1 + (n - 1) % 3], CASE WHEN n % 11 = 0 THEN 'Y' ELSE 'N' END,
  CASE WHEN n % 6 = 0 THEN 'TREATMENT EMERGENT' ELSE 'NON-TREATMENT EMERGENT' END, NULL,
  DATE '2026-01-01' + n, CASE WHEN n % 4 = 0 THEN NULL ELSE DATE '2026-01-03' + n END,
  CASE WHEN n % 4 = 0 THEN 'Y' ELSE 'N' END,
  (ARRAY['NOT RELATED', 'POSSIBLY RELATED', 'PROBABLY RELATED'])[1 + (n - 1) % 3],
  (ARRAY['NONE', 'DRUG INTERRUPTED', 'CONCOMITANT MEDICATION'])[1 + (n - 1) % 3],
  CASE WHEN n % 4 = 0 THEN 'NOT RECOVERED/NOT RESOLVED' ELSE 'RECOVERED/RESOLVED' END,
  'N', CASE WHEN n % 11 = 0 THEN 'Y' ELSE 'N' END, 'N'
FROM generate_series(1, 32) AS n;

UPDATE adverse_events
SET narrative = 'The participant reported a mild headache on 2026-01-02. The event was assessed as not related to study treatment. No action was taken with study treatment. The headache resolved on 2026-01-04 without sequelae. The participant continued study participation.'
WHERE usubjid = 'AE-0001';