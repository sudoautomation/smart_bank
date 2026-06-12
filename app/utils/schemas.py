# app/utils/schemas.py — northstar-bank
# Database schema definitions passed to the NL-to-SQL generator as context.

NL_TO_SQL_SCHEMA = """
Database: PostgreSQL
All tables are in the `banking` schema.

banking.customers
  customer_id   UUID  PK
  full_name     VARCHAR(150)
  email         VARCHAR(150) UNIQUE
  phone         VARCHAR(20)
  date_of_birth DATE
  kyc_status    VARCHAR(20)   -- 'pending' | 'verified' | 'rejected'
  credit_score  INTEGER       -- 300–900
  created_at    TIMESTAMPTZ

banking.accounts
  account_id     UUID  PK
  customer_id    UUID  FK → banking.customers
  account_number VARCHAR(20) UNIQUE
  account_type   VARCHAR(20)  -- 'savings' | 'current' | 'loan' | 'fd'
  balance        NUMERIC(15,2)
  currency       VARCHAR(5)   DEFAULT 'INR'
  status         VARCHAR(20)  -- 'active' | 'inactive' | 'frozen' | 'closed'
  opened_at      TIMESTAMPTZ

banking.transactions
  transaction_id UUID  PK
  account_id     UUID  FK → banking.accounts
  txn_type       VARCHAR(20)  -- 'credit' | 'debit' | 'transfer' | 'emi' | 'fee'
  amount         NUMERIC(15,2)
  currency       VARCHAR(5)   DEFAULT 'INR'
  description    TEXT
  txn_date       TIMESTAMPTZ
  reference_id   VARCHAR(50)

banking.loans
  loan_id        UUID  PK
  customer_id    UUID  FK → banking.customers
  account_id     UUID  FK → banking.accounts  (nullable)
  loan_type      VARCHAR(30)  -- 'home' | 'personal' | 'auto' | 'education' | 'business'
  principal      NUMERIC(15,2)
  interest_rate  NUMERIC(5,2)
  tenure_months  INTEGER
  emi_amount     NUMERIC(15,2)
  disbursed_at   TIMESTAMPTZ
  status         VARCHAR(20)  -- 'pending' | 'active' | 'closed' | 'npa'

banking.branches
  branch_id   UUID  PK
  branch_name VARCHAR(100)
  branch_code VARCHAR(20) UNIQUE
  city        VARCHAR(60)
  state       VARCHAR(60)
  ifsc_code   VARCHAR(20) UNIQUE
"""
