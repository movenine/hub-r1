#!/usr/bin/python3
## Author: Dustin Lee
## Date: 2023.12.10
## Company: Cudo Communication
## This is a functional testing code for a processor unit of Hub board
## Feature : monitoring task loutine

import sys, os, time, syslog
import pandas as pd
# import wiringpi
# from wiringpi import GPIO
from dataclasses import dataclass

sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from lib.ethernet import *
from lib.database import *
from lib.pio import *
from lib.protocol import *

## ---------------- 클래스 ---------------- ##
@dataclass
class hubdata:
    _serverid: int
    _clientid: int    
    _power: float
    _signal: int
    _powerstatus: int
    _opMode: int

    @property
    def serverid(self): return self._serverid
    @serverid.setter
    def serverid(self, value): self._serverid = value

    @property
    def clientid(self): return self._clientid
    @clientid.setter
    def clientid(self, value): self._clientid = value

    @property
    def power(self): return self._power
    @power.setter
    def power(self, value): self._power = value

    @property
    def signal(self): return self._signal
    @signal.setter
    def signal(self, value): self._signal = value

    @property
    def powerstatus(self): return self._powerstatus
    @powerstatus.setter
    def powerstatus(self, value): self._powerstatus = value

    @property
    def opMode(self): return self._opMode
    @opMode.setter
    def opMode(self, value): self._opMode = value

    def getDict(self):
        dic = dict()
        dic['serverId'] = [self.serverid, ]
        dic['clientId'] = [self.clientid, ]
        dic['power'] = [self.power, ]
        dic['signal'] = [self.signal, ]
        dic['powerStatus'] = [self.powerstatus, ]
        return dic
    
## ---------------- 클래스 인스턴스 ---------------- ##
hubDatas = hubdata(_serverid= 0x0,
               _clientid= 0x0,
               _power= 0.0,
               _signal= 0,
               _powerstatus= 0,
               _opMode=0)

db_data = SqlLib(filename=db_file_path, table=SQL_PARAMETER.DATA_TABLE)
db_cmdTable = SqlLib(filename=db_file_path, table=SQL_PARAMETER.CMD_TABLE)
## ---------------- 콜백 ---------------- ##

## ---------------- 서브루틴 ---------------- ##
def get_signal_status(pioData: dict) -> int:
    '''
    영상신호 상태 리턴 (backup 신호는 하드웨어 디버깅 필요)
    '''
    if pioData['no_signal'] == 1:
        result = 0  # no signal
    elif pioData['signal_master'] == 0:
        result = 1  # master main
    elif pioData['signal_master'] == 1:
        result = 2  # master sub
    elif pioData['signal_backup'] == 0:
        result = 3  # backup main
    elif pioData['signal_backup'] == 1:
        result = 4  # backup sub
    return result

def get_power_watt():
    '''
    소비전력량 계산
    '''
    pass

def get_power_save(pioData: dict) -> int:
    '''
    절전모드 상태 리턴 0: normal, 1: saved
    '''
    result = 0 if pioData['power_save'] == 0 else 1
    return result


## ---------------- 메인루틴 ---------------- ##
def main():
    try:
        Pio = pio() # power/signal control instance
        # db = SqlLib(filename=db_file_path, table=SQL_PARAMETER.DATA_TABLE)
        fd = Pio.pio_I2Csetup() # i2c file descriptor

        print(f'start {__file__} main() loop ...')

        # main loop
        while True:
            # get hubdata from pio()
            if Pio.configSet(fd, I2CPARAMETER.CH_0, I2CPARAMETER.SR_240, I2CPARAMETER.GAIN_X1) != 0:  # write cmd for conversion (one-shot)
                raise ConnectionError
            voltage = Pio.readVoltage(fd)
            voltage = round(voltage, 4) # 소수점 4자리만 반영
            Pio.voltage = voltage
            # print(Pio.getDict())    # pio 산출정보

            # hub 데이터 생성
            pioData = Pio.getDict()
            pio_signal = get_signal_status(pioData)

            # get id from database 
            serverId = db_data.sql_select_one(SQL_PARAMETER.COL_SID)
            if serverId is not None:
                hubDatas.serverid = serverId[SQL_PARAMETER.COL_SID]

            # get id from database 
            clientId = db_data.sql_select_one(SQL_PARAMETER.COL_CID)
            if clientId is not None:
                hubDatas.clientid = clientId[SQL_PARAMETER.COL_CID]
            
            # get host ip for mode
            hostip = db_cmdTable.sql_select_one(SQL_PARAMETER.COL_HIP)
            if hostip is not None:
                if hostip[SQL_PARAMETER.COL_HIP] != "localhost":
                    hubDatas.opMode = MODE.SERVER
                else:
                    hubDatas.opMode = MODE.CLIENT
            
            # get status value
            hubDatas.power = float(pioData['voltage'])
            hubDatas.signal = pio_signal
            hubDatas.powerstatus = int(pioData['power_save'])

            # db table update (server mode / client mode)
            if hubDatas.opMode == MODE.SERVER:
            # if 0:
                if hubDatas.serverid != 0:    
                    if db_data.sql_table_check(SQL_PARAMETER.DATA_TABLE):
                        # get hub data from DB
                        readSql = pd.read_sql(f"select * from {SQL_PARAMETER.DATA_TABLE}", db_data._dbcon, index_col=None)
                        db_data.sql_commit()
                        if not readSql.empty:
                            # check client id '0' for server board
                            result = readSql[SQL_PARAMETER.COL_CID].isin([0])
                            # searching client id index
                            for i in result.index:
                                if result[i]:  # if is true
                                    db_data.sql_update_multi_column(0x0, hubDatas.power, hubDatas.signal, hubDatas.powerstatus)
            elif hubDatas.opMode == MODE.CLIENT:
            # elif 1:
                if hubDatas.clientid != 0:    
                    df = pd.DataFrame(data=hubDatas.getDict())
                    df.to_sql(SQL_PARAMETER.DATA_TABLE, db_data._dbcon, if_exists='replace', index=False)
                    db_data.sql_commit()
            else:
                syslog.syslog(f'disabled mode : {hubDatas.opMode}')  
                pass
            time.sleep(0.7)
    except KeyboardInterrupt as e:
        syslog.syslog(f'KeyInterrupt : {e}')
    except ConnectionError as e:
        syslog.syslog(f'IO Error : Error code [{IO_ERROR.I2C_CONNECT}], msg [{e}]')
    except Exception as e:
        print(f'File : {__file__}, Msg : {e}')
        syslog.syslog(f'File : {__file__}, Msg : {e}')
    finally:
        if db_data._dbcon:
            db_data.close()
            syslog.syslog(f'Event : Sql event code [{SQL_EVENT.CONNECT}]')
        '''
        # 오류 발생시 어플리케이션 재실행에 대한 루틴을 작성할 것
        '''
        # sys.exit(0)

if __name__ == '__main__':
	main()
        