from usr.libs.logging import getLogger
from usr.libs.qth import qth_init, qth_config, qth_bus


logger = getLogger(__name__)


class QthClient(object):

    @classmethod
    def init(cls, pk, ps):
        qth_init.init()
        qth_config.setProductInfo(pk, ps)
        qth_config.setEventCb(
            {
                'devEvent':cls.event_cb, 
                'recvTrans':cls.recv_trans_cb,
                'recvTsl':cls.recv_tsl_cb, 
                'readTsl':cls.read_tsl_cb, 
                'readTslServer':cls.recv_tsl_server_cb,
                'ota': {
                    'otaPlan':cls.ota_plan_cb,
                    'fotaResult':cls.fota_result_cb
                }
            }
        )

    @classmethod
    def start(cls):
        qth_init.start()

    @classmethod
    def event_cb(cls, event, result):
        logger.debug('dev event:{} result:{}'.format(event, result))

    @classmethod
    def recv_trans_cb(cls, value):
        ret = qth_bus.sendTrans(1, value)
        logger.debug('recvTrans value:{} ret:{}'.format(value, ret))

    @classmethod
    def recv_tsl_cb(cls, value):
        logger.debug('recvTsl:{}'.format(value))
        for cmdId, val in value.items():
            if cmdId == 4:
                logger.debug("调节音量: {}".format(val))
            else:
                pass

    @classmethod
    def read_tsl_cb(cls, ids, pkgId):
        logger.debug('readTsl ids:{} pkgId:{}'.format(ids, pkgId))
        value=dict()
        for id in ids:
            if 1 == id:
                value[1]=180.25
            elif 2 == id:
                value[2]=30
            elif 3 == id:
                value[3]=True
        qth_bus.ackTsl(1, value, pkgId)

    @classmethod
    def recv_tsl_server_cb(cls, serverId, value, pkgId):
        logger.debug('recvTslServer serverId:{} value:{} pkgId:{}'.format(serverId, value, pkgId))
        qth_bus.ackTslServer(1, serverId, value, pkgId)

    @classmethod
    def ota_plan_cb(cls, plans):
        logger.debug('otaPlan:{}'.format(plans))

    @classmethod
    def fota_result_cb(cls, comp_no, result):
        logger.debug('fotaResult comp_no:{} result:{}'.format(comp_no, result))

    @classmethod
    def App_sotaInfoCb(cls, comp_no, version, url,fileSize, md5, crc):   # fileSize是可选参数
        logger.debug('sotaInfo comp_no:{} version:{} url:{} fileSize:{} md5:{} crc:{}'.format(comp_no, version, url,fileSize, md5, crc))
        # 当使用url下载固件完成，且MCU更新完毕后，需要获取MCU最新的版本信息，并通过setMcuVer进行更新

    @classmethod
    def App_sotaResultCb(cls, comp_no, result):
        logger.debug('sotaResult comp_no:{} result:{}'.format(comp_no, result))
