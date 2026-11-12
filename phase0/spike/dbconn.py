import os, psycopg

def kwargs():
    if os.getenv("SUPABASE_DB_HOST"):
        return dict(host=os.environ["SUPABASE_DB_HOST"], port=int(os.getenv("SUPABASE_DB_PORT", "5432")),
                    dbname=os.getenv("SUPABASE_DB_NAME", "postgres"), user=os.environ["SUPABASE_DB_USER"],
                    password=os.environ["SUPABASE_DB_PASSWORD"], sslmode="require")
    return dict(host=os.getenv("PGHOST", "localhost"), port=int(os.getenv("PGPORT", "5432")),
                dbname=os.getenv("PGDATABASE", "postgres"), user=os.getenv("PGUSER", "postgres"),
                password=os.getenv("PGPASSWORD", ""))

def connect(**extra):
    return psycopg.connect(**kwargs(), autocommit=True, **extra)
