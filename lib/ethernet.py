#!/usr/bin/python3
## Author: Dustin Lee
## Date: 2023.12.10
## Company: Cudo Communication
## This is a functional testing code for a processor unit of Hub board
## Feature : manage the network communication between daisy-chained the processor board

import binascii
import fcntl
import re
import socket
import struct
import selectors
import netifaces, syslog, sys, os
from enum import IntEnum

sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from lib.protocol import *

# To import *
__all__ = ['ETHER', 'MODE', 'RESULT', 'ether']

class ETHER(object):
    # Definitions of the socket-level I/O control calls.
    # Source: https://github.com/torvalds/linux/blob/master/include/uapi/linux/sockios.h
    _SIOCGIFHWADDR = 0x8927      # Get hardware address

    # Global definitions for the Ethernet IEEE 802.3 interface.
    # Source: https://github.com/torvalds/linux/blob/master/include/uapi/linux/if_ether.h
    ETH_ALEN = 6                # Octets in one ethernet addr
    ETH_TLEN = 2                # Octets in ethernet type field
    ETH_HLEN = 14               # Total octets in header.
    ETH_ZLEN = 60               # Min. octets in frame sans FCS
    ETH_DATA_LEN = 1500         # Max. octets in payload
    ETH_FRAME_LEN = 1514        # Max. octets in frame sans FCS

    ETH_P_ALL = 0x0003          # Every packet (be careful!!!)
    ETH_P_IP = 0x0800           # Internet Protocol packet
    ETH_P_ARP = 0x0806          # Address Resolution packet
    ETH_P_802_EX1 = 0x88B5      # Local Experimental Ethertype 1
    ETH_P_802_EX2 = 0x88B6      # Local Experimental Ethertype 2

    # Definitions of the user-level I/O control calls.
    ETH_REQ_ID = 0x6000
    ETH_SET_POWER_SAVE = 0x6002
    ETH_REQ_HUBINFO = 0x6001

    # Definitions of ethernet layer
    TCP_PORT = 55555
    UDP_PORT = 55556
    BROADCAST_MAC = 'ff:ff:ff:ff:ff:ff'

    # Definitions of iface
    PORT_WAN = 'eth0'
    PORT_LAN = 'lan0'
    PORT_WLAN = 'lo'

    # socket delay time
    TCP_TIMEOUT = 10
    RAW_TIMEOUT = 5
    RAW_SEND_DELAY = 2

class MODE(IntEnum):
    NONE = 0
    SERVER = 1
    CLIENT = 2
    IN = 3
    OUT = 4

class RESULT(IntEnum):
    SEND_OK = 1
    SEND_FAIL = 2
    RCV_OK = 3
    RCV_FAIL = 4
    CONNECT_OK = 5
    CONNECT_FAIL = 6

class ether:
    _port_in: str # define for direction port
    _port_out: str # define for direction port
    _op_mode: int  # defined ethernet.py : operation mode
    _local_ip_addr: str # allocated ip address
    _host_ip_addr: str
    _broadcast_ip_addr: str

    def __init__(self, port_in: str,
                 port_out: str,
                 op_mode: int,
                 local_ip: str,
                 host_ip: str,
                 broadcast_ip: str):
        ether._port_in = port_in
        ether._port_out = port_out
        ether._op_mode = op_mode
        ether._local_ip_addr = local_ip
        ether._host_ip_addr = host_ip
        ether._broadcast_ip_addr = broadcast_ip 
    
    def bytes_to_eui48(self, b: bytes, sep=':'):
        """Convert bytes to MAC address (EUI-48) string."""
        if len(b) != ETHER.ETH_ALEN:
            raise ValueError()
        if sep != ':' and sep != '-':
            raise ValueError()
        return sep.join('%02x' % octet for octet in b)

    def eui48_to_bytes(self, s: str):
        """Convert MAC address (EUI-48) string to bytes."""
        if re.match(r'^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$', s):
            sep = ':'
        elif re.match(r'^([0-9A-Fa-f]{2}-){5}([0-9A-Fa-f]{2})$', s):
            sep = '-'
        else:
            raise ValueError('invalid format')
        return binascii.unhexlify(''.join(s.split(sep)))

    def get_hardware_address(self, interface):
        """Get hardware address of specific interface."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Invoke ioctl for a socket descriptor to obtain a hardware address
            info = fcntl.ioctl(s.fileno(), ETHER._SIOCGIFHWADDR, struct.pack('256s', interface[:15].encode()))
            return info[18:24]

    def get_IPv4_address_by(self, interface):
        """Check allocated ip address of specific interface."""
        """return dictionary {'ip': ip_addr, 'iface': iface}"""
        iface_info = netifaces.ifaddresses(interface)
        # Check ethernet layer 3 level
        if netifaces.AF_INET in iface_info:
            ipv4_addr = iface_info[netifaces.AF_INET][0]['addr']
        else:
            ipv4_addr = ""
        return ipv4_addr

    def get_IPv4_address(self) -> dict:
        """Check allocated ip address of specific interface."""
        """return dictionary {'ip': ip_addr, 'iface': iface}"""
        for iface in netifaces.interfaces():
            if iface == 'eth0' or iface == 'lan0':
                iface_info = netifaces.ifaddresses(iface)
                # Check ethernet layer 3 level
                if netifaces.AF_INET in iface_info:
                    ipv4_addr = iface_info[netifaces.AF_INET][0]['addr']
                    break
                else:
                    ipv4_addr = ""
        ip_dict = {'ip': ipv4_addr, 'iface': iface}
        return ip_dict

    def get_operate_mode(self) -> int:
        """
        Get operating mode(server or client)
        PC-S-C >>> 방향 기준으로 포트 in, out 설정 알고리즘 적용
        """
        net_info = self.get_IPv4_address()
        if net_info['ip'] != "":
            self.op_mode = MODE.SERVER
            self.local_ip_addr = net_info['ip']
            if net_info['iface'] == ETHER.PORT_WAN:
                self.port_in = ETHER.PORT_WAN
                self.port_out = ETHER.PORT_LAN
            elif net_info['iface'] == ETHER.PORT_LAN:
                self.port_in = ETHER.PORT_LAN
                self.port_out = ETHER.PORT_WAN
            else:
                pass
            return MODE.SERVER
        else:
            self.op_mode = MODE.CLIENT
            # 포트정의는 raw packet 이벤트 함수에서 설정함
            return MODE.CLIENT

    def get_host_ip_addr(self, broadcast, port):
        '''
        get dhcp host ip address
        '''
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind((broadcast, port))
            s.setblocking(False)
            s.settimeout(ETHER.TCP_TIMEOUT)

            print('UDP server is up and listening')
            syslog.syslog('UDP server is up and listening')
            # s.listen()
            while True:
                try:
                    d = s.recvfrom(1024)
                    if d:
                        data = d[0] # packet data
                        addr = d[1] # host ip
                        reply = self.get_IPv4_address()

                        s.sendto(bytes(reply['ip'], 'UTF-8'), (addr[0],ETHER.UDP_PORT)) # UDP PORT는 고정
                        print(f'Message[{addr[0]} : {str(addr[1])}] {data.strip().decode()}')

                        if data.strip().decode('utf-8') == TCP_OBJECT.PRODUCT_INFO:
                            self.host_ip_addr = addr[0] # ip 만 전달
                            syslog.syslog(f'get host ip : [{addr}], set server mode')
                            return self.host_ip_addr
                except IOError as e:
                    # time.sleep(1)
                    syslog.syslog(f'Waiting to request activation..')
                    pass

    def get_broadcast_ip_addr(self):
        '''
        get broadcast ip address
        '''
        for iface in netifaces.interfaces():
            if iface == 'eth0' or iface == 'lan0':
                iface_info = netifaces.ifaddresses(iface)
                # Check ethernet layer 3 level
                if netifaces.AF_INET in iface_info:
                    self.broadcast_ip_addr = iface_info[netifaces.AF_INET][0]['broadcast']
                    break
                else:
                    self.broadcast_ip_addr = ""
        return self.broadcast_ip_addr

    def receiveRaw(self, **kwargs) -> str:
        '''
        receive raw packet to mac address (interface, time)
        '''
        interface = kwargs.get('interface', "")
        time = kwargs.get('time', 0)
        etherType = kwargs.get('etherType', 0)

        decodeData = ""

        if etherType == 0:
            syslog.syslog(f'Socket error {__file__}, msg : etherType {etherType}')
            return ""
        else:
            try:
                with socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(etherType)) as s:
                    s.bind((interface, 0))
                    s.settimeout(time)
                    with selectors.DefaultSelector() as selector:
                        selector.register(s.fileno(), selectors.EVENT_READ)
                        ready = selector.select()
                        if ready:
                            if self.port_in == "undefinded":
                                self.port_in = interface
                            frame = s.recv(ETHER.ETH_DATA_LEN)
                            header = frame[:ETHER.ETH_HLEN]
                            dst, src, proto = struct.unpack('!6s6sH', header)
                            payload = frame[ETHER.ETH_HLEN:]
                            _len = len(payload)
                            unpackData = struct.unpack(f'!{_len}s', payload)
                            decodeData = unpackData[0].decode('utf-8')
            except socket.error as e:
                syslog.syslog(f'Socket error {__file__} receiveRaw(), msg : {e}')
            except UnicodeError as e:
                syslog.syslog(f'Socket error {__file__} receiveRaw(), msg : {e}')
            finally:
                print(f'dst: {self.bytes_to_eui48(dst)}, '
                    f'src: {self.bytes_to_eui48(src)}, '
                    f'type: {hex(proto)}, '
                    f'payload: {len(decodeData)} {decodeData}')
                return decodeData

    def sendRaw(self, **kwargs) -> int:
        '''
        send raw packet to mac address (target, interface, etherType, packet)
        '''
        target = kwargs.get('target', "")
        interface = kwargs.get('interface', "")
        etherType = kwargs.get('etherType', 0)
        packet = kwargs.get('packet', "")

        error_code = 0

        if len(packet) > ETHER.ETH_DATA_LEN:
            syslog.syslog(f'Socket error {__file__}, msg : packet size bigger than {ETHER.ETH_DATA_LEN} [{len(packet)}]')
            return -1
        elif len(packet) == 0:
            syslog.syslog(f'Socket error {__file__}, msg : packet size [{len(packet)}]')
            return -1
        else:
            try:
                _len = len(packet)  # packing size
                with socket.socket(socket.AF_PACKET, socket.SOCK_RAW) as s:
                    s.bind((interface, 0))
                    s.sendall(
                        struct.pack(f'!6s6sH{_len}s',
                                    self.eui48_to_bytes(target),            # Destination MAC address
                                    self.get_hardware_address(interface),   # Source MAC address
                                    etherType,                              # Ethernet type
                                    packet.encode('utf-8')))                # Payload (encoding bytes type)
                    # print(f'send Raw packet : [len : {len(packet)}]')
                    # syslog.syslog(f'send Raw packet : [len : {len(packet)}]')
                    error_code = s.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            except socket.error as e:
                syslog.syslog(f'Socket error {__file__} sendRaw(), msg : {e}')
            finally:
                return error_code

    def getDict(self) -> dict:
        dic = dict()
        dic['port_in'] = self.port_in
        dic['port_out'] = self.port_out
        dic['op_mode'] = self.op_mode
        dic['host_ip_addr'] = self.host_ip_addr
        dic['broadcast_ip_addr'] = self.broadcast_ip_addr
        return dic

    @property
    def port_in(self): return self._port_in
    @port_in.setter
    def port_in(self, value): self._port_in = value

    @property
    def port_out(self): return self._port_out
    @port_out.setter
    def port_out(self, value): self._port_out = value

    @property
    def op_mode(self): return self._op_mode
    @op_mode.setter
    def op_mode(self, value): self._op_mode = value

    @property
    def host_ip_addr(self): return self._host_ip_addr
    @host_ip_addr.setter
    def host_ip_addr(self, value): self._host_ip_addr = value

    @property
    def broadcast_ip_addr(self): return self._broadcast_ip_addr
    @broadcast_ip_addr.setter
    def broadcast_ip_addr(self, value): self._broadcast_ip_addr = value

    @property
    def local_ip_addr(self): return self._local_ip_addr
    @local_ip_addr.setter
    def local_ip_addr(self, value): self._local_ip_addr = value

# def main():
#     Ether = ether()
#     # check host ip
#     HOST = Ether.get_broadcast_ip_addr()
#     PORT = ETHER.UDP_PORT

#     try:
#         Ether.get_host_ip_addr(HOST, PORT)
#     except socket.error as e:
#         syslog.syslog(f'Socket error {__file__}, msg : {e}')

# if __name__ == "__main__":
#     main()
