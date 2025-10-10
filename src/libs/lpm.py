import pm


class WakeLock(object):

    def __init__(self, name):
        self.__name = name
        self.__lock_ident = pm.create_wakelock(name, len(name))
        if self.__lock_ident == -1:
            raise ValueError("create wake lock failed!")

    def __enter__(self):
        self.acquire()

    def __exit__(self, *args, **kwargs):
        self.release()

    def acquire(self):
        return pm.wakelock_lock(self.__lock_ident) == 0

    def release(self):
        return pm.wakelock_unlock(self.__lock_ident) == 0

    def destroy(self):
        return pm.delete_wakelock(self.__lock_ident) == 0

    @classmethod
    def counts(cls):
        return pm.get_wakelock_num()


def auto_sleep(flag=True):
    return pm.autosleep(int(flag)) == 0


class Psm(object):

    @classmethod
    def set_mode(cls, mode):
        return pm.set_psm_time(mode)

    @classmethod
    def get_mode(cls):
        return pm.get_psm_time()[0]

    @classmethod
    def set_time(cls, tau_hours=2, act_minutes=4):
        return pm.set_psm_time(1, tau_hours, 1, act_minutes)

    @classmethod
    def get_time(cls):
        temp = pm.get_psm_time()
        return temp[2], temp[4]
