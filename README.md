# Maisha Jobs Platform

Maisha Jobs is a Flask-based job board and hiring portal with candidate applications, employer dashboards, AI-assisted interview flows, resume analysis, and PWA support.

## Features

- Candidate job browsing, application, and profile management
- Employer dashboard with:
  - overview stats
  - `Your Jobs` management page
  - applications and candidate detail views
  - taxonomy management for industries and categories
- AI interview generation and answer evaluation powered by OpenRouter
- Resume upload and AI resume fit analysis
- Email verification and interview invitation emails
- PWA manifest and service worker support
- Responsive layout for desktop and mobile

## Project Structure

- `app/blueprints/` - Flask route groups for candidates, jobs, and employers
- `app/services/` - business logic, AI helpers, verification, resume analysis
- `app/repository/` - database access layer
- `app/templates/` - Jinja templates for the UI
- `app/static/` - icons, resumes, and PWA assets
- `run.py` - local development entry point

## Requirements

- Python 3.13+
- Flask
- MySQL or MariaDB database
- Mail server access for OTP and notification emails
- OpenRouter API key for AI interview features

## Environment Variables

Create a `.env` file with the following values:

```env
FLASK_SECRET_KEY=your-secret-key

DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your-password
DB_NAME=maisha_jobs

MAIL_USERNAME=your-mail-username
MAIL_PASSWORD=your-mail-password
MAIL_DEFAULT_SENDER=accounts@cm.co.ke

OPEN_ROUTER_API_KEY=your-openrouter-key
# or
OPENROUTER_API_KEY=your-openrouter-key

YOUR_SITE_URL=https://your-domain.example
YOUR_SITE_NAME=Maisha Jobs
```

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Make sure your database is available and the schema is loaded.
4. Add your `.env` file.
5. Run the app:

```bash
python run.py
```

## Key Employer Pages

- `/employers/dashboard` - overview dashboard
- `/employers/jobs` - `Your Jobs` page
- `/employers/jobs/new` - create a job
- `/employers/jobs/<job_id>` - job detail
- `/employers/jobs/<job_id>/applications` - applications for a job
- `/employers/jobs/<job_id>/applications/<application_id>` - application detail
- `/employers/candidates/<candidate_id>` - candidate detail
- `/employers/taxonomy` - industries and categories

## Key Candidate Pages

- `/` - job listings
- `/jobs/<job_id>` - job detail
- `/jobs/<job_id>/apply` - standard application
- `/jobs/<job_id>/easy-apply` - logged-in candidate application
- `/jobs/<job_id>/interview` - AI interview entry point

## PWA

The app includes:

- `app/static/pwa/manifest.json`
- `app/static/pwa/sw.js`

The shared layouts load the manifest and register the service worker automatically.

## Notes

- AI interview prompts now use the full job details, including title, description, skills, experience level, and taxonomy.
- Resume uploads are stored under `app/static/resumes/`.
- The employer UI uses a fixed dashboard shell with a collapsible sidebar and internal scrolling content.

## Branding

Footer branding points to:

- [Cybermaisha](https://cybermaisha.co.ke)


## Passwordless sign-in

All three portals use email OTPs:

- `/candidates/login` — existing candidate accounts; registration is available.
- `/employers/login` — existing employer accounts; registration is available.
- `/admin/login` — restricted to the comma-separated `ADMIN_EMAILS` allowlist in the environment.

Set `ADMIN_EMAILS` to your administrator email addresses and restart the app. Admin access is disabled when this value is empty; public registration cannot create an administrator. The admin overview lists employer accounts and role totals.

Mail settings are read from the environment, including `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USE_SSL`, `MAIL_USERNAME`, `MAIL_PASSWORD`, and `MAIL_DEFAULT_SENDER`. Use an email address for the sender. See `.env.example`. Set `SESSION_COOKIE_SECURE=true` for HTTPS deployments. Install with `pip install -r requirements.txt` (this includes `req.txt`).

The existing database initializer creates the `auth_challenges` table automatically. Codes are stored as keyed hashes, isolated by account role, expire after 10 minutes, and allow five attempts. Resends require a 60-second cooldown and invalidate the previous code. Verification consumes a code atomically, establishes an eight-hour session, and clears other role sessions. Failed mail delivery does not establish a pending login. Resend and authentication forms use CSRF tokens. The service worker caches only public static assets; authenticated pages use the network.

Run authentication and template checks with `python -m unittest discover -s tests -v`. To also run repository integration tests against the configured MySQL database, set `AUTH_TEST_MYSQL=1`. These tests use temporary `example.invalid` identities and never send real email.

The refreshed UI draws inspiration from [Nearskill](https://nearskill.in/): a light grid background, indigo accents, a search-led jobs page, consistent role cards, and shared role-specific sign-in screens. Keyword search combines with industry, category, and experience filters.


## Interview coverage and coding challenges

Interviews now save a 15-question plan on first start and reuse it when candidates
resume. Every description item and listed skill is allocated to a coverage slot;
the AI receives the full job context and a distinct focus for each slot. Valid AI questions are retained even when the provider adds prose or truncates
its response. Missing, invalid, or repeated questions are replaced with distinct
prepared questions tailored to each coverage slot before the plan is saved.
Prepared technical challenges include examples, constraints, and required tests.
Existing interviews keep their submitted answers and receive a plan for the
remaining questions. Candidates must answer all questions before finishing, and
duplicate submissions cannot increment scores.

In the employer job form, enable **Technical job — include coding challenges**
alongside **AI Enabled** to include three coding challenges. Each challenge asks
for inputs, outputs, constraints, examples, and edge-case tests. Candidates submit
code, their language, and an explanation with test cases. The AI reviews the code
statically; this version does not execute submissions or provide sandboxed test runs.
Code and explanations appear in the existing employer interview response review.

The database initializer adds `jobs.is_technical` (default false) and
`interviews.question_plan` automatically. Existing jobs must be explicitly marked
technical to receive coding challenges in new interview plans; saved plans stay
unchanged. Run regression checks with `python -m unittest discover -s tests -v`.

## Structured job postings

Employer create/edit forms and job detail pages now separate Overview, What you
will do, Requirements, Who should apply, Salary insight, and Location. Overview
uses the existing `description` field so older postings retain their content.
Salary insight is employer-provided text: include currency, range, and pay period.
Posted date comes from `created_at` and remains unchanged when a job is edited;
the application deadline remains editable. Missing fields display clear placeholders.
The database initializer adds the new nullable text columns automatically.
Responsibilities, requirements, and applicant guidance also feed interview planning
and resume fit analysis. Keyword search includes the new role content and location.

## Candidate workspace, CV matching, and feedback

The candidate workspace groups applied jobs, pending interviews, saved jobs, and CV
matches. Start/Continue Interview opens the next unanswered question directly.
Posting deadlines stop new applications; existing applicants can still complete
their interview. Missing-job interview pages render an error without loading the
interview script.

Candidates can upload a text-based PDF or DOCX CV (up to 5 MB) from My CV. Install
the updated requirements for PDF parsing. Profile CV files live under
`app/private/candidate_resumes/`; their metadata and extracted text are stored in
the candidate record. Matches rank open, unapplied roles by shared skills and
terms, and refresh when the workspace opens. Scores represent text overlap.
Applications can reuse a saved CV, and replacing it does not change earlier
applications. New saved-CV downloads are restricted to the candidate, authorized
employer for an application, or an allowlisted administrator.

New interview evaluations save a score, feedback, suggested strong answer, and
question number. Candidates can review submitted responses from each application.
Answers are locked after submission, with row locking and a unique database index
preventing concurrent retries from saving or scoring twice. Older responses
without a suggested answer show an explicit historical-data placeholder.

The admin dashboard adds active-role and candidate counts, an application
pipeline, recent applications, employer verification totals, and interview metrics.
Public, candidate, employer, and admin screens share the refreshed responsive
workspace stylesheet. Database migrations are additive and run through the
existing initializer.

Run standard checks with `python -m unittest discover -s tests -v`. Run isolated
job/CV persistence and concurrent interview submission checks with
`INTERVIEW_TEST_MYSQL=1 python -m unittest discover -s tests -p test_interview_repository.py -v`.
These create temporary records, delete them afterward, and send no email or AI requests.

The public top navigation includes Home, Browse Jobs, Categories, AI Job Match,
and Find Jobs, with the same destinations in the mobile menu. Categories show
open-role counts and link to filtered searches. AI Job Match opens the CV matching
workspace for signed-in candidates and a sign-in/upload introduction for guests.
The light/dark toggle persists the preference across public and employer pages.


## Reliable answer submission

Interview answers are committed and locked before AI evaluation. Provider failures
or malformed output leave a nullable score and `evaluation_status=pending`, allowing
the candidate to continue and finish without a zero grade. The application average
remains pending until every answer is graded. Candidates can retry feedback from
the saved application review; this evaluates the existing immutable answer and
cannot add the score twice.

Feedback uses a strict JSON schema for score, feedback, and suggested answer.
The default model order is `openai/gpt-4o-mini,openai/gpt-4.1-mini`, configurable
with `OPENROUTER_MODEL` or comma-separated `OPENROUTER_MODELS`. A failed request
tries the next configured model. Model availability or account limits can still
delay evaluation, while saved answers remain available.
