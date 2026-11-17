import pandas as pd
import mysql.connector
from datetime import datetime


# ======================
# ĐỌC FILE EXCEL
# ======================

file = r"C:\Users\khanh\OneDrive\Documents\python\chinese_learning\test_hsk.xlsx"

questions_df = pd.read_excel(file, sheet_name="test_questions")


# ======================
# KẾT NỐI MYSQL
# ======================

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="12345678",
    database="chinese_learning"
)

cursor = conn.cursor()


# ======================
# XÓA DỮ LIỆU CŨ (NẾU IMPORT LẠI)
# ======================

cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

cursor.execute("DELETE FROM test_questions")
cursor.execute("DELETE FROM tests")

cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

print("Đã xóa dữ liệu test cũ!")


# ======================
# TẠO CÁC ĐỀ HSK
# ======================

test_map = {}


# lấy các HSK + đề khác nhau
test_list = questions_df[
    ["hsk_level", "test_number"]
].drop_duplicates()


for _, row in test_list.iterrows():

    sql = """
    INSERT INTO tests
    (
        course_id,
        lesson_id,
        hsk_level,
        title,
        description,
        duration,
        passing_score,
        status,
        created_at,
        updated_at
    )
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """

    cursor.execute(sql, (
        None,
        None,
        int(row["hsk_level"]),
        f"Đề thi HSK {int(row['hsk_level'])} - Đề {int(row['test_number'])}",
        f"Bài kiểm tra HSK {int(row['hsk_level'])} đề số {int(row['test_number'])}",
        45,
        60,
        "published",
        datetime.now(),
        datetime.now()
    ))

    # lưu id đề
    test_map[
        (
            int(row["hsk_level"]),
            int(row["test_number"])
        )
    ] = cursor.lastrowid


print("Import bảng tests xong!")


# ======================
# IMPORT CÂU HỎI
# ======================

for _, row in questions_df.iterrows():

    sql = """
    INSERT INTO test_questions
    (
        test_id,
        question,
        question_type,
        option_a,
        option_b,
        option_c,
        option_d,
        correct_answer,
        explanation,
        question_order,
        score,
        created_at
    )
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """


    cursor.execute(sql, (

        test_map[
            (
                int(row["hsk_level"]),
                int(row["test_number"])
            )
        ],

        row["question"],
        row["question_type"],
        row["option_a"],
        row["option_b"],
        row["option_c"],
        row["option_d"],
        row["correct_answer"],
        row["explanation"],
        int(row["question_order"]),
        float(row["score"]),
        datetime.now()
    ))


print("Import câu hỏi xong!")


# lưu dữ liệu
conn.commit()


cursor.close()
conn.close()


print("🎉 Import đề thi HSK thành công!")