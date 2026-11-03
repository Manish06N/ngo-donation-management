# Database

PostgreSQL in Docker, SQLite for tests and a laptop without Docker. The migration in `alembic/versions` is the schema both of them apply.

Money is `NUMERIC(12, 2)`. Stock quantities are integers with a check that they cannot go negative. Donation references and receipt numbers are unique. A donation has at most one receipt.

```mermaid
erDiagram
  users ||--o| donors : profile
  users ||--o| volunteers : profile
  users ||--o{ refresh_tokens : sessions
  users ||--o{ password_reset_tokens : resets
  donors ||--o{ donor_contacts : contacts
  donors ||--o{ donations : gives
  campaigns ||--o{ donations : receives
  donations ||--o| donation_receipts : receipt
  users ||--o{ campaigns : manages
  users ||--o{ projects : manages
  projects ||--o{ project_approvals : decisions
  projects ||--o{ milestones : milestones
  milestones ||--o{ tasks : tasks
  volunteers ||--o{ tasks : assigned
  volunteers ||--o{ volunteer_assignments : assignments
  projects ||--o{ volunteer_assignments : staffs
  volunteer_assignments ||--o{ attendance : days
  projects ||--o{ expenses : expenses
  campaigns ||--o{ expenses : "optional spend"
  expenses ||--o{ expense_actions : history
  resources ||--o{ resource_transactions : movements
  projects ||--o{ resource_transactions : allocations
  beneficiaries }o--o{ projects : "beneficiary_projects"
  beneficiaries ||--o{ beneficiary_assistance : assistance
  projects ||--o{ impact_updates : impact
  users ||--o{ notifications : inbox
  users ||--o{ audit_logs : actions
```

`campaigns.goal_amount` is what the fundraiser is trying to raise. `campaigns.raised_amount` is the sum of confirmed donations that have not been reversed or refunded. `campaigns.budget_amount` and `projects.budget_amount` are spending limits. Approved and reimbursed expenses count against those limits.

`projects.approval_state` is separate from `projects.status`. A project can sit in planning while a decision is pending. Status becomes `approved` only when someone with approval permission accepts it.
