# =====================================================================================
# Surrogate Language Alignment Program
#
# Verify expiry, active-request protection, and shutdown cleanup of owned uploads.
# =====================================================================================

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from surrogate_aligner.runs import RunStore


# Class:        RunStoreTests
# Description:  Exercises cleanup using isolated files and an explicitly controlled clock.

class RunStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.patch = patch('surrogate_aligner.runs.tempfile.gettempdir', return_value=self.directory.name)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.store = RunStore(ttl_seconds=100)
        self.addCleanup(self.store.close)

    # Expiry removes idle runs while leaving a request's actively used inputs available
    def test_expiry_protects_active_requests(self):
        with patch('surrogate_aligner.runs.time.monotonic', return_value=0):
            idle = self.store.create()
            active = self.store.create()
            lease = self.store.acquire(active.name)
        with patch('surrogate_aligner.runs.time.monotonic', return_value=101):
            self.store.expire()
            self.assertFalse(idle.exists())
            self.assertTrue(active.exists())
            lease.close()
        with patch('surrogate_aligner.runs.time.monotonic', return_value=202):
            self.store.expire()
            self.assertFalse(active.exists())

    # Explicit abandonment waits for all operations to finish using the files
    def test_discard_defers_until_request_finishes(self):
        path = self.store.create()
        lease = self.store.acquire(path.name)
        self.store.discard(path.name)
        self.assertTrue(path.exists())
        with self.assertRaises(KeyError):
            self.store.acquire(path.name)
        lease.close()
        lease.close()
        self.assertFalse(path.exists())

    # Shutdown removes owned uploads but never scans or deletes unrelated temporary folders
    def test_close_removes_only_owned_runs(self):
        owned = self.store.create()
        unrelated = Path(self.directory.name) / 'surrogate-aligner-unrelated'
        unrelated.mkdir()
        self.store.close()
        self.assertFalse(owned.exists())
        self.assertTrue(unrelated.exists())
        self.assertFalse(self.store._thread.is_alive())
        with self.assertRaises(RuntimeError):
            self.store.create()


if __name__ == '__main__':
    unittest.main()
