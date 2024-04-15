#!/usr/bin/python3
## Author: Dustin Lee
## Date: 2023.12.10
## Company: Cudo Communication
## This is a functional testing code for a processor unit of Hub board
## Feature : network's task loutine

from pickle import NONE
import socket, socketserver, time, sys, os, syslog, json, threading
import pandas as pd
from dataclasses import dataclass, field
from typing import Callable

sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from lib.ethernet import *
from lib.database import *
from lib.protocol import *

## ---------------- 고정 변수 ---------------- ##

## ---------------- 서브클래스 ---------------- ##
@dataclass
class EventTrigger:
    on_evnet: Callable = field(default=lambda: None)

@dataclass
class tcpFormat:
    _h_server_id: int
    _h_client_number: int
    _c_command: str
    _host_request: str
    _client_request_to_server: str = ""
    _client_request_to_client: str = ""
    event_trigger_server: EventTrigger = EventTrigger()
    event_trigger_client: EventTrigger = EventTrigger()
    
    def __post_init__(self):
        self.event_trigger_server.on_evnet = self.handle_event_server
        self.event_trigger_client.on_evnet = self.handle_event_client

    def checkServerId(self, id):
        result = id if id in range(TCP_OBJECT.MIN_ID, TCP_OBJECT.MAX_ID) else 0xFFFF
        self.h_server_id = result

    def checkCmd(self, value: list):
        loc = value.index(1)
        if loc == 0:
            self.c_command = TCP_OBJECT.RESPONSE_CMD_ID
        elif loc == 1:
            self.c_command = TCP_OBJECT.RESPONSE_CMD_SAVE
        elif loc == 2:
            self.c_command = TCP_OBJECT.RESPONSE_CMD_INFO
        else:
            self.c_command = ""

    def getJsonTcp(self, string):
        try:
            self.host_request = string
            data = json.loads(string)
            # checking companyId 
            check_result = True if data[TCP_OBJECT.HEADER_COMPANY_ID] == TCP_OBJECT.COMPANY_ID else False

            if check_result:
                cmd_list = [data[TCP_OBJECT.RESPONSE_CMD_ID], data[TCP_OBJECT.RESPONSE_CMD_SAVE], data[TCP_OBJECT.RESPONSE_CMD_INFO]]
                # save command
                self.checkCmd(cmd_list)
                # save server id
                self.checkServerId(data[TCP_OBJECT.HEADER_SERVER_ID])
                # save client number
                self.h_client_number = data[TCP_OBJECT.HEADER_CLIENT_NUMBER]
                # if data[TCP_OBJECT.HEADER_CLIENT_NUMBER] > 0:
                #     print(f'{COLOR.BRIGHT_RED} request to set client number : {self.h_client_number}')
                # print(f'{COLOR.BRIGHT_CYAN} {self.__dict__}')
            else:
                print(f'The JSON string does not conform to the protocol.'
                      f'{__file__} {self.__class__.__name__} getJsonTcp, msg : {data}')
                syslog.syslog(f'The JSON string does not conform to the protocol.'
                              f'{__file__} {self.__class__.__name__} getJsonTcp, msg : {data}')
                pass
        except ValueError as e:
            syslog.syslog(f'Socket error {__file__} {self.__class__.__name__}, msg : {e}')
    
    def setJsonCmdClientId(self, string):
        '''
        json string for set client id
        parameter : (str) JSON
        work : clientNumber + 1
        return : (str) JSON
        '''
        data = json.loads(string)
        data[TCP_OBJECT.HEADER_CLIENT_NUMBER] += 1
        return json.dumps(data)
    
    def setJsonResponeReqId(self) -> str:
        '''json string for request setup server id'''
        handle_db_req = SqlLib(filename=db_file_path, table=SQL_PARAMETER.DATA_TABLE)
        # get header + command (dict)
        headerCmd = self.getResFormatDictEx()
        # get hub data from DB (table:hubDataTable) (dataframe to dict)
        if handle_db_req.sql_table_check(SQL_PARAMETER.DATA_TABLE):
            hubData = pd.read_sql(f"select * from {SQL_PARAMETER.DATA_TABLE}", handle_db_req._dbcon, index_col=None)
            handle_db_req.sql_commit()
            if not hubData.empty:
                dictHubData = hubData.to_dict(orient='index') # type: ignore
                # rename object
                tcpData = dict()
                tcpData[TCP_OBJECT.DATA_ID] = dictHubData[0][SQL_PARAMETER.COL_SID]
                tcpData[TCP_OBJECT.DATA_POWER] = dictHubData[0][SQL_PARAMETER.COL_POW]
                tcpData[TCP_OBJECT.DATA_SIGNAL] = dictHubData[0][SQL_PARAMETER.COL_SIG]
                tcpData[TCP_OBJECT.DATA_POWERSTATUS] = dictHubData[0][SQL_PARAMETER.COL_PST]
        # appending
        if tcpData:
            headerCmd[TCP_OBJECT.DATA_SERVER_INFO] = tcpData
        else:
            headerCmd[TCP_OBJECT.DATA_SERVER_INFO] = "Unknown"
        # print(headerCmd)
        return json.dumps(headerCmd)
    
    def setJsonResponseReqHub(self):
        '''json string for request hub datas'''
        handle_db_req = SqlLib(filename=db_file_path, table=SQL_PARAMETER.DATA_TABLE)
        handle_db = SqlLib(filename=db_file_path, table=SQL_PARAMETER.CMD_TABLE)
        # get header + command (dict)
        headerCmd = self.getResFormatDictEx()
        # get hub data from DB (table:hubDataTable) (dataframe to dict)
        if handle_db_req.sql_table_check(SQL_PARAMETER.DATA_TABLE):
            hubData = pd.read_sql(f"select * from {SQL_PARAMETER.DATA_TABLE}", handle_db_req._dbcon, index_col=None)
            handle_db_req.sql_commit()
            if not hubData.empty:
                dictHubData = hubData.to_dict(orient='index') # type: ignore
                # rename object and appending
                clientList = []
                for index, value in dictHubData.items():
                    if index == 0:
                        del value[SQL_PARAMETER.COL_CID]
                        headerCmd[TCP_OBJECT.DATA_SERVER_INFO] = value
                    else:
                        del value[SQL_PARAMETER.COL_SID]
                        clientList.append(value)

                if len(clientList) > 0:
                    clientNumber = len(clientList)
                    headerCmd[TCP_OBJECT.DATA_CLIENT_INFO] = clientList
                    handle_db.sql_update_column(column=SQL_PARAMETER.COL_CNB, value=clientNumber)
                    headerCmd[TCP_OBJECT.HEADER_CLIENT_NUMBER] = clientNumber
                else:
                    headerCmd[TCP_OBJECT.DATA_CLIENT_INFO] = ""
        print(f'length: {len(clientList)}, {headerCmd}')
        return (len(clientList), json.dumps(headerCmd))

    def getResFormatDictEx(self) -> dict:
        '''
        get dictionary type of [header + response]
        '''
        dic = dict()
        dic[TCP_OBJECT.HEADER_COMPANY_ID] = TCP_OBJECT.COMPANY_ID
        dic[TCP_OBJECT.HEADER_PRODUCT_INFO] = TCP_OBJECT.PRODUCT_INFO
        dic[TCP_OBJECT.HEADER_SERVER_ID] = self.h_server_id
        dic[TCP_OBJECT.HEADER_CLIENT_NUMBER] = self.h_client_number
        dic[TCP_OBJECT.RESPONSE_CMD] = self.c_command
        return dic

    def getResFormatDict(self) -> dict:
        '''
        get dictionary type of [header + response]
        '''
        dic = dict()
        dic[TCP_OBJECT.HEADER_COMPANY_ID] = [TCP_OBJECT.COMPANY_ID, ]
        dic[TCP_OBJECT.HEADER_PRODUCT_INFO] = [TCP_OBJECT.PRODUCT_INFO, ]
        dic[TCP_OBJECT.HEADER_SERVER_ID] = [self.h_server_id, ]
        dic[TCP_OBJECT.HEADER_CLIENT_NUMBER] = [self.h_client_number, ]
        dic[TCP_OBJECT.RESPONSE_CMD] = [self.c_command, ]
        return dic
    
    def getcmdTableDict(self) -> dict:
        '''
        get dictionary type of command table
        '''
        dic = dict()
        dic[TCP_OBJECT.HEADER_SERVER_ID] = [self.h_server_id, ]
        dic[TCP_OBJECT.HOST_IP] = [Ether.host_ip_addr, ]
        dic[TCP_OBJECT.HEADER_CLIENT_NUMBER] = [self.h_client_number, ]
        dic[TCP_OBJECT.PORT_IN] = [Ether.port_in, ]
        dic[TCP_OBJECT.PORT_OUT] = [Ether.port_out, ]
        return dic

    def handle_event_server(self):
        '''
        raw 패킷 수신 이벤트 처리함수 (서버 모드)
        In server mode, when set client_request, working parser and store database
        '''
        if self.client_request_to_server == "":
            return
        
        handle_db_req = SqlLib(filename=db_file_path, table=SQL_PARAMETER.DATA_TABLE)
        # load json data from raw packet
        data = json.loads(self.client_request_to_server)
        # if exist client id, check DB's client id and insert row list
        if data[SQL_PARAMETER.COL_CID] != 0:
            # get hub data from DB (table:hubDataTable) (dataframe to dict)
            if handle_db_req.sql_table_check(SQL_PARAMETER.DATA_TABLE):
                readSql = pd.read_sql(f"select * from {SQL_PARAMETER.DATA_TABLE}", handle_db_req._dbcon, index_col=None)
                handle_db_req.sql_commit()
                if not readSql.empty:    
                    # check id is exist
                    result = readSql[SQL_PARAMETER.COL_CID].isin([data[SQL_PARAMETER.COL_CID]])
                    cnt = 0
                    for i in result.index:
                        if result[i]:  # if is true, increase count
                            cnt += 1
            if cnt > 0:   # is duplicated
                handle_db_req.sql_update_multi_column(clientId=data[SQL_PARAMETER.COL_CID],
                                                      power=data[SQL_PARAMETER.COL_POW],
                                                      signal=data[SQL_PARAMETER.COL_SIG],
                                                      powerStatus=data[SQL_PARAMETER.COL_PST])
            else:   # if new, insert data
                insert_row = (data[SQL_PARAMETER.COL_SID], data[SQL_PARAMETER.COL_CID],
                            data[SQL_PARAMETER.COL_POW], data[SQL_PARAMETER.COL_SIG],
                            data[SQL_PARAMETER.COL_PST])
                handle_db_req.sql_insert(insert_row)
        else:   # when clientId is '0'
            syslog.syslog(f'packet client id not exist {__file__} func : handle_event_server -> msg: {self.client_request_to_server}')
            pass

    def handle_event_client(self):
        '''
        raw 패킷 수신 이벤트 처리함수 (클라이언트 모드)
        In client mode, when set client_request, working parser and store database
        '''
        # check msg
        if self.client_request_to_client == "":
            return
        # set port in/out
        Ether.port_out = ETHER.PORT_LAN if Ether.port_in == ETHER.PORT_WAN else ETHER.PORT_WAN

        # analysis
        if tcpData.h_client_number > 0: # monitoring
            tcpData.c_command = TCP_OBJECT.RESPONSE_CMD_INFO
        else:
            tcpData.getJsonTcp(self.client_request_to_client)

        # processing
        if tcpData.c_command == TCP_OBJECT.RESPONSE_CMD_ID:
            # DB store to datatable
            handle_db_data = SqlLib(filename=db_file_path, table=SQL_PARAMETER.DATA_TABLE)
            handle_db_cmd = SqlLib(filename=db_file_path, table=SQL_PARAMETER.CMD_TABLE)
            if tcpData.h_server_id != 0 and tcpData.h_client_number > 0:
                clientId = tcpData.h_server_id + tcpData.h_client_number
                # update hubDataTable (serverId, clientId)
                handle_db_data.sql_update_column(column=SQL_PARAMETER.COL_SID, value=tcpData.h_server_id)
                handle_db_data.sql_update_column(column=SQL_PARAMETER.COL_CID, value=clientId)
                # update hubcmdTable (serverId, hostIp, clientNumber, In, Out)
                df = pd.DataFrame(data=tcpData.getcmdTableDict())
                df.to_sql(SQL_PARAMETER.CMD_TABLE, handle_db_cmd._dbcon, if_exists='replace', index=False)
                handle_db_cmd.sql_commit()
                # next client id (+1 clientNumber)
                clientPacket = tcpData.setJsonCmdClientId(self.client_request_to_client)
                print(f'{COLOR.RED} {clientPacket} {COLOR.DEFAULT}')
                # send next hub board
                result = Ether.sendRaw(target=ETHER.BROADCAST_MAC,
                            interface=Ether.port_out,
                            etherType=ETHER.ETH_REQ_ID,
                            packet=clientPacket
                            )
                if result != 0:
                    syslog.syslog(f'send error {__file__} {self.__class__.__name__} func : handle_event_client -> error_code: {result}')
        elif tcpData.c_command == TCP_OBJECT.RESPONSE_CMD_SAVE:
            pass
        elif tcpData.c_command == TCP_OBJECT.RESPONSE_CMD_INFO:
            rcv_string = json.loads(self.client_request_to_client)
            handle_db_data = SqlLib(filename=db_file_path, table=SQL_PARAMETER.DATA_TABLE)
            if handle_db_data.sql_table_check(SQL_PARAMETER.DATA_TABLE):
                readSql = pd.read_sql(f"select * from {SQL_PARAMETER.DATA_TABLE}", handle_db_data._dbcon, index_col=None)
                handle_db_data.sql_commit()
                if not readSql.empty:
                    clientId = readSql.loc[0, SQL_PARAMETER.COL_CID]
            # 수신받은 패킷의 클라이언트 아이디를 확인 및 처리
            # port out -> in : toss hub data
            if rcv_string[SQL_PARAMETER.COL_CID] != clientId:
                result = Ether.sendRaw(target=ETHER.BROADCAST_MAC,
                            interface=Ether.port_in,
                            etherType=ETHER.ETH_REQ_HUBINFO,
                            packet=self.client_request_to_client
                            )
                if result != 0:
                    syslog.syslog(f'send error {__file__} {self.__class__.__name__} func : handle_event_client -> error_code: {result}')
        else:
            syslog.syslog(f'Command error {__file__} {self.__class__.__name__} func : handle_event_client')
            pass

    @property
    def h_server_id(self): return self._h_server_id
    @h_server_id.setter
    def h_server_id(self, value): self._h_server_id = value

    '''
    h_client_number : 아이디 셋업을 위한 전달자로 사용, gethubinfo 요청시 전체 수량 리턴 
    '''
    @property
    def h_client_number(self): return self._h_client_number
    @h_client_number.setter
    def h_client_number(self, value): self._h_client_number = value

    @property
    def c_command(self): return self._c_command
    @c_command.setter
    def c_command(self, value): self._c_command = value

    @property
    def host_request(self): return self._host_request
    @host_request.setter
    def host_request(self, value): self._host_request = value

    @property
    def client_request_to_server(self): return self._client_request_to_server
    @client_request_to_server.setter
    def client_request_to_server(self, value): 
        self._client_request_to_server = value
        self.event_trigger_server.on_evnet()   # when client_request_server value set, trigging event!

    @property
    def client_request_to_client(self): return self._client_request_to_client
    @client_request_to_client.setter
    def client_request_to_client(self, value): 
        self._client_request_to_client = value
        self.event_trigger_client.on_evnet()   # when client_request_client value set, trigging event!

class HubTCPHandler(socketserver.BaseRequestHandler):
    '''attention - Create a thread, not a main thread'''
    def handle(self) -> None:
        print(f'Connected client ip address : [{self.client_address[0]}]')
        # User protocol parser 
        try: 
            packet = str(self.request.recv(1024), 'utf-8')
            # packet 분석(serverId, command), write server id 
            tcpData.getJsonTcp(packet) 

            # 명령처리
            if tcpData.c_command == TCP_OBJECT.RESPONSE_CMD_ID:
                # DB store after checking id
                handle_db = SqlLib(filename=db_file_path, table=SQL_PARAMETER.CMD_TABLE)
                df = pd.DataFrame(data=tcpData.getcmdTableDict())
                # print(df)
                df.to_sql(SQL_PARAMETER.CMD_TABLE, handle_db._dbcon, if_exists='replace', index=False)
                # DB store to datatable
                handle_db_data = SqlLib(filename=db_file_path, table=SQL_PARAMETER.DATA_TABLE)
                if tcpData.h_server_id != 0:
                    # update hubDataTable (serverId)
                    handle_db_data.sql_update_column(column=SQL_PARAMETER.COL_SID, value=tcpData.h_server_id)
                if Ether.port_out != "undefinded":
                    # set client id (ether_type : 0x6000)
                    clientPacket = tcpData.setJsonCmdClientId(packet)
                    result = Ether.sendRaw(target=ETHER.BROADCAST_MAC,
                                interface=Ether.port_out,
                                etherType=ETHER.ETH_REQ_ID,
                                packet=clientPacket
                                )
                    if result != 0:
                        syslog.syslog(f'send error {__file__} {self.__class__.__name__} func : handle_event_client -> error_code: {result}')
                response = bytes(tcpData.setJsonResponeReqId(), 'utf-8')
                self.request.sendall(response)
            elif tcpData.c_command == TCP_OBJECT.RESPONSE_CMD_SAVE:
                pass
            elif tcpData.c_command == TCP_OBJECT.RESPONSE_CMD_INFO:
                # DB store after updating client Number
                handle_db = SqlLib(filename=db_file_path, table=SQL_PARAMETER.CMD_TABLE)
                client_number, response_Json = tcpData.setJsonResponseReqHub()
                handle_db.sql_update_column(column=SQL_PARAMETER.COL_CNB, value=client_number)
                response = bytes(response_Json, 'utf-8')
                self.request.sendall(response)
            else:
                syslog.syslog(f'Command error {__file__} {self.__class__.__name__} func : handle')
                pass
        except UnicodeDecodeError as e:
            print(f'{e}')  
        except socket.error as e:
            syslog.syslog(f'Socket error {__file__} {self.__class__.__name__} func : handle, msg : {e}')
        # return    
        
class ThreadedHubTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_addr, RequestHandlerClass):
        socketserver.TCPServer.__init__(self, server_addr, RequestHandlerClass)


## ---------------- 클래스 인스턴스 ---------------- ##
tcpData = tcpFormat(
    _h_server_id=0,
    _h_client_number=0,
    _c_command="",
    _host_request=""
)
Ether = ether(
    port_in="",
    port_out="",
    op_mode=MODE.NONE,
    local_ip="",
    host_ip="localhost",
    broadcast_ip="192.168.0.255"
)
# this is sqlite object for main thread
try:
    db_data = SqlLib(filename=db_file_path, table=SQL_PARAMETER.DATA_TABLE)
    db_cmdTable = SqlLib(filename=db_file_path, table=SQL_PARAMETER.CMD_TABLE)
except Exception as e:
    syslog.syslog(f'File : {__file__}, Msg : {e}')
    pass

## ---------------- 콜백(이벤트) ---------------- ##

## ---------------- 서브루틴 ---------------- ##
def getClientDataPort(iface: str, timeout: int):
    '''
    get client data from port in/out ('eth0', 'lan0') by orangepi-r1-plus-lts
    '''
    try:
        while True:
            if Ether.op_mode == MODE.SERVER:
            # if 0:
                # if serverid, wait to hub data.
                if tcpData.h_server_id:
                    data = Ether.receiveRaw(interface=iface, time=timeout, etherType=ETHER.ETH_REQ_HUBINFO)
                    tcpData.client_request_to_server = data if data != "" else ""
                # # if not serverid, wait to id
                # else:
                #     data = Ether.receiveRaw(interface=iface, time=timeout, etherType=ETHER.ETH_REQ_ID)
                #     tcpData.client_request_to_server = data if data != "" else ""
            elif Ether.op_mode == MODE.CLIENT:
            # elif 1:
                # if client number, wait to hub data
                if tcpData.h_client_number > 0:
                    data = Ether.receiveRaw(interface=iface, time=timeout, etherType=ETHER.ETH_REQ_HUBINFO)
                    tcpData.client_request_to_client = data if data != "" else ""
                # if not client numner, wait to id
                else:
                    data = Ether.receiveRaw(interface=iface, time=timeout, etherType=ETHER.ETH_REQ_ID)
                    tcpData.client_request_to_client = data if data != "" else ""
            else:
                pass
            time.sleep(1)
    except Exception as e:
        syslog.syslog(f'File : {__file__} func : getClientDataPort, Msg : {e}')

def init_attribute():
    '''to initialize a attribute of classes from DB'''
    try:
        init_db_cmd = SqlLib(filename=db_file_path, table=SQL_PARAMETER.CMD_TABLE)
        if init_db_cmd.sql_table_check(SQL_PARAMETER.DATA_TABLE):
            readSql = pd.read_sql(f"select * from {SQL_PARAMETER.CMD_TABLE}", init_db_cmd._dbcon, index_col=None)
            init_db_cmd.sql_commit()
            if not readSql.empty:
                tcpData.h_server_id = readSql.loc[0, SQL_PARAMETER.COL_SID]
                tcpData.h_client_number = readSql.loc[0, SQL_PARAMETER.COL_CNB]
                Ether.port_in = readSql.loc[0, TCP_OBJECT.PORT_IN]
                Ether.port_out = readSql.loc[0, TCP_OBJECT.PORT_OUT]
    except Exception as e:
        syslog.syslog(f'File : {__file__} func : init_attribute, Msg : {e}')

def setClientDataPort():
    '''set client data to send a next connection'''
    try:
        result = 0
        while True:
            thread_db_data = SqlLib(filename=db_file_path, table=SQL_PARAMETER.DATA_TABLE)
            # busy check from database
            if thread_db_data.sql_table_check(SQL_PARAMETER.DATA_TABLE):
                readSql = pd.read_sql(f"select * from {SQL_PARAMETER.DATA_TABLE}", thread_db_data._dbcon, index_col=None)
                thread_db_data.sql_commit()
                if not readSql.empty:
                    hubData = readSql.to_dict(orient='index')
                    hubDataJSON = json.dumps(hubData[0])
                    # print(f'{hubDataJSON}')
                    if Ether.port_in != "undefinded":
                        result = Ether.sendRaw(target=ETHER.BROADCAST_MAC,
                                    interface=Ether.port_in,
                                    etherType=ETHER.ETH_REQ_HUBINFO,
                                    packet=hubDataJSON
                                    )
            if result != 0:
                syslog.syslog(f'send error {__file__} {__name__} func : setClientDataPort -> error_code: {result}')
            time.sleep(ETHER.RAW_SEND_DELAY)
    except Exception as e:
        print(f'File : {__file__} func : setClientDataPort, Msg : {e}')
        syslog.syslog(f'File : {__file__} func : setClientDataPort, Msg : {e}')
        pass

## ---------------- 메인루틴 ---------------- ##
def main():
    try:
        # tcpData value initialize from DB
        init_attribute()

        if Ether.get_operate_mode() == MODE.SERVER:
        # if 0:
            try:
                if Ether.host_ip_addr == "localhost":
                    HOST = Ether.get_broadcast_ip_addr()
                    PORT = ETHER.UDP_PORT
                    Ether.get_host_ip_addr(HOST, PORT)
            except socket.error as e:
                syslog.syslog(f'Socket error {__file__}, msg : {e}')
            else:
                if Ether.local_ip_addr != "":
                    HOST = Ether.local_ip_addr
                    PORT = ETHER.TCP_PORT
                    with ThreadedHubTCPServer((HOST, PORT), HubTCPHandler) as server:
                        # 운영서버 통신라인
                        server_thread = threading.Thread(target=server.serve_forever)
                        server_thread.daemon = True                                                         
                        server_thread.start()

                        client_thread = threading.Thread(target=getClientDataPort,
                                                         args=(Ether.port_out, ETHER.RAW_TIMEOUT),
                                                         daemon=True)
                        client_thread.start()
                        syslog.syslog(f'Main() working.. {__file__} Mode: {MODE.NONE}, '
                                    f'Processing thread: {server_thread.name}, {client_thread.name}')
                        while True:
                            if tcpData.h_server_id != 0:
                                break
                        # updating DB's command table in main loop
                        df = pd.DataFrame(data=tcpData.getcmdTableDict())
                        df.to_sql(SQL_PARAMETER.CMD_TABLE, db_cmdTable._dbcon, if_exists='replace', index=False)
                        db_cmdTable.sql_commit()
                        print(df)

                        while True:
                            if server_thread.is_alive() == False:
                                break
                        
        elif Ether.get_operate_mode() == MODE.CLIENT:
        # elif 1:
            # thread<1> : socket to send the packet hub data
            socket_thread_send = threading.Thread(target=setClientDataPort, daemon=True)
            socket_thread_send.start()
            # thread<2> : socket to receive the port (eth0)
            socket_thread_rcv_eth0 = threading.Thread(target=getClientDataPort,
                                                      args=(ETHER.PORT_WAN, ETHER.RAW_TIMEOUT),
                                                      daemon=True)
            socket_thread_rcv_eth0.start()
            # thread<3> : socket to receive the port (lan0)
            socket_thread_rcv_lan0 = threading.Thread(target=getClientDataPort,
                                                      args=(ETHER.PORT_LAN, ETHER.RAW_TIMEOUT),
                                                      daemon=True)
            socket_thread_rcv_lan0.start()
            syslog.syslog(f'Main() working.. {__file__} Mode: {MODE.NONE}, '
                            f'Processing thread: {socket_thread_send.name}, {socket_thread_rcv_eth0.name}, {socket_thread_rcv_lan0.name}')
            while True:
                if socket_thread_send.is_alive() == False or socket_thread_rcv_eth0.is_alive() == False or socket_thread_rcv_lan0.is_alive() == False:
                    break
        else:
            syslog.syslog(f'Mode not definded error {__file__} {MODE.NONE}, will be pass in while loop')
            pass
    except KeyboardInterrupt as e:
        syslog.syslog(f'KeyInterrupt : {e}')
    except Exception as e:
        print(f'File : {__file__}, Msg : {e}')
        syslog.syslog(f'File : {__file__}, Msg : {e}')
        if db_data._dbcon:
            db_data.close()
            syslog.syslog(f'Event : Sql event code [{SQL_EVENT.CONNECT}], Table name [{SQL_PARAMETER.DATA_TABLE}]')
        elif db_cmdTable._dbcon:
            db_cmdTable.close()
            syslog.syslog(f'Event : Sql event code [{SQL_EVENT.CONNECT}], Table name [{SQL_PARAMETER.DATA_TABLE}]')
        '''
        # 오류 발생시 어플리케이션 재실행에 대한 루틴을 작성할 것
        '''
        syslog.syslog(f'main() some error {__file__}, Please restart service')
        sys.exit(0)

if __name__ == '__main__':
	main()