import pandas as pd
import mysql.connector


# đọc Excel
file = "grammar_hsk.xlsx"

df = pd.read_excel(file)


# kết nối MySQL
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="MẬT_KHẨU_MYSQL",
    database="ChineseLearning"
)

cursor = conn.cursor()


sql = """
INSERT INTO grammar
(
    hsk_level,
    title,
    explanation,
    examples,
    notes
)
VALUES
(%s,%s,%s,%s,%s)
"""


count = 0


for _, row in df.iterrows():

    data = (
        int(row["hsk_level"]),
        str(row["title"]),
        str(row["explanation"]),
        str(row["examples"]),
        str(row["notes"])
    )

    cursor.execute(sql, data)

    count += 1


conn.commit()


cursor.close()
conn.close()


print(f"Import thành công {count} ngữ pháp")