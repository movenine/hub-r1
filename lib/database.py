#!/usr/bin/python3
## Author: Dustin Lee
## Date: 2023.12.10
## Company: Cudo Communication
## This is a functional testing code for a processor unit of Hub board
## Feature : manage a power or signal data of the processor board

import sqlite3
import syslog, sys
# import pandas as pd

# To import *
__all__ = [ 'db_file_path', 'SQL_PARAMETER', 'SQL_EVENT', 'SqlLib' ]

db_file_path = "/home/orangepi/wiringOP-Python/project/DB/hubData.db"

class SQL_PARAMETER(object):
    DATA_TABLE = 'hubDataTable'
    CMD_TABLE = 'hubCmdTable'
    COL_SID = 'serverId'
    COL_CID = 'clientId'
    COL_POW = 'power'
    COL_SIG = 'signal'
    COL_PST = 'powerStatus'
    COL_HIP = 'hostIp'
    COL_CNB = 'clientNumber'

class SQL_EVENT(object):
    CONNECT = 60

class SqlLib:
    def __init__(self, **kwargs):
        self.filename = kwargs.get('filename')  # 클래스 초기화 인수1 : database file
        self.table = kwargs.get('table', 'test')  # 클래스 초기화 인수2 : database table into DB file
        # self.cur = self.db.cursor()

    def sql_do(self, sql, *params):
        try:
            cur = self._dbcon.cursor()  
            cur.execute(sql, params)
            self._dbcon.commit()
            cur.close()
        except sqlite3.Error as e:
            syslog.syslog(f'{sys._getframe(1)} {e}')
            self.close()

    def sql_insert(self, params=()):
        try:
            cur = self._dbcon.cursor()
            if self.filename == db_file_path:
                sql = "insert into '{}' values (?, ?, ?, ?, ?)".format(self._table)
                cur.execute(sql, params)
                self._dbcon.commit()
            # DB 파일포맷에 따라 values 값을 조정하는 조건문
            # elif self.filename == db_analysis:
            cur.close()
        except sqlite3.Error as e:
            syslog.syslog(f'{sys._getframe(1)} {e}')
            self.close()

    def sql_retrieve(self, column, value):
        sql = f"select * from {self._table} where {column}=?"
        val = (value,)
        try:
            cur = self._dbcon.cursor()
            cur.execute(sql, val)
            row = cur.fetchone()
            cur.close()
            self._dbcon.commit()
        except sqlite3.Error as e:
            syslog.syslog(f'{sys._getframe(1)} {e}')
            self.close()
        return dict(row)

    def sql_update_cmdTable(self, serverId, hostIp, clientNumber, port_in, port_out):
        sql = f"update {self._table} set serverId = ?, hostIp = ?, clientNumber = ?, 'IN' = ?, 'OUT' = ?"
        value_list = (serverId, hostIp, clientNumber, port_in, port_out)
        try:
            cur = self._dbcon.cursor()
            cur.execute(sql, value_list)
            self._dbcon.commit()
            cur.close()
        except sqlite3.Error as e:
            syslog.syslog(f'{sys._getframe(1)} {e}')
            self.close()
    
    def sql_update_column(self, column, value):
        sql = f"update {self._table} set {column}={value}"
        try:
            cur = self._dbcon.cursor()
            cur.execute(sql)
            self._dbcon.commit()
            cur.close()
        except sqlite3.Error as e:
            syslog.syslog(f'{sys._getframe(1)} {e}')
            self.close()

    def sql_update_multi_column(self, clientId, power, signal, powerStatus):
        sql = f"update {self._table} set power = ?, signal = ?, powerStatus = ? where clientId = ?"
        value_list = (power, signal, powerStatus, clientId)
        try:
            cur = self._dbcon.cursor()
            cur.execute(sql, value_list)
            self._dbcon.commit()
            cur.close()
        except sqlite3.Error as e:
            syslog.syslog(f'{sys._getframe(1)} {e}')
            self.close()

    def sql_get_all(self):
        sql = f"select * from '{self._table}'"
        results = []
        try:
            cur = self._dbcon.cursor()
            cur.execute(sql)
            rows = cur.fetchall()
            self._dbcon.commit()
            for row in rows:
                results.append(dict(row))
            cur.close()
        except sqlite3.Error as e:
            syslog.syslog(f'{sys._getframe(1)} {e}')
            self.close()
        return results

    def sql_select_one(self, column, params=()):
        sql = f'SELECT {column} FROM {self._table}'
        try:
            cur = self._dbcon.cursor()
            cur.execute(sql, params)
            row = cur.fetchone()
            self._dbcon.commit()
            if row is None:
                cur.close()
                return
            cur.close()
        except sqlite3.Error as e:
            syslog.syslog(f'{sys._getframe(1)} {e}')
            self.close()
        return dict(row)

    def sql_lock_check(self):
        sql = f'PRAGMA locking_mode'
        try:
            cur = self._dbcon.cursor()
            cur.execute(sql)
            result = cur.fetchone()
            self._dbcon.commit()
            cur.close()
        except sqlite3.Error as e:
            syslog.syslog(f'{sys._getframe(1)} {e}')
            self.close()
        return dict(result)

    # to_sql, read_sql of pandas library - data empty 애러 발생으로 수동 커밋함수 추가
    def sql_commit(self):
        self._dbcon.commit()

    def sql_table_check(self, tableName):
        sql = f'PRAGMA table_info({tableName})'
        result: bool = False
        try:
            cur = self._dbcon.cursor()
            cur.execute(sql)
            row = cur.fetchone()
            if row is not None:
                result = True
            else:
                result = False
            return result
        except sqlite3.Error as e:
            syslog.syslog(f'{sys._getframe(1)} {e}')
            self.close()

    def close(self):
        self._dbcon.close()
        del self._filename

    @property
    def filename(self):
        return self._filename

    @filename.setter
    def filename(self, fn):
        self._filename = fn
        self._dbcon = sqlite3.connect(fn) # type: ignore
        self._dbcon.row_factory = sqlite3.Row  # row 리턴 값을 튜플 또는 dic(row)를 통해 딕셔너리 형태로 선택 가능
        # self._cur = self._db.cursor()  # Connection 을 얻고 명령 실행을 위한 cursor 객체를 생성함

    @filename.deleter
    def filename(self):
        self.close()

    # table 에 대한 getter, setter
    @property
    def table(self):
        return self._table

    @table.setter
    def table(self, t):
        self._table = t

    @table.deleter
    def table(self):
        self._table = 'test'

# def main():
#     #dataframe 생성
#     table_name = 'hubDataTable'
#     hub_data = {'serverid': [0x5000, 0x5000, 0x5000, 0x5000],
#                 'clientid' : [0x5001, 0x5002, 0x5003, 0x5004],
#                 'power' : [1.50, 1.65, 1.75, 1.66],
#                 'signal' : [1, 1, 1, 1],
#                 'powerstatus' : [0, 0, 0, 0]}
#     df = pd.DataFrame(hub_data)
#     db = SqlLib(filename=db_file_path, table=table_name)

#     print(df)
#     print(f'Table : {db.table}')
    
#     #dataframe를 db에 저장
#     df.to_sql(table_name, db._dbcon, if_exists='replace', index=False)
#     #db table을 읽어오기
#     read_table = pd.read_sql(f'select * from {table_name}', db._dbcon, index_col=None)
#     print(read_table)

#     #데이터 추가
#     add_data = [{'serverid': 0x5100,
#                 'clientid': 0x5101,
#                 'power': 1.77,
#                 'signal': 1,
#                 'powerstatus': 0}]
#     df = df.append(add_data, ignore_index=True)
#     print(df)

#     #dataframe를 db에 저장
#     df.to_sql(table_name, db._dbcon, if_exists='replace', index=False)
#     #db table을 읽어오기
#     read_table = pd.read_sql(f'select * from {table_name}', db._dbcon, index_col=None)
#     print(read_table)

#     #특정 컬럼 읽어오기
#     result = db.sql_select_one(COL_CID)
#     print(result)
#     print(result[COL_CID])

#     #특정 컬럼 바꾸기
#     db.sql_update_column(column=COL_SIG, value=0, row=COL_CID, condition=result[COL_CID])
#     #db table을 읽어오기
#     read_table = pd.read_sql(f'select * from {table_name}', db._dbcon, index_col=None)
#     print(read_table)

#     test_data = {'serverid': [0x5300,], 'clientid': [0x5301,], 'power': [1.247,], 'signal': [1,], 'powerstatus': [0,]}
#     df = pd.DataFrame(data=test_data)
#     print(df)

#     df.to_sql(table_name, db._dbcon, if_exists='replace', index=False)
#     #db table을 읽어오기
#     read_table = pd.read_sql(f'select * from {table_name}', db._dbcon, index_col=None)
#     print(read_table)

#     #특정 컬럼 읽어오기
#     result = db.sql_select_one(COL_CID)
#     print(result)
#     print(result[COL_CID])



# if __name__ == "__main__":
#     main()