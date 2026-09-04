-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- RIGS Qualified Leads
CREATE TABLE IF NOT EXISTS public.leads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization VARCHAR(255) NOT NULL,
    risk_score NUMERIC(3,2) NOT NULL,
    intent_score INT NOT NULL,
    growth_tier VARCHAR(50) NOT NULL,
    stakeholder_role VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trust Settlement Ledger
CREATE TABLE IF NOT EXISTS public.settlement_ledger (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_source VARCHAR(100) NOT NULL,
    volume_amount NUMERIC(12,2) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- System Audit & Friction Logs
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source VARCHAR(100) NOT NULL,
    event VARCHAR(550) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed Initial Pipeline Data
INSERT INTO public.leads (organization, risk_score, intent_score, growth_tier, stakeholder_role, status)
VALUES 
    ('Apex Logistics Corp', 0.12, 94, 'Tier-1', 'C-Suite', 'Qualified'),
    ('Synergy Cloud Group', 0.34, 98, 'Enterprise', 'VP Eng', 'Qualified');

INSERT INTO public.settlement_ledger (event_source, volume_amount, status)
VALUES ('initial_escrow', 393000.00, 'Cleared');
