# 导入相关库
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import RPi.GPIO
from homeassistant.helpers.event import track_time_interval
from datetime import timedelta
import RPi.GPIO

# 设置GPIO的端口，配置PWN频率。
RPi.GPIO.setwarnings(False)
RPi.GPIO.setmode(RPi.GPIO.BCM)
RPi.GPIO.setup(2, RPi.GPIO.OUT)
pwm = RPi.GPIO.PWM(2, 100)
RPi.GPIO.setwarnings(False)
pwm.start(0)

# 配置风扇卡的相关参数
DOMAIN = "rpifan"
MODEID = DOMAIN + ".mode"
STATUSID = DOMAIN + ".status"
# 在python中，__name__代表模块名字
_LOGGER = logging.getLogger(__name__)
 
# 预定义配置文件中的key值
CONF_START_TEMP = "start_temp"
CONF_STOP_TEMP = "stop_temp"

# 预定义缺省的配置值
DEFAULT_START_TEMP = 50
DEFAULT_STOP_TEMP = 40

# 预定义风扇状态值
CONTROLMODE = ['auto' ,'stop' ,'start']

# 预定义cpu温度
cpu_temp = 0
max_temp = 0
min_temp = 100000

# 检查配置文件中的值
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                # vol.Optional配置文件中是可以不配置，vol.Required表示是必须存在的，否则报错，cv.string为字符串，cv.positive_int为整数
                vol.Optional(CONF_START_TEMP, default=DEFAULT_START_TEMP): cv.positive_int,
				vol.Optional(CONF_STOP_TEMP, default=DEFAULT_STOP_TEMP): cv.positive_int,
            }),
    },
    extra=vol.ALLOW_EXTRA)

# 默认刷新的时间间隔为5秒。修改数字5即可
REFRESHTIME = timedelta(seconds=5) 

# 创建获取cpu温度的函数
def getcputem():
    global max_temp , min_temp
    tmpFile = open('/sys/class/thermal/thermal_zone0/temp')
    cpu_temp = int(tmpFile.read())
    tmpFile.close() 
    if cpu_temp > max_temp:
       max_temp = cpu_temp
    if cpu_temp < min_temp:
       min_temp = cpu_temp
    return cpu_temp , max_temp, min_temp
 
def setup(hass, config):
    """配置文件加载后，setup被系统调用."""
    # config[DOMAIN]代表这个域下的配置信息
    conf = config[DOMAIN]
	# 获得具体配置项信息
    starttemp = conf.get(CONF_START_TEMP)
    stoptemp = conf.get(CONF_STOP_TEMP)   
  
	# 配置风扇的属性     
    modeattr = {"icon": "mdi:hand-pointing-right",
            "friendly_name": "风扇模式", }
    statusattr = {"icon": "mdi:fan",
            "friendly_name": "风扇转速",
            "unit_of_measurement": "%" ,
            "CPU实时温度": "0 ℃",
            "CPU最高温度": "0 ℃",
            "CPU最低温度": "0 ℃",}
            
	# 创建风扇模式     
    hass.states.set(MODEID, CONTROLMODE[0], attributes=modeattr)    
    
    #引入一个显示风扇状态的类
    rpifanstatus(hass,starttemp,stoptemp,statusattr)    

	# 创建风扇模式的service动作    
    def control_auto(call):
        # 切换风扇模式的状态值
        _LOGGER.info("rpifan control_auto service is called.")
        hass.states.set(MODEID, CONTROLMODE[0], attributes=modeattr)        
    def control_stop(call):
        # 切换风扇模式,停止风扇并写入状态
        _LOGGER.info("rpifan control_stop service is called.rpifan's speed is 0")
        pwm.ChangeDutyCycle(0)        
        hass.states.set(MODEID, CONTROLMODE[1], attributes=modeattr)
        statusattr['icon'] = "mdi:fan-off"
        gcpu_temp ,gmax_temp ,gmin_temp = getcputem()
        statusattr['CPU实时温度'] = str(round(gcpu_temp/1000,2)) +" ℃"
        statusattr['CPU最高温度'] = str(round(gmax_temp/1000,2)) +" ℃"
        statusattr['CPU最低温度'] = str(round(gmin_temp/1000,2)) +" ℃"
        hass.states.set(STATUSID, 0, attributes=statusattr)        
    def control_start(call):
        # 切换风扇模式,启动风扇并写入状态
        _LOGGER.info("rpifan control_start service is called,rpifan's speed is 100.")
        pwm.ChangeDutyCycle(100)
        hass.states.set(MODEID, CONTROLMODE[2], attributes=modeattr)
        statusattr['icon'] = "mdi:fan"
        gcpu_temp ,gmax_temp ,gmin_temp = getcputem()
        statusattr['CPU实时温度'] = str(round(gcpu_temp/1000,2)) +" ℃"
        statusattr['CPU最高温度'] = str(round(gmax_temp/1000,2)) +" ℃"
        statusattr['CPU最低温度'] = str(round(gmin_temp/1000,2)) +" ℃"
        hass.states.set(STATUSID, 100, attributes=statusattr)
        
    # 注册风扇模式的服务
    hass.services.register(DOMAIN, 'control_auto', control_auto)
    hass.services.register(DOMAIN, 'control_stop', control_stop)
    hass.services.register(DOMAIN, 'control_start', control_start) 
    
    
    return True
    
#创建一个风扇状态的类    
class rpifanstatus(object):
    #初始化风扇状态类的参数 
    def __init__(self, hass , starttemp, stoptemp, statusattr):    
        self._hass = hass
        self._starttemp = starttemp*1000
        self._stoptemp = stoptemp*1000
        self._statusattr = statusattr
        self._state = 0
        self._check = 9

    #创建初始化的风扇状态
        self._hass.states.set(STATUSID, self._state, attributes=self._statusattr)
    #设置刷新时间的动作
        track_time_interval(self._hass, self.update, REFRESHTIME)
    #刷新时的动作  
    def update(self, now):
        """在rpifanstatus类中定义函数update,更新状态.""" 
        cpu_temp,max_temp,min_temp = getcputem()
        #获取操作模式
        self._check = self._check + 1
        modecheck = self._hass.states.get(MODEID).state
        _LOGGER.info("rpifan's mode is " + modecheck + ",CPU's temperature is " + str(cpu_temp/1000)+",max temp is "+ str(max_temp/1000)+",min temp is "+ str(min_temp/1000))    
        if modecheck == CONTROLMODE[0]:            
            if cpu_temp>=self._starttemp :
                if cpu_temp>self._starttemp+10000 :  
                        speed = 100
                else :                        
                        speed = int(((cpu_temp - self._stoptemp) / (self._starttemp - self._stoptemp + 10000))*80 + 20)
            elif cpu_temp>=self._stoptemp :
                if self._hass.states.get(STATUSID).state == "0" :
                        speed = 0 
                else :
                        speed = int(((cpu_temp - self._stoptemp) / (self._starttemp - self._stoptemp + 10000))*80 + 20)
            else :
              speed = 0
            pwm.ChangeDutyCycle(speed)            
        elif modecheck == CONTROLMODE[1]:
           speed = 0
        else:
           speed = 100
        # 写入新的风扇状态
        self._state = speed
        if speed == 0:
           if self._check >= 10:       
                _LOGGER.info("writing the rpifan's state,rpifan's speed is 0")
                self._check = 0
                self._hass.states.set(STATUSID, self._state, attributes={"icon": "mdi:fan-off",
                                                                          "friendly_name": "风扇转速",
                                                                          "unit_of_measurement": "%" ,
                                                                          "CPU实时温度": str(round((cpu_temp/1000),2)) + " ℃",
                                                                          "CPU最高温度": str(round((max_temp/1000),2)) + " ℃",
                                                                          "CPU最低温度": str(round((min_temp/1000),2)) + " ℃",})
           else:
                _LOGGER.info("waiting for writing the rpifan's status--->  0%>>>>>>>>>>>> " + str(10 - self._check))
        elif speed == 100:
           if self._check >= 10:
                _LOGGER.info("writing the rpifan's state,rpifan's speed is 100")
                self._check = 0
                self._hass.states.set(STATUSID, self._state, attributes={"icon": "mdi:fan",
                                                                          "friendly_name": "风扇转速",
                                                                          "unit_of_measurement": "%" ,
                                                                          "CPU实时温度": str(round((cpu_temp/1000),2)) + " ℃",
                                                                          "CPU最高温度": str(round((max_temp/1000),2)) + " ℃",
                                                                          "CPU最低温度": str(round((min_temp/1000),2)) + " ℃",})
           else:
                _LOGGER.info("waiting for writing the rpifan's status--->100%>>>>>>>>>>>> " + str(10 - self._check))
        else :
           _LOGGER.info("writing the rpifan's state,rpifan's speed is " + str(speed))
           self._check = 9
           self._statusattr['icon'] = "mdi:fan"
           self._statusattr['CPU实时温度'] = str(round(cpu_temp/1000,2)) + " ℃"
           self._statusattr['CPU最高温度'] = str(round(max_temp/1000,2)) + " ℃"
           self._statusattr['CPU最低温度'] = str(round(min_temp/1000,2)) + " ℃"
           self._hass.states.set(STATUSID, self._state, attributes=self._statusattr)




