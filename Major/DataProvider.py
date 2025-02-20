""" all data and transformer active """
from Database import SQL_operate
from Database.SQL_operate import SqlSentense
import pandas as pd
from Datatransformer import Datatransformer
from utils.Debug_tool import debug
import logging
from binance import AsyncClient, BinanceSocketManager
import datetime
from datetime import timedelta
import asyncio
from . import custom
import copy

class DataProvider:
    """
        用來整合 binance 的 API
        MYSQL
        和資料轉換
    """

    def __init__(self):
        self.Binanceapp = custom.Binance_server()
        self.SQL = SQL_operate.DB_operate()
        self.transformer = Datatransformer()

    def reload_data(self, symbol_name='BTCUSDT', time_type=None, iflower=True, reload_type=None, symbol_type=None):
        assert symbol_type is not None, "ERROR symbol type can't be None"

        # 先檢查是否有相關資料 取得目前所有列
        symbol_name_list = self.SQL.get_db_data('show tables;')
        symbol_name_list = [y[0] for y in symbol_name_list]

        table_name = self.transformer.generate_table_name(
            symbol_name, symbol_type, time_type, iflower)

        if table_name in symbol_name_list:
            # 當實時交易的時候減少 讀取數量
            if reload_type == 'History':
                SQL_Q = f"""SELECT * FROM ( SELECT * FROM `{table_name}` ORDER BY Datetime DESC LIMIT 20 ) t ORDER BY Datetime ASC;"""
                df = self.SQL.read_Dateframe(SQL_Q)

            elif reload_type == 'Online':
                parser_date = str(datetime.date.today() + timedelta(days=-100))
                df = self.SQL.read_Dateframe(
                    f'SELECT * FROM `{table_name}` where Datetime > "{parser_date}"')

            elif reload_type == 'all_data':
                df = self.SQL.read_Dateframe(table_name)

            # 這邊竟然會出現df是None的狀態 有點匪夷所思
            # 這邊的問題是只創建未保存 所以下次會出現問題 因為測試的關係
            df['Datetime'] = df['Datetime'].astype(str)
        else:
            print('創建資料')
            self.SQL.change_db_data(
                SqlSentense.create_table_name(table_name))
            df = pd.DataFrame()

        # 這邊的資料為原始的UTC資料 無任何加工
        original_df, eachCatchDf = self.Binanceapp.BinanceDate.download(
            df, f"{symbol_name}", kline_size=time_type, symbol_type=symbol_type)

        return original_df, eachCatchDf

    def save_data(self, symbol_name, original_df, symbol_type: str, time_type: str, iflower=True, exists="replace"):
        """
            保存資料到SQL
        """
        # 你可以这样调用这个函数
        table_name = self.transformer.generate_table_name(
            symbol_name, symbol_type, time_type, iflower)
        if exists == 'replace':
            self.SQL.write_Dateframe(original_df, table_name)
        else:
            self.SQL.write_Dateframe(
                original_df, table_name, exists=exists)

    def reload_all_data(self, time_type, symbol_type):
        """
            Args:
            time_type (_type_, optional): _description_. Defaults to None.
                如果'D' 代表要取用的時間為日線
            用來回補所有symbol的歷史資料
            為了避免寫入過慢 更改成append

            2023.04.18
                TODO:
                    lewis MSG:
                        i find bug in pandas to sql 
                        in SQLAlchemy==2.XX.XX no error but mysql database can't insert data
                        so i reply SQLAlchemy==1.4.44
                        if future can try to fix this bug 

        """
        for symbol_name in self.Binanceapp.get_targetsymobls():
            try:
                original_df, eachCatchDf = self.reload_data(
                    symbol_name, time_type=time_type, reload_type="History", symbol_type=symbol_type)
                eachCatchDf.drop(
                    [eachCatchDf.index[0], eachCatchDf.index[-1]], inplace=True)
                if len(eachCatchDf) != 0:
                    eachCatchDf.set_index('Datetime', inplace=True)

                    self.save_data(symbol_name, eachCatchDf, symbol_type, time_type,
                                   exists="append")
            except:
                debug.print_info()
                debug.record_msg(
                    error_msg=f"symbol = {symbol_name}", log_level=logging.error)

    def get_symbols_history_data(self, symbol_type, time_type=None, iflower=True) -> list:
        """
            讀取所有日線資料 用來分析和排序
        Args:
            time_type (_type_, optional): _description_. Defaults to None.
                如果'D' 代表要取用的時間為日線
            iflower (bool, optional): _description_. Defaults to True.

        Returns:
            list: 
                [[tb_symbol_name,each_df],
                 [tb_symbol_name,each_df],
                 ....
                ]
        """
        out_list = []
        for symbol_name in self.Binanceapp.get_targetsymobls():
            tb_symbol_name = self.transformer.generate_table_name(
                symbol_name, symbol_type, time_type, iflower)

            each_df = self.SQL.read_Dateframe(tb_symbol_name)
            out_list.append([tb_symbol_name, each_df])

        return out_list

    def get_symboldata(self, symbol_name, freq: int = 15, QMType=None):
        """
            非即時交易的時候用來產生回測資料
            並且保存至本地端點
            
            即時交易的時候,先將DB的資料讀取出來並且回傳,不保存
            
            QMType:
                    Eample (History)
                    Eample (Online)
        """
        assert QMType is not None, 'QMtype Can`t be Nonetype'

        if QMType == 'History':
            original_df, eachCatchDf = self.reload_data(
                symbol_name, time_type='1m', reload_type="all_data", symbol_type='FUTURES')

            new_df = self.transformer.get_tradedata(original_df, freq=freq)
            new_df.to_csv(f"{symbol_name}-F-{freq}-Min.csv")
        
        elif QMType == 'Online':
            original_df, eachCatchDf = self.reload_data(
            symbol_name, time_type='1m', reload_type="Online", symbol_type='FUTURES')

            return original_df, eachCatchDf

class DataProvider_online(DataProvider):
    def __init__(self):
        super().__init__()

    def get_trade_data(self, original_df, freq):
        new_df = self.transformer.get_tradedata(original_df, freq=freq)
        return new_df


class AsyncDataProvider():
    def __init__(self) -> None:
        self.all_data = {}
        self.lock = asyncio.Lock()

    async def process_message(self, res):
        filterdata = res['data']['k']
        data = {"Datetime": datetime.datetime.utcfromtimestamp(filterdata["t"]/1000).strftime("%Y-%m-%d %H:%M:%S"),  # 将 Unix 时间戳转换为 datetime 格式
                "Open": filterdata["o"],
                "High": filterdata["h"],
                "Low": filterdata["l"],
                "Close": filterdata["c"],
                "Volume": filterdata["v"],
                "close_time": filterdata["T"],
                "quote_av": filterdata["q"],
                "trades": filterdata["n"],
                "tb_base_av": filterdata["V"],
                "tb_quote_av": filterdata["Q"],
                "ignore": filterdata["B"]}

        return data

    async def update_data(self, symbol, data):
        async with self.lock:
            self.all_data[symbol].update({data['Datetime']: data})

    async def get_all_data(self) -> dict:
        async with self.lock:
            return copy.deepcopy(self.all_data)

    async def subscriptionData(self, streams: set):
        """ 用來訂閱系統資料

        Args:
            input streams :{'DEFIUSDT', 'SOLUSDT', 'COMPUSDT', 'AAVEUSDT', 'AVAXUSDT'}
            output streams (list): ['btcusdt@kline_1m', 'ethusdt@kline_1m', 'bnbusdt@kline_1m']

        Returns:
            _type_: Not return
        """

        def changestreams(streams: set):
            return [each_stream.lower() + "@kline_1m" for each_stream in list(streams)]

        streams = changestreams(streams)

        with open(r"C:/bi_.txt", 'r') as file:
            data = file.read()
            account = data.split("\n")[0]
            passwd = data.split("\n")[1]

        client = await AsyncClient.create(account, passwd)
        bsm = BinanceSocketManager(client)

        symbols = [each.split('@')[0].upper() for each in streams]

        self.all_data = {symbol: {} for symbol in symbols}

        last_all = {symbol: 0 for symbol in symbols}

        print(f"即時行情回補, 目前商品: {symbols}")
        async with bsm.futures_multiplex_socket(streams) as stream:
            while True:
                res = await stream.recv()
                symbol = res['stream'].split('@')[0].upper()
                data = await self.process_message(res)
                await self.update_data(symbol, data)

                # if len(self.all_data[symbol]) != last_all[symbol]:
                #     print(self.all_data[symbol])
                #     print('*' * 120)
                #     last_all[symbol] = len(self.all_data[symbol])
