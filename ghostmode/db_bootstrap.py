"""Bootstrap the nestops database on RDS. Run once or on every startup (idempotent).

Connects as the postgres superuser to create the nestops database and user,
then the event_store module handles table creation.
"""
import os
import logging

logger = logging.getLogger(__name__)


def bootstrap_db():
    """Create nestops database and user if they don't exist. Idempotent."""
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    except ImportError:
        logger.warning("psycopg2 not available — skipping DB bootstrap")
        return False

    host = os.getenv("DB_HOST", "phenom-dev-postgres.c8toq6uq223c.us-east-1.rds.amazonaws.com")
    port = int(os.getenv("DB_PORT", "5432"))
    password = os.getenv("DB_PASSWORD", "")

    if not password:
        logger.warning("DB_PASSWORD not set — skipping DB bootstrap")
        return False

    try:
        # Connect as postgres superuser to create DB and role
        # Try postgres superuser first, fall back to synapse user
        bootstrap_user = os.getenv("DB_BOOTSTRAP_USER", "postgres")
        bootstrap_pass = os.getenv("DB_BOOTSTRAP_PASSWORD", password)
        conn = psycopg2.connect(
            host=host, port=port, user=bootstrap_user, password=bootstrap_pass,
            dbname="postgres", connect_timeout=10, sslmode="require"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cur:
            # Create role if not exists
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'nestops'")
            if not cur.fetchone():
                cur.execute(f"CREATE ROLE nestops WITH LOGIN PASSWORD %s", (password,))
                logger.info("Created nestops role")

            # Create database if not exists
            cur.execute("SELECT 1 FROM pg_database WHERE datname = 'nestops'")
            if not cur.fetchone():
                cur.execute("CREATE DATABASE nestops OWNER nestops")
                logger.info("Created nestops database")

            # Grant permissions
            cur.execute("GRANT ALL PRIVILEGES ON DATABASE nestops TO nestops")

        conn.close()
        logger.info("DB bootstrap complete")
        return True
    except Exception as e:
        logger.error("DB bootstrap failed: %s", e)
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bootstrap_db()
