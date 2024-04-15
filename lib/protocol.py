#!/usr/bin/python3
## Author: Dustin Lee
## Date: 2023.12.10
## Company: Cudo Communication
## This is a functional testing code for a processor unit of Hub board
## Feature : manage the network communication between daisy-chained the processor board

class COLOR(object):
    CYAN = '\033[96m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    DEFAULT = '\033[0m'
    BLUE = '\033[94m'

class TCP_OBJECT(object):
    '''Tcp frame object name'''
    HEADER_COMPANY_ID = 'companyId'
    HEADER_PRODUCT_INFO = 'productInfo'
    HEADER_SERVER_ID = 'serverId'
    HEADER_CLIENT_NUMBER = 'clientNumber'
    RESPONSE_CMD = 'command'
    RESPONSE_CMD_ID = 'setServerId'
    RESPONSE_CMD_SAVE = 'setPowerSave'
    RESPONSE_CMD_INFO = 'getHubInfo'
    DATA_SERVER_INFO = 'serverHubInfo'
    DATA_CLIENT_INFO = 'clientHubInfo'
    DATA_ID = 'Id'
    DATA_POWER = 'power'
    DATA_SIGNAL = 'signal'
    DATA_POWERSTATUS = 'powerStatus'
    '''Tcp frame constans value'''
    COMPANY_ID = 'cudoled'
    PRODUCT_INFO = 'hub-r1'
    NO_SIGNAL = 0
    MASTER_MAIN = 1
    MASTER_SUB = 2
    BACKUP_MAIN = 3
    BACKUP_SUB = 4
    POWER_NORMAL = 0
    POWER_SAVING = 1
    MAX_ID = 0x5FFF
    MIN_ID = 0x5000
    HOST_IP = 'hostIp'
    PORT_IN = 'IN'
    PORT_OUT = 'OUT'


    