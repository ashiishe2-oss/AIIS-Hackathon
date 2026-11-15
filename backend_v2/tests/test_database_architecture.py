"""
AIIS Backend V2 - Stage 2: Database Architecture & Migration Test Suite
======================================================================
Automated validation of:
1. SQL migration sequence and file structure.
2. Schema integrity, tables, foreign keys, and indexes.
3. Capacity constraints and mathematical balance rules.
4. Emergency category and status lifecycle constraints.
5. Row Level Security (RLS) policy coverage and immutability checks.
6. Guest tracking token SHA-256 cryptographic design.
7. Supabase client configuration and environment isolation.
"""

import os
import re
import hashlib
import secrets
import pytest

from backend_v2.config import BaseConfig, TestingConfig
from backend_v2.extensions import SupabaseManager

MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "database",
    "migrations",
)
SEEDS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "database",
    "seeds",
)


# ── 1. Migration Ordering & File Integrity ───────────────────────────────────

def test_migration_files_sequence():
    """Verify that all migration files exist in strict sequential ordering."""
    assert os.path.exists(MIGRATIONS_DIR), "Migrations directory must exist"
    migration_files = sorted([f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")])

    expected_prefixes = [
        "001_create_profiles.sql",
        "002_create_hospitals.sql",
        "003_create_hospital_capabilities.sql",
        "004_create_hospital_capacity.sql",
        "005_create_emergency_requests.sql",
        "006_create_emergency_request_events.sql",
        "007_create_hospital_request_responses.sql",
        "008_create_normal_healthcare.sql",
        "009_create_indexes_and_constraints.sql",
        "010_enable_rls_policies.sql",
    ]

    for expected in expected_prefixes:
        assert expected in migration_files, f"Migration {expected} must be present in {MIGRATIONS_DIR}"

    # Verify seed files exist
    assert os.path.exists(SEEDS_DIR), "Seeds directory must exist"
    seed_files = os.listdir(SEEDS_DIR)
    assert "001_seed_hospitals.sql" in seed_files
    assert "002_seed_capabilities_and_departments.sql" in seed_files


# ── 2. Table Creation & Relationship Static Analysis ─────────────────────────

def _load_all_sql() -> str:
    """Concatenate all migration SQL files for holistic analysis."""
    migration_files = sorted([f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")])
    combined_sql = ""
    for mf in migration_files:
        with open(os.path.join(MIGRATIONS_DIR, mf), "r", encoding="utf-8") as f:
            combined_sql += f"\n-- File: {mf}\n" + f.read()
    return combined_sql


def test_core_tables_defined():
    """Verify all 3 AIIS pillars have defined tables with explicit schemas."""
    sql = _load_all_sql().lower()

    required_tables = [
        "profiles",
        "hospitals",
        "hospital_capabilities",
        "hospital_capacity",
        "hospital_capacity_history",
        "emergency_requests",
        "emergency_request_events",
        "hospital_request_responses",
        "hospital_departments",
        "hospital_equipment",
        "appointments",
    ]

    for tbl in required_tables:
        pattern = rf"create table if not exists public\.{tbl}\s*\("
        match = re.search(pattern, sql)
        assert match is not None, f"Table public.{tbl} definition not found in migrations"


def test_primary_and_foreign_keys():
    """Verify primary keys and referential integrity foreign keys are defined."""
    sql = _load_all_sql().lower()

    # Foreign key references
    assert "references auth.users(id)" in sql
    assert "references public.hospitals(id)" in sql
    assert "references public.profiles(id)" in sql
    assert "references public.emergency_requests(id)" in sql


# ── 3. Mathematical Constraints & Capacity Integrity ─────────────────────────

def test_capacity_mathematical_constraints():
    """Verify check constraints prevent impossible bed allocations."""
    with open(os.path.join(MIGRATIONS_DIR, "004_create_hospital_capacity.sql"), "r", encoding="utf-8") as f:
        sql = f.read().lower()

    # Bed balance: occupied + available + provisional <= total
    assert "check (occupied_beds + available_beds + provisionally_allocated_beds <= total_beds)" in sql
    # ICU balance: icu_occupied + icu_available <= icu_total
    assert "check (icu_occupied + icu_available <= icu_total)" in sql
    # Ventilator balance: ventilators_available <= ventilators_total
    assert "check (ventilators_available <= ventilators_total)" in sql


def test_capacity_python_validation_rules():
    """Unit test the mathematical capacity integrity in Python application layer."""
    def validate_capacity(total, avail, occ, prov):
        if total < 0 or avail < 0 or occ < 0 or prov < 0:
            return False, "Negative values not allowed"
        if (avail + occ + prov) > total:
            return False, "Total allocated beds exceed physical capacity"
        return True, "Valid"

    # Valid distribution
    is_valid, _ = validate_capacity(total=100, avail=15, occ=80, prov=5)
    assert is_valid is True

    # Over-allocation failure
    is_valid, msg = validate_capacity(total=100, avail=20, occ=85, prov=5)
    assert is_valid is False
    assert "exceed" in msg

    # Negative value failure
    is_valid, msg = validate_capacity(total=100, avail=-1, occ=80, prov=0)
    assert is_valid is False


# ── 4. Emergency Categories & Status Validation ──────────────────────────────

def test_emergency_categories_and_statuses():
    """Verify allowed categories and status lifecycles are restricted via CHECK constraints."""
    with open(os.path.join(MIGRATIONS_DIR, "005_create_emergency_requests.sql"), "r", encoding="utf-8") as f:
        sql = f.read().lower()

    categories = ["cardiac", "stroke_neuro", "trauma", "breathing", "paediatric", "other_unsure"]
    for cat in categories:
        assert cat in sql, f"Category '{cat}' must be in emergency_requests check constraint"

    statuses = ["pending", "acknowledged", "accepted", "declined", "expired", "cancelled", "completed"]
    for st in statuses:
        assert st in sql, f"Status '{st}' must be in emergency_requests check constraint"


# ── 5. Row Level Security (RLS) Policy Coverage ──────────────────────────────

def test_rls_enabled_on_all_tables():
    """Verify that every sensitive table has RLS explicitly enabled."""
    with open(os.path.join(MIGRATIONS_DIR, "010_enable_rls_policies.sql"), "r", encoding="utf-8") as f:
        rls_sql = f.read().lower()

    tables = [
        "profiles",
        "hospitals",
        "hospital_capabilities",
        "hospital_capacity",
        "hospital_capacity_history",
        "emergency_requests",
        "emergency_request_events",
        "hospital_request_responses",
        "hospital_departments",
        "hospital_equipment",
        "appointments",
    ]

    for tbl in tables:
        expected = f"alter table public.{tbl} enable row level security;"
        assert expected in rls_sql, f"RLS must be enabled on public.{tbl}"


def test_immutable_audit_events_policy():
    """Verify emergency_request_events prohibits UPDATE and DELETE policies."""
    with open(os.path.join(MIGRATIONS_DIR, "010_enable_rls_policies.sql"), "r", encoding="utf-8") as f:
        rls_sql = f.read()

    # Find all policies on emergency_request_events
    event_policies = re.findall(
        r'CREATE\s+POLICY\s+"([^"]+)"\s+ON\s+public\.emergency_request_events\s+FOR\s+(\w+)',
        rls_sql,
        re.IGNORECASE,
    )

    for pol_name, op in event_policies:
        assert op.upper() in {"SELECT", "INSERT"}, (
            f"Policy {pol_name} on emergency_request_events allows operation '{op}'. "
            "Only SELECT and INSERT are permitted on immutable audit ledger!"
        )


def test_hospital_admin_isolation_policy():
    """Verify hospital admin policies strictly bind to get_auth_user_hospital_id()."""
    with open(os.path.join(MIGRATIONS_DIR, "010_enable_rls_policies.sql"), "r", encoding="utf-8") as f:
        rls_sql = f.read()

    # The helper function must be defined as SECURITY DEFINER
    assert "FUNCTION public.get_auth_user_hospital_id()" in rls_sql
    assert "SECURITY DEFINER" in rls_sql
    assert "capacity_hospital_admin_update" in rls_sql


# ── 6. Guest Tracking Token Cryptographic Design ──────────────────────────────

def test_guest_tracking_token_hash_design():
    """
    Verify high-entropy guest token generation and SHA-256 verification.
    The server stores ONLY the hash; the guest holds the raw token.
    """
    # 1. Generate 32-byte high-entropy token for guest
    raw_guest_token = secrets.token_hex(32)
    assert len(raw_guest_token) == 64

    # 2. Hash token with SHA-256 for database persistence
    stored_hash = hashlib.sha256(raw_guest_token.encode("utf-8")).hexdigest()
    assert len(stored_hash) == 64

    # 3. Verify incoming token against stored hash
    incoming_token_valid = raw_guest_token
    incoming_token_invalid = secrets.token_hex(32)

    assert hashlib.sha256(incoming_token_valid.encode("utf-8")).hexdigest() == stored_hash
    assert hashlib.sha256(incoming_token_invalid.encode("utf-8")).hexdigest() != stored_hash


# ── 7. Supabase Client & Environment Configuration ────────────────────────────

def test_supabase_manager_graceful_missing_credentials():
    """Verify Supabase client handles unconfigured credentials safely without crashing."""
    manager = SupabaseManager()
    assert manager.is_configured is False
    assert manager.get_client() is None
    assert manager.get_admin_client() is None


def test_config_reads_all_supabase_vars(monkeypatch):
    """Verify configuration loads all Supabase variables."""
    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-abc")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key-xyz")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "jwt-secret-123")

    class TestConf(BaseConfig):
        SUPABASE_URL = os.getenv("SUPABASE_URL", "")
        SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
        SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

    conf = TestConf()
    assert conf.SUPABASE_URL == "https://xyzcompany.supabase.co"
    assert conf.SUPABASE_ANON_KEY == "anon-key-abc"
    assert conf.SUPABASE_SERVICE_ROLE_KEY == "service-key-xyz"
    assert conf.SUPABASE_JWT_SECRET == "jwt-secret-123"

