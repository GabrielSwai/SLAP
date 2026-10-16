# =====================================================================================
# Surrogate Language Alignment Program
#
# Own temporary uploads, protect active requests, and expire abandoned analyses.
# =====================================================================================

from pathlib import Path
import shutil
import tempfile
from threading import Event, RLock, Thread
import time


# Class:        RunLease
# Description:  Keeps an upload alive until its current request or save operation finishes.

class RunLease:
    def __init__(self, store, run_id, path):
        self.path = path
        self._store = store
        self._run_id = run_id
        self._closed = False

    def close(self):
        if not self._closed:
            self._closed = True
            self._store.release(self._run_id)


# Class:        RunStore
# Description:  Tracks only uploads created by this process, with inactivity expiry.

class RunStore:
    def __init__(self, ttl_seconds=86400):
        self.ttl_seconds = ttl_seconds
        self._runs = {}
        self._lock = RLock()
        self._stop = Event()
        self._thread = None
        self._closed = False

    # Function:     create
    # Inputs:       None
    # Outputs:      path | new owned upload directory (Path)
    # Description:  Starts the expiry worker and records a new temporary upload.

    def create(self):
        with self._lock:
            if self._closed:
                raise RuntimeError('SLAP is shutting down.')
            path = Path(tempfile.mkdtemp(prefix='surrogate-aligner-'))
            self._runs[path.name] = {'path': path, 'used': time.monotonic(), 'active': 0, 'deleted': False}
            if self._thread is None:
                self._thread = Thread(target=self._expire_loop, name='slap-expiry', daemon=True)
                self._thread.start()
            return path

    # Function:     acquire
    # Inputs:       run_id | owned upload identifier (str)
    # Outputs:      lease | handle protecting the upload during processing (RunLease)
    # Description:  Rejects removed or expired runs and extends the inactivity deadline.

    def acquire(self, run_id):
        with self._lock:
            record = self._runs.get(run_id)
            if (self._closed or record is None or record['deleted']
                    or (not record['active'] and time.monotonic() - record['used'] >= self.ttl_seconds)):
                if record is not None:
                    self.discard(run_id)
                raise KeyError(run_id)
            record['active'] += 1
            record['used'] = time.monotonic()
            return RunLease(self, run_id, record['path'])

    # Function:     release
    # Inputs:       run_id | owned upload identifier (str)
    # Outputs:      None
    # Description:  Releases an active request and completes any deferred deletion.

    def release(self, run_id):
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                return
            record['active'] -= 1
            record['used'] = time.monotonic()
            if record['deleted'] and not record['active']:
                shutil.rmtree(record['path'], ignore_errors=True)
                del self._runs[run_id]

    # Function:     discard
    # Inputs:       run_id | owned upload identifier (str)
    # Outputs:      None
    # Description:  Removes idle uploads immediately and defers deletion of busy uploads.

    def discard(self, run_id):
        with self._lock:
            record = self._runs.get(run_id)
            if record is not None:
                record['deleted'] = True
                if not record['active']:
                    shutil.rmtree(record['path'], ignore_errors=True)
                    del self._runs[run_id]

    # Function:     expire
    # Inputs:       None
    # Outputs:      None
    # Description:  Removes inactive uploads whose retention period has elapsed.

    def expire(self):
        with self._lock:
            for run_id, record in list(self._runs.items()):
                if not record['active'] and time.monotonic() - record['used'] >= self.ttl_seconds:
                    self.discard(run_id)

    def _expire_loop(self):
        # Wake periodically without keeping the application alive after shutdown
        while not self._stop.wait(min(300, max(1, self.ttl_seconds))):
            self.expire()

    # Function:     close
    # Inputs:       None
    # Outputs:      None
    # Description:  Stops expiry and removes this process's temporary uploads at shutdown.

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        with self._lock:
            self._closed = True
            for record in self._runs.values():
                shutil.rmtree(record['path'], ignore_errors=True)
            self._runs.clear()
