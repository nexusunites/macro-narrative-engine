import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import sqlalchemy as sa
from alembic import command
from alembic.config import Config


class StudioBoardMigrationTests(unittest.TestCase):
    def test_0005_up_preserves_q1_data_and_down_keeps_newest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "migration.sqlite3"
            url = f"sqlite:///{path}"
            config = Config("alembic.ini")
            with patch.dict(os.environ, {"MNE_DATABASE_URL": url}):
                command.upgrade(config, "0004_studio_board")

                engine = sa.create_engine(url)
                older = datetime(2026, 8, 12, 12, 0)
                original = {"schema_version": 1, "thesis": "Existing Q1 thesis", "nodes": [], "connections": []}
                with engine.begin() as connection:
                    connection.execute(sa.text(
                        "INSERT INTO users (user_id,email,password_hash,display_name,account_status,role,plan,internal_full_access,created_at,updated_at,terms_accepted_at,privacy_accepted_at) "
                        "VALUES (:id,:email,'hash','Migration User','ACTIVE','USER','FREE',0,:at,:at,:at,:at)"
                    ), {"id": "migration-user", "email": "migration@example.com", "at": older})
                    connection.exec_driver_sql("DROP TABLE studio_boards")
                    connection.exec_driver_sql(
                        "CREATE TABLE studio_boards (user_id VARCHAR(36) PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE, payload JSON NOT NULL, updated_at DATETIME NOT NULL)"
                    )
                    connection.execute(sa.text(
                        "INSERT INTO studio_boards (user_id,payload,updated_at) VALUES (:user_id,:payload,:updated_at)"
                    ), {"user_id": "migration-user", "payload": json.dumps(original), "updated_at": older})
                engine.dispose()

                command.upgrade(config, "0005_studio_boards_multi")
                engine = sa.create_engine(url)
                with engine.connect() as connection:
                    migrated = connection.execute(sa.text(
                        "SELECT board_id,user_id,payload,created_at,updated_at FROM studio_boards"
                    )).mappings().one()
                self.assertEqual(migrated["user_id"], "migration-user")
                self.assertEqual(json.loads(migrated["payload"]), original)
                self.assertEqual(migrated["created_at"], migrated["updated_at"])
                self.assertTrue(migrated["board_id"])

                newer = older + timedelta(days=1)
                replacement = {**original, "thesis": "Newest thesis"}
                with engine.begin() as connection:
                    connection.execute(sa.text(
                        "INSERT INTO studio_boards (board_id,user_id,payload,created_at,updated_at) VALUES ('newest','migration-user',:payload,:created_at,:updated_at)"
                    ), {"payload": json.dumps(replacement), "created_at": newer, "updated_at": newer})
                engine.dispose()

                command.downgrade(config, "0004_studio_board")
                engine = sa.create_engine(url)
                with engine.connect() as connection:
                    collapsed = connection.execute(sa.text(
                        "SELECT user_id,payload,updated_at FROM studio_boards"
                    )).mappings().one()
                self.assertEqual(collapsed["user_id"], "migration-user")
                self.assertEqual(json.loads(collapsed["payload"])["thesis"], "Newest thesis")
                engine.dispose()

                command.upgrade(config, "0005_studio_boards_multi")


if __name__ == "__main__":
    unittest.main()
