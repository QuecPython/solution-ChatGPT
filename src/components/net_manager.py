import sim
import net
import utime
import checkNet
import dataCall
from misc import Power
from usr.libs.logging import getLogger
from usr.libs.threading import Thread


logger = getLogger(__name__)


class NetManager(object):

    def __init__(self):
        self.callback_handlers = {}

    def init(self):
        logger.info("init NetManager extension")
        self.active_sim_hot_swap()
        self.active_net_callback()
        self.wait_network_ready()

    def active_sim_hot_swap(self):
        try:
            trigger_level = 0
            if sim.setSimDet(1, trigger_level) != 0:
                logger.warn("active sim switch failed.")
            else:
                logger.debug("active sim switch success.")
                if sim.setCallback(self.__sim_callback) != 0:
                    logger.warn("register sim switch callback failed.")
                else:
                    logger.debug("register sim switch callback success.")
        except Exception as e:
            logger.error("sim check init failed: {}".format(e))
        else:
            logger.debug("sim check init success.")

    def active_net_callback(self):
        try:
            if dataCall.setCallback(self.__net_callback) != 0:
                logger.warn("register data callback failed.")
            else:
                logger.debug("register data callback success.")
        except Exception as e:
            logger.warn("net check init failed: {}".format(e))
        else:
            logger.debug("net check init success.")

    @staticmethod
    def make_cfun():
        net.setModemFun(0, 0)
        utime.sleep_ms(200)
        net.setModemFun(1, 0)

    def wait_network_ready(self):
        for _ in range(3):
            logger.info("wait network ready...")
            code = checkNet.waitNetworkReady(60)
            if code == (3, 1):
                logger.info("network has been ready.")
                break
            else:
                logger.warn("network not ready, code: {}".format(code))
                self.make_cfun()
        else:
            logger.warn("power restart")
            Power.powerRestart()

    def __net_callback(self, args):
        # WARN: Do not write time-consuming or blocking code here
        logger.info("net_callback get args: {}".format(args))
        handlers = self.callback_handlers.setdefault("net", [])
        for handler in handlers:
            Thread(target=handler, args=(args,)).start()
        if args[1] == 0:
            Thread(target=self.wait_network_ready).start()

    def register_net_callback(self, fn):
        handlers = self.callback_handlers.setdefault("net", [])
        handlers.append(fn)
        return fn

    def __sim_callback(self, state):
        # WARN: Do not write time-consuming or blocking code here
        logger.info("sim_callback get state: {}".format(state))
        handlers = self.callback_handlers.setdefault("sim", [])
        for handler in handlers:
            Thread(target=handler, args=(state,)).start()

    def register_sim_callback(self, fn):
        handlers = self.callback_handlers.setdefault("sim", [])
        handlers.append(fn)
        return fn

    def set_apn(self, apn, username, password):
        # 获取第一路的APN信息，确认当前使用的是否是用户指定的APN
        pdpCtx = dataCall.getPDPContext(1)
        if pdpCtx != -1:
            if pdpCtx[1] != apn:
                # 如果不是用户需要的APN，使用如下方式配置
                ret = dataCall.setPDPContext(1, 0, apn, username, password, 0)
                if ret != 0:
                    raise ValueError("APN set failed")
            else:
                raise ValueError("APN already set")
        else:
            raise ValueError("get PDP Context failed")
