import ql_fs
import usocket
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


class Singleton(object):
    """单例模式"""

    def __init__(self, cls):
        self.cls = cls
        self.instance = None

    def __call__(self, *args, **kwargs):
        if self.instance is None:
            self.instance = self.cls(*args, **kwargs)
        return self.instance

    def __repr__(self):
        return repr(self.cls)


class _Node(object):
    """链表节点"""

    def __init__(self, obj, next_=None, prev=None):
        self.obj = obj
        self.next = next_
        self.prev = prev

    def __repr__(self):
        return "{}(obj={})".format(type(self).__name__, repr(self.obj))


class DoublyLinkedList(object):
    """双向链表"""

    def __init__(self):
        self.__root = _Node(None)
        self.__root.next = self.__root
        self.__root.prev = self.__root

    def __iter__(self):
        curr = self.__root.next
        while curr != self.__root:
            yield curr
            curr = curr.next

    def __len__(self):
        result = 0
        for _ in self:
            result += 1
        return result

    def is_empty(self):
        return self.__root.next is None

    def add(self, obj):
        node = _Node(obj, next_=self.__root.next, prev=self.__root)
        self.__root.next.prev = node
        self.__root.next = node

    def append(self, obj):
        node = _Node(obj, next_=self.__root, prev=self.__root.prev)
        self.__root.prev.next = node
        self.__root.prev = node

    def insert(self, obj, base):
        pos = self.search(base)
        if pos is None:
            raise ValueError("{} not in list".format(base))
        node = _Node(obj, next_=pos, prev=pos.prev)
        pos.prev.next = node
        pos.prev = node

    def search(self, obj):
        for node in self:
            if node.obj == obj:
                return node

    def remove(self, obj):
        node = self.search(obj)
        if node is None:
            raise ValueError("{} not in list".format(obj))
        node.prev.next = node.next
        node.next.prev = node.prev


class OrderedDict(object):
    """有序字典"""

    def __init__(self, iterable=None):
        self.__keys_linked_list = DoublyLinkedList()
        self.__key_node_map = {}
        self.__storage = {}
        if isinstance(iterable, (tuple, list)):
            self.__load(iterable)

    def __load(self, sequence):
        for k, v in sequence:
            self[k] = v

    def __repr__(self):
        return "{}({})".format(type(self).__name__, [(k, v) for k, v in self.items()])

    def __iter__(self):
        return (node.obj for node in self.__keys_linked_list)

    def __setitem__(self, key, value):
        if key not in self.__storage:
            self.__key_node_map[key] = self.__keys_linked_list.append(key)
        self.__storage[key] = value

    def __getitem__(self, item):
        return self.__storage[item]

    def __delitem__(self, key):
        del self.__storage[key]
        node = self.__key_node_map.pop(key)
        node.prev.next = node.next
        node.next.prev = node.prev

    def keys(self):
        return iter(self)

    def values(self):
        return (self.__storage[key] for key in self)

    def items(self):
        return ((k, self.__storage[k]) for k in self)

    def get(self, key, default=None):
        if key not in self.__storage:
            return default
        return self.__storage[key]

    def pop(self, key, default=None):
        if key not in self.__storage:
            return default
        temp = self[key]
        del self[key]
        return temp

    def update(self, obj):
        for k, v in obj.items():
            self[k] = v

    def setdefault(self, key, value):
        if key in self.__storage:
            return self[key]
        else:
            self[key] = value
            return value


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

    def from_json(self, path):
        """warning: this method will overwrite the data"""
        with self.__lock:
            self.__data.update(ql_fs.read_json(path) or {})
