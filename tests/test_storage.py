import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from cyai.storage import apply_pending, validate_destination


class StorageTests(unittest.TestCase):
    def test_migration_preserves_data_and_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root/'old', root/'new'
            source.mkdir()
            db = sqlite3.connect(source/'cyai.sqlite3')
            db.execute('CREATE TABLE test(value TEXT)')
            db.execute("INSERT INTO test VALUES('history')")
            db.commit()
            db.close()
            (source/'secrets.dpapi').write_bytes(b'opaque-encrypted-data')
            config={'data_dir':str(source),'pending_data_dir':str(target)}
            config_path=root/'config.json'
            config_path.write_text(json.dumps(config))
            apply_pending(config,config_path)
            self.assertEqual(config['data_dir'],str(target.resolve()))
            self.assertNotIn('pending_data_dir',config)
            self.assertTrue((source/'cyai.sqlite3').exists())
            self.assertEqual((target/'secrets.dpapi').read_bytes(),b'opaque-encrypted-data')
            db=sqlite3.connect(target/'cyai.sqlite3')
            self.assertEqual(db.execute('SELECT value FROM test').fetchone()[0],'history')
            db.close()

    def test_refuses_overlap_and_nonempty(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/'old';source.mkdir()
            for target in (source,source/'child',root):
                with self.assertRaises(ValueError):validate_destination(source,str(target.resolve()))
            target=root/'occupied';target.mkdir();(target/'keep').write_text('keep')
            with self.assertRaises(ValueError):validate_destination(source,str(target.resolve()))

