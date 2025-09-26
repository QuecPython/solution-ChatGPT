import sys
import net
import sim
import modem
from misc import Power
from .common import OrderedDict, Singleton, deepcopy
from .threading import Lock


@Singleton
class _AppCtxGlobals(object):
    __lock__ = Lock()

    def __init__(self):
        self.__data = {}

    def setdefault(self, name, value):
        with self.__lock__:
            return deepcopy(self.__data.setdefault(name, value))

    def get(self, name, default=None):
        with self.__lock__:
            return deepcopy(self.__data.get(name, default))

    def set(self, name, value):
        with self.__lock__:
            self.__data[name] = deepcopy(value)

    def update(self, kwargs):
        with self.__lock__:
            return self.__data.update(kwargs)


G = _AppCtxGlobals


@Singleton
class Application(object):
    """Application Class"""

    def __init__(self, name, version='1.0.0'):
        self.__name = name
        self.__version = version
        self.__components = OrderedDict()

    def __repr__(self):
        return '{}(name=\"{}\", version=\"{}\")'.format(type(self).__name__, self.name, self.version)

    def __getattr__(self, name):
        return self.__components[name]

    def register(self, name, ext):
        if name in self.__components:
            raise ValueError('extension name \"{}\" already in use'.format(name))
        self.__components[name] = ext

    def __power_on_print_once(self):
        output = '==================================================\r\n'
        output += 'APP_NAME         : {}\r\n'
        output += 'APP_VERSION      : {}\r\n'
        output += 'FIRMWARE_VERSION : {}\r\n'
        output += 'POWERON_REASON   : {}\r\n'
        output += 'DEVICE_IMEI      : {}\r\n'
        output += 'SIM_STATUS       : {}\r\n'
        output += 'NET_STATUS       : {}\r\n'
        output += '=================================================='
        print(output.format(
            self.name,
            self.version,
            modem.getDevFwVersion(),
            Power.powerOnReason(),
            modem.getDevImei(),
            sim.getStatus(),
            net.getState()[1][0]
        ))

    def __load_extensions(self):
        for ext in self.__components.values():
            if not hasattr(ext, 'init'):
                continue
            try:
                ext.init()
            except Exception as e:
                sys.print_exception(e)

    def run(self):
        self.__power_on_print_once()
        self.__load_extensions()

    @property
    def version(self):
        return self.__version

    @property
    def name(self):
        return self.__name


CurrentApp = Application
