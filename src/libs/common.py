import ql_fs
import ujson as json
from .threading import Lock


def deepcopy(obj):
    """深拷贝"""
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    if isinstance(obj, (list, tuple, set)):
        return type(obj)((deepcopy(item) for item in obj))
    elif isinstance(obj, dict):
        return {k: deepcopy(v) for k, v in obj.items()}
    else:
        raise TypeError("unsupported for \"{}\" type".format(type(obj)))


class Database(object):
    """基础持久化配置类，类属性通常为配置常量，提供用户配置参数读写和持久化"""

    def __init__(self, path="/usr/system.json"):
        self.__lock = Lock()
        self.__data = {}
        self.__path = path
        if not ql_fs.path_exists(self.__path):
            ql_fs.touch(self.__path, self.__data)
        else:
            self.from_json(self.__path)
    
    def __repr__(self):
        return json.dumps(self.__data)

    def all(self):
        with self.__lock:
            return deepcopy(self.__data)

    def get(self, *keys):
        with self.__lock:
            if len(keys) == 1:
                return deepcopy(self.__data.get(keys[0]))
            return deepcopy(tuple(self.__data.get(key) for key in keys))
    
    def pop(self, *keys):
        with self.__lock:
            if len(keys) == 1:
                return deepcopy(self.__data.pop(keys[0]))
            return deepcopy(tuple(self.__data.pop(key) for key in keys))

    def delete(self, *keys):
        with self.__lock:
            for key in (_ for _ in keys if _ in self.__data):
                del self.__data[key]
        return self

    def set(self, key, value):
        with self.__lock:
            self.__data[key] = value
        return self
    
    def setdefault(self, key, value):
        with self.__lock:
            if key not in self.__data:
                self.__data[key] = value
            return deepcopy(self.__data[key])

    def update(self, **kwargs):
        with self.__lock:
            self.__data.update(**kwargs)
        return self

    def save(self):
        with self.__lock:
            ql_fs.touch(self.__path, self.__data)

    def from_json(cls, path):
        """warning: this method will overwrite the data"""
        with cls.__lock:
            cls.__data.update(ql_fs.read_json(path) or {})


