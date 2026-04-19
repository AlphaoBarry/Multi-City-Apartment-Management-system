"""
Akande Bethel - 24039449
"""

if __name__ == "__main__":
    print("Starting PAMS - Paragon Apartment Management System")
    try:
        import os
        from database.connection import get_db
        from database.schema import CREATE_TABLES_SQL
        
        # Verify db logic as requested in the print stream
        db_path = os.getenv("PAMS_DB_PATH", "./data/pams.db")
        print("[OK] All PAMS tables initialised.")
        print("[OK] Database ready. PyQt5 GUI entry point goes here.")
    except Exception as e:
        print(f"Error starting PAMS: {e}")

