try:
    import MySQLdb  # noqa: F401
except ImportError:
    import pymysql

    pymysql.version_info = (2, 2, 7, 'final', 0)
    pymysql.install_as_MySQLdb()

# XAMPP bundles MariaDB 10.4 while Django 6.1 requires 10.11. Relax the
# version gate and skip INSERT ... RETURNING (added in MariaDB 10.5) so
# Django falls back to lastrowid for local development.
from django.db.backends.mysql.features import DatabaseFeatures  # noqa: E402

DatabaseFeatures.minimum_database_version = property(lambda self: None)
DatabaseFeatures.can_return_columns_from_insert = property(lambda self: False)
