# Database Migrations

This directory contains Alembic database migration scripts for YouTube Audit Engine.

## Creating a New Migration

### Auto-generate from model changes:
```bash
alembic revision --autogenerate -m "description of changes"
```

### Create empty migration:
```bash
alembic revision -m "description of changes"
```

## Running Migrations

### Upgrade to latest:
```bash
alembic upgrade head
```

### Upgrade to specific revision:
```bash
alembic upgrade <revision_id>
```

### Downgrade one revision:
```bash
alembic downgrade -1
```

### Downgrade to specific revision:
```bash
alembic downgrade <revision_id>
```

## Checking Migration Status

### Show current revision:
```bash
alembic current
```

### Show migration history:
```bash
alembic history
```

### Show pending migrations:
```bash
alembic show <revision_id>
```

## Best Practices

1. **Always review auto-generated migrations** - Alembic may not catch all schema changes
2. **Test migrations** - Run upgrade and downgrade to ensure they work
3. **Keep migrations atomic** - Each migration should represent a single logical change
4. **Never edit applied migrations** - Create new migrations to fix issues
5. **Backup before migrating production** - Always have a backup before running migrations

## Migration Files

Migration files are named: `YYYYMMDD_HHMM_<revision>_<slug>.py`

Example: `20240101_1200_abc123_initial_schema.py`
