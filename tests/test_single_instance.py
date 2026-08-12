from yida_ai.system.single_instance import SingleInstanceLock, run_single_instance


class FakeLock:
    def __init__(self, acquired):
        self.acquired = acquired
        self.closed = 0

    def acquire(self):
        return self.acquired

    def close(self):
        self.closed += 1


def test_second_instance_is_rejected_without_running_callback():
    lock = FakeLock(False)
    calls = []
    acquired, code = run_single_instance(lambda: calls.append(True), lock=lock)
    assert not acquired
    assert code == 2
    assert calls == []
    assert lock.closed == 1


def test_single_instance_releases_lock_after_callback():
    lock = FakeLock(True)
    acquired, code = run_single_instance(lambda: 7, lock=lock)
    assert acquired
    assert code == 7
    assert lock.closed == 1


class FakeWindowsApi:
    def __init__(self, handle, last_error):
        self.handle = handle
        self.last_error = last_error
        self.closed = []

    def CreateMutexW(self, *_args):
        return self.handle

    def GetLastError(self):
        return self.last_error

    def CloseHandle(self, handle):
        self.closed.append(handle)


def test_windows_mutex_detects_existing_instance_and_closes_handle():
    api = FakeWindowsApi(123, 183)
    lock = SingleInstanceLock(windows_api=api)
    assert not lock.acquire()
    lock.close()
    assert api.closed == [123]


def test_windows_mutex_handles_creation_failure():
    lock = SingleInstanceLock(windows_api=FakeWindowsApi(0, 0))
    assert not lock.acquire()
    lock.close()
