from usr.libs import CurrentApp
from usr.libs.logging import getLogger
from usr.configure import settings
from . import Qth


logger = getLogger(__name__)


class QthClient(object):

    def init(self):
        logger.info("init {} extension".format(type(self).__name__))
        Qth.init()
        Qth.setProductInfo(settings.PRODUCT_KEY, settings.PRODUCT_SECRET)
        Qth.setServer(settings.QTH_SERVER)
        Qth.setAppVer(settings.get_version(), self.app_ota_result_cb)
        Qth.setEventCb(
            {
                'devEvent': self.event_cb, 
                'recvTrans': self.recv_trans_cb,
                'recvTsl': self.recv_tsl_cb, 
                'readTsl': self.read_tsl_cb, 
                'readTslServer': self.recv_tsl_server_cb,
                'ota': {
                    'otaPlan': self.ota_plan_cb,
                    'fotaResult': self.fota_result_cb
                }
            }
        )
        Qth.start()
    
    def event_cb(self, event, result):
        logger.debug('event_cb event: {} result: {}'.format(event, result))

    def recv_trans_cb(self, value):
        ret = Qth.sendTrans(1, value)
        logger.debug('recv_trans_cb value: {} ret: {}'.format(value, ret))
    
    def recv_tsl_cb(self, value):
        # logger.debug('recv_tsl_cb: {}'.format(value))
        for cmdId, val in value.items():
            if cmdId == 4:
                logger.debug("调节音量: {}".format(val))
                CurrentApp().audio_manager.aud.setVolume(val)
            if cmdId == 3:
                logger.debug("设置唤醒词为：{}".format(val[0][1]))
                settings.update(
                    DISPLAY_TEXT=val[0][1],
                    WAKEUP_KEYWORD=val[0][2]
                )
                CurrentApp().protocol.disconnect()
            if cmdId == 6:
                logger.debug("开关：{}".format(val))
            if cmdId == 11:
                logger.debug("智能体参数设置: {}".format(val))
            if cmdId == 13:
                logger.debug("AI 接入方式：{}".format(val))
            if cmdId == 10:
                logger.debug("音乐播放地址: {}".format(val))
                CurrentApp().audio_manager.play_music(val)
            if cmdId == 7:
                logger.debug("聊天模式：{}".format(val))
            if cmdId == 5:
                logger.debug("设备模式: {}".format(val))
            if cmdId == 1:
                logger.debug("设备重新进入聊天：{}".format(val))
            else:
                pass

    def read_tsl_cb(self, ids, pkgId):
        logger.debug('read_tsl_cb ids: {} pkgId: {}'.format(ids, pkgId))
        value=dict()
        for id in ids:
            if id == 1:
                logger.debug("设备重新进入聊天")
            elif id == 2:
                logger.debug("设备重新进入聊天结果")
                value[2] = True
            elif id == 3:
                logger.debug("唤醒词")
                value[3] = [{1: settings.get("DISPLAY_TEXT"), 2: settings.get("WAKEUP_KEYWORD")}]
            elif id == 4:
                logger.debug("音量")
            elif id == 5:
                logger.debug("设备模式")
                value[5] = 1
            elif id == 6:
                logger.debug("开关")
            elif id == 7:
                logger.debug("聊天模式")
                value[7] = 1
            elif id == 8:
                logger.debug("电量")
                value[8] = 90
            elif id == 9:
                logger.debug("充电状态")
                value[9] = 1
            elif id == 10:
                logger.debug("音乐播放地址")
            elif id == 13:
                logger.debug("AI接入方式")
                value[13] = 1
            elif id == 14:
                logger.debug("语音检测模式")
                value[14] = 1
            else:
                pass
        Qth.ackTsl(1, value, pkgId)

    def recv_tsl_server_cb(self, serverId, value, pkgId):
        logger.debug('recv_tsl_server_cb serverId:{} value:{} pkgId:{}'.format(serverId, value, pkgId))
        Qth.ackTslServer(1, serverId, value, pkgId)

    def ota_plan_cb(self, plans):
        """[(组件类型,组件标识,源版本,目标版本,Ota升级最小电量,ota升级需要磁盘空间,Ota升级最小信号强度),]"""
        # [(1, 'appota', None, '2.0.0', 30, 25988, -113)]
        # [(0, 'fota', None, 'EC800MCNLER01A03M08_OCPU_QPY_TEST0813', 30, 11855635, -113)]
        logger.debug('ota_plan_cb: {}'.format(plans))
        Qth.otaAction(1)

    def fota_result_cb(self, comp_no, result):
        logger.debug('fota_result_cb comp_no:{} result:{}'.format(comp_no, result))

    def app_ota_result_cb(self, comp_no, result):
        logger.debug('app_sota_result_cb comp_no:{} result:{}'.format(comp_no, result))
