from sqlalchemy import create_engine, engine
from sqlalchemy import text


def get_mysql_financialdata_conn() -> engine.base.Connection:
    """    
    user: root
    password: 123456
    host: localhost
    port: 3306
    database: financialdata
    如果有實體 IP，以上設定可以自行更改
    Returns:
        engine.base.Connection: _description_
    """
    address = "mysql+pymysql://root:test@localhost:3306/crypto_data"
    # address = "mysql+pymysql://root:123456@localhost:3306/crypto_data"
    engine = create_engine(address)
    connect = engine.connect()

    return connect

def checkIfDataBase():
    address = "mysql+pymysql://root:test@localhost:3306"
    engine = create_engine(address)
    connection = engine.connect()

    databases = connection.execute(text("show databases like 'crypto_data';"))
    if databases.rowcount > 0:
        pass
    else:
        connection.execute(text("CREATE DATABASE crypto_data"))
        

    




if __name__ == "__main__":
    with get_mysql_financialdata_conn() as conn:
        result = conn.execute(text("select *  from `btcusdt-f-d`;"))
        print(len(list(result)))

