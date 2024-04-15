#!/usr/bin/python3
## Author: Lee Dong Gu
## Date: 2023.12.10
## Company: Cudo Communication
## This is a functional testing code for a processor unit of Hub board
## Feature : signal mornitoring and processing the events

# import time, sys
import wiringpi
import argparse
from wiringpi import GPIO
from enum import IntEnum

# To import *
__all__ = ['IO_ERROR', 'IOPIN', 'IOPARAMETER', 'I2CPARAMETER', 'pio']

parser = argparse.ArgumentParser(description='i2c')
parser.add_argument("--device", type=str, default="/dev/i2c-0", help='specify the i2c node')
args = parser.parse_args()

class IO_ERROR(object):
    VALUE = 50
    I2C_CONNECT = 51

class IOPIN(IntEnum):
    FAULT = 2   # (input) HUB 전원공급 불량
    MOD_PW_CLK = 3  # (output) 모듈 전원제어 클록
    MOD_PW_EN = 4   # (output) 모듈 전원제어 레벨
    NO_SIG = 5  # (input) no signal 인터럽트 핀
    DET_M = 6   # (input) 메인영상 신호상태 (master / slave)
    DET_B = 7   # (input) 백업영상 신호상태 (master / slave)

class IOPARAMETER(object):
    TIME_ONOFF = 500    #(0.5sec)
    TIME_PCTRL = 3000   #(3sec)

class I2CPARAMETER(object):
    PIN_BASE = 65   # pinBase는 각 디바이스의 IO, CH 등을 부여한 번호(int형), 최소값 64
    I2C_ADDR = 0x6a # read cmd = 1, write cmd = 0
    CH_0 = 0x0
    CH_1 = 0x1
    CH_2 = 0x2
    CH_3 = 0x3
    SR_240 = 0x0
    SR_60 = 0x1
    SR_15 = 0x2
    SR_3_75 = 0x3
    GAIN_X1 = 0x0
    GAIN_X2 = 0x1
    GAIN_X3 = 0x2
    GAIN_X4 = 0x3
    MODE_ONESHOT = 0x0
    MODE_CONTINOUS = 0x1

class pio:
    _signal_master: int = 0 # 0: main, 1: sub
    _signal_bakcup: int = 0 # 0: main, 1: sub
    _no_signal: int = 0 # low active
    _powerSave: int = 0 # 0: normal, 1: saving
    _voltage: float     # input voltage
    _sign: int          # sign bit (+ (0), - (1))

    def __init__(self):
        self.pio_setup()

    def pio_setup(self):
        # io 초기화
        wiringpi.wiringPiSetup()
        # wiringpi.pinMode(IOPIN.FAULT, GPIO.INPUT)
        # MOD_PW_CLK 핀 대체 사용
        wiringpi.pinMode(IOPIN.FAULT, GPIO.OUTPUT)

        wiringpi.pinMode(IOPIN.MOD_PW_CLK, GPIO.OUTPUT) 
        wiringpi.pinMode(IOPIN.MOD_PW_EN, GPIO.OUTPUT) 
        wiringpi.pinMode(IOPIN.NO_SIG, GPIO.INPUT)
        wiringpi.pinMode(IOPIN.DET_M, GPIO.INPUT)
        wiringpi.pinMode(IOPIN.DET_B, GPIO.INPUT)
        # 콜백정의
        # wiringpi.wiringPiISR(IOPIN.FAULT, GPIO.INT_EDGE_FALLING, isr_fault_callback)
        wiringpi.wiringPiISR(IOPIN.NO_SIG, GPIO.INT_EDGE_BOTH, self.isr_nosignal_callback)
        wiringpi.wiringPiISR(IOPIN.DET_M, GPIO.INT_EDGE_BOTH, self.isr_detect_main_callback)
        wiringpi.wiringPiISR(IOPIN.DET_B, GPIO.INT_EDGE_BOTH, self.isr_detect_backup_callback)
        # wiringpi.softPwmCreate(IOPIN.MOD_PW_CLK,0,self.pulsewidth)

    # i2c file descriptor(fd)
    def pio_I2Csetup(self):
        return wiringpi.wiringPiI2CSetupInterface(args.device, I2CPARAMETER.I2C_ADDR)

    def pio_setModulePower(self, en: int) -> int:
        ''' en : pwm duty cycle
            time : time to keep a level
            return : 0: normal, 1: power saving, 50: valueError
        '''
        if en > 1:
            print(f'valueError : EN is [{en}]')
            return IO_ERROR.VALUE
        wiringpi.digitalWrite(IOPIN.MOD_PW_EN, en)
        # wiringpi.softPwmWrite(IOPIN.MOD_PW_CLK, self.pulsewidth)
        for time in range(0, 4):
            wiringpi.digitalWrite(IOPIN.FAULT, GPIO.LOW)
            wiringpi.delay(IOPARAMETER.TIME_ONOFF) # 1000 => 1 second
            wiringpi.digitalWrite(IOPIN.FAULT, GPIO.HIGH)
            wiringpi.delay(IOPARAMETER.TIME_ONOFF) # 1000 => 1 second
            # print(f'MOD_PW_CLK [{IOPIN.FAULT}] port rising edge time : {time}')
        return en

        # gpio callback function
    def isr_fault_callback(self):
        pass

    def isr_nosignal_callback(self):
        '''
        nNO_SIG : low active (falling edge)
        '''
        print(f'no signal event : nNO_SIG pin[{IOPIN.NO_SIG}]')
        wiringpi.delay(IOPARAMETER.TIME_PCTRL)
        pin_value = wiringpi.digitalRead(IOPIN.NO_SIG)
        self._no_signal = 1 if pin_value == 0 else 0
        result = self.pio_setModulePower(0) if pin_value == 0 else self.pio_setModulePower(1)
        self._powerSave = 1 if result == 0 else 0

    def isr_detect_main_callback(self):
        '''
        DET_M : low (main), high(backup)
        '''
        print(f'signal status event : DET_M pin[{IOPIN.DET_M}]')
        wiringpi.delay(1000)
        pin_value = wiringpi.digitalRead(IOPIN.DET_M)
        self._signal_master = 0 if pin_value == 0 else 1

    def isr_detect_backup_callback(self):
        '''
        DET_B : low (main), high(backup)
        '''
        print(f'signal status event : DET_B pin[{IOPIN.DET_B}]')
        wiringpi.delay(1000)
        pin_value = wiringpi.digitalRead(IOPIN.DET_B)
        self._signal_bakcup = 0 if pin_value == 0 else 1

        # gpio callback function
    def configSet(self, fd, ch, samplerate, gain):
        _configBit = 0x80 | (ch << 5) | (samplerate << 2) | gain    # one-shot, 채널1, 샘플링 12bits, 증폭 x1
        if wiringpi.wiringPiI2CWrite(fd, _configBit) < 0:
            print("Error write byte to mcp3424")
            return -1
        return 0

    def readRaw(self, fd) -> int:
        raw = wiringpi.wiringPiI2CReadReg16(fd, 0)
        lower = (raw & 0xFF00) >> 8
        upper = (raw & 0x00FF) << 8

        raw = upper | lower

        if (raw >> 11) & 1:    # 음수일 경우
            self.sign = 1
            # raw &= ~(1 << 11) # 파이선은 변수길이가 큼 64bit
            raw &= 0x07FF
        else:
            self.sign = 0

        # print(f'[{bin(raw)}] [{bin(upper)}] [{bin(lower)}]')
        return raw

    def readVoltage(self, fd) -> float:
        voltage = 0.0
        raw = self.readRaw(fd)
        lsb = 0.001     # 1mV by 12bit
        offset = 2.048
        sign = self.sign

        if sign == 1:
            voltage = float((raw * lsb) - offset)
        else:
            voltage = float(raw * lsb)

        return voltage

    def getDict(self):
        dic = dict()
        dic['signal_master'] = self.signal_master
        dic['signal_backup'] = self.signal_bakcup
        dic['no_signal'] = self.no_signal
        dic['power_save'] = self.powerSave
        dic['voltage'] = self.voltage
        dic['sign'] = self.sign
        return dic

    @property
    def signal_master(self): return self._signal_master
    @signal_master.setter
    def signal_master(self, value): self._signal_master = value

    @property
    def signal_bakcup(self): return self._signal_bakcup
    @signal_bakcup.setter
    def signal_bakcup(self, value): self._signal_bakcup = value

    @property
    def no_signal(self): return self._no_signal
    @no_signal.setter
    def no_signal(self, value): self._no_signal = value

    @property
    def powerSave(self): return self._powerSave
    @powerSave.setter
    def powerSave(self, value): self._powerSave = value

    @property
    def voltage(self): return self._voltage
    @voltage.setter
    def voltage(self, value): self._voltage = value

    @property
    def sign(self): return self._sign
    @sign.setter
    def sign(self, value): self._sign = value


# def main():
#     Pio = pio()
#     fd = Pio.pio_I2Csetup()

#     try:
#         while True:
#             if Pio.configSet(fd, I2CPARAMETER.CH_0, I2CPARAMETER.SR_240, I2CPARAMETER.GAIN_X1) != 0:  # write cmd for conversion (one-shot)
#                 raise ConnectionError
#             voltage = Pio.readVoltage(fd)
#             voltage = round(voltage, 4) # 소수점 4자리만 반영
#             Pio.voltage = voltage
                
#             print(Pio.getDict())
#             time.sleep(2)
#     except KeyboardInterrupt:
#         print("\nexit")
#         sys.exit(0)
#     except ConnectionError as e:
#         print(f'Error : {e}')

# if __name__ == "__main__":
#     main()