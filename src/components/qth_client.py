from usr.libs import CurrentApp
from usr.libs.qth import qth_init, qth_config, qth_bus
from usr.libs.logging import getLogger
from usr.configure import settings


logger = getLogger(__name__)


class QthClient(object):

    def init(self):
        logger.info("init {} extension".format(type(self).__name__))
        qth_init.init()
        qth_config.setServer(settings.QTH_SERVER)
        qth_config.setProductInfo(settings.PRODUCT_KEY, settings.PRODUCT_SECRET)
        qth_config.setEventCb(
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
        qth_init.start()
    
    def event_cb(self, event, result):
        logger.debug('dev event: {} result: {}'.format(event, result))

    def recv_trans_cb(self, value):
        ret = qth_bus.sendTrans(1, value)
        logger.debug('recvTrans value: {} ret: {}'.format(value, ret))
    
    def recv_tsl_cb(self, value):

        # logger.debug('recvTsl:{}'.format(value))
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
        logger.debug('readTsl ids: {} pkgId: {}'.format(ids, pkgId))
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
        qth_bus.ackTsl(1, value, pkgId)

    def recv_tsl_server_cb(self, serverId, value, pkgId):
        logger.debug('recvTslServer serverId:{} value:{} pkgId:{}'.format(serverId, value, pkgId))
        qth_bus.ackTslServer(1, serverId, value, pkgId)

    def ota_plan_cb(self, plans):
        logger.debug('otaPlan:{}'.format(plans))

    def fota_result_cb(self, comp_no, result):
        logger.debug('fotaResult comp_no:{} result:{}'.format(comp_no, result))

    def App_sotaInfoCb(self, comp_no, version, url,fileSize, md5, crc):   # fileSize是可选参数
        logger.debug('sotaInfo comp_no:{} version:{} url:{} fileSize:{} md5:{} crc:{}'.format(comp_no, version, url,fileSize, md5, crc))
        # 当使用url下载固件完成，且MCU更新完毕后，需要获取MCU最新的版本信息，并通过setMcuVer进行更新

    def App_sotaResultCb(self, comp_no, result):
        logger.debug('sotaResult comp_no:{} result:{}'.format(comp_no, result))
