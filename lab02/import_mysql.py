"""实验二 第三阶段：把 data/houseinfo.csv 写入 MySQL(smartpark_lab.houseinfo)。

读取第二阶段保存的 CSV，不重新采集网页。
运行：在 workspace/lab02 下执行  python import_mysql.py
"""

import csv
from pathlib import Path

import pymysql

CSV_PATH = Path("data/houseinfo.csv")

# 与建表语句、CSV 表头保持一致的 8 个字段顺序
FIELDS = ["title", "house", "address", "struct", "area", "floor", "maketime", "price"]

DB_CONFIG = {
    "host": "mysql",          # 课程数据库服务名（Docker 内部网络）
    "port": 3306,
    "user": "student",
    "password": "123456",
    "database": "smartpark_lab",
    "charset": "utf8mb4",
    "autocommit": False,      # 关闭自动提交，由程序显式 commit / rollback
}

# 8 个字段对应 8 个 %s 占位符，值通过第二个参数传入，不做字符串拼接
INSERT_SQL = """
    INSERT INTO houseinfo
        (title, house, address, struct, area, floor, maketime, price)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""

SELECT_EXISTING_SQL = """
    SELECT title, house, address, struct, area, floor, maketime, price
    FROM houseinfo
"""


def read_csv(path=CSV_PATH):
    """读取 CSV，检查表头，按固定顺序整理成 (8 项) 元组的列表，并在文件内部去重。"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != FIELDS:
            raise ValueError(f"CSV 表头不符：{reader.fieldnames}")

        records = []
        seen = set()
        for line_no, row in enumerate(reader, start=1):
            rec = tuple(row[k] for k in FIELDS)   # 顺序固定，不丢字段
            if len(rec) != 8:
                raise ValueError(f"第 {line_no} 行字段数不是 8 个")
            if rec in seen:                       # 8 个字段完全相同的重复行，只保留一条
                continue
            seen.add(rec)
            records.append(rec)
    return records


def fetch_existing(cursor):
    """把库里已有的记录读成集合，用于重跑时判断"这条已经在库中"。"""
    cursor.execute(SELECT_EXISTING_SQL)
    return {tuple(row) for row in cursor.fetchall()}


def import_to_mysql():
    records = read_csv()
    print(f"CSV 读取完成：{len(records)} 条（已按 8 个字段去重）")

    conn = None
    cursor = None
    try:
        # ① 连接数据库，先用一条查询确认连接正常
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION(), DATABASE(), CURRENT_USER()")
        print("连接成功：", cursor.fetchone())

        # ② 比较库内已有记录，只插入尚不存在的记录（重跑不会重复插入）
        existing = fetch_existing(cursor)
        todo = [rec for rec in records if rec not in existing]
        print(f"库内已有 {len(existing)} 条，本次待插入 {len(todo)} 条")

        if not todo:
            print("没有新记录，跳过插入，避免重复。")
            return

        # ③ 先用少量真实记录试写，再用 rollback 撤销，确认事务可控
        cursor.executemany(INSERT_SQL, todo[:3])
        cursor.execute("SELECT COUNT(*) FROM houseinfo")
        print(f"试写 3 条后（未提交）条数：{cursor.fetchone()[0]}")
        conn.rollback()
        cursor.execute("SELECT COUNT(*) FROM houseinfo")
        print(f"rollback 之后条数：{cursor.fetchone()[0]}")

        # ④ 写入全部记录，成功后提交
        affected = cursor.executemany(INSERT_SQL, todo)
        conn.commit()
        print(f"executemany 影响行数：{affected}，已 commit")

        # ⑤ 提交后在同一个连接里核对条数
        cursor.execute("SELECT COUNT(*) FROM houseinfo")
        print(f"入库后条数：{cursor.fetchone()[0]}")

    except Exception as e:
        # 出错时撤销本次事务中尚未提交的修改
        if conn is not None:
            conn.rollback()
        print(f"入库失败，已 rollback：{type(e).__name__}: {e}")
        raise
    finally:
        # 成功或失败都要释放资源：先关游标，再关连接
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()
        print("游标与连接已关闭")


if __name__ == "__main__":
    import_to_mysql()
