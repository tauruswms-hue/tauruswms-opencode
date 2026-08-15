import pymysql

password = input("Contraseña de root de MySQL (dejar vacío si no tiene): ")
root_pass = password or ''
try:
    conn = pymysql.connect(host='localhost', user='root', password=root_pass, charset='utf8mb4', port=3306)
    cursor = conn.cursor()
    cursor.execute("ALTER USER 'taurus_admin'@'localhost' IDENTIFIED BY 'Taurus_2001'")
    cursor.execute("FLUSH PRIVILEGES")
    conn.commit()
    conn.close()
    print("Contraseña de taurus_admin actualizada a Taurus_2001")
    # Probar conexion
    conn2 = pymysql.connect(host='localhost', user='taurus_admin', password='Taurus_2001', database='taurus_admin', charset='utf8mb4', port=3306)
    conn2.close()
    print("Conexion exitosa con taurus_admin!")
except Exception as e:
    print(f"ERROR: {e}")
finally:
    import os
    os.remove(__file__)
