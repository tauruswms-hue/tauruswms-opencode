"""
Script para crear las tablas en la base de datos taurus_wms
"""
import pymysql


def crear_tablas():
    print("📊 CREACIÓN DE TABLAS TAURUS WMS")
    print("=" * 50)

    # Configuración de conexión
    config = {
        'host': 'localhost',
        'user': 'taurus',
        'password': 'Taurus_2001',
        'database': 'taurus_wms',
        'charset': 'utf8'
    }

    try:
        # Conectar a MySQL
        conn = pymysql.connect(**config)
        cursor = conn.cursor()

        print("✅ Conectado a MySQL")

        # ============================================
        # 1. TABLA MATERIALES
        # ============================================
        print("\n📦 Creando tabla 'materiales'...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS materiales (
                id INT AUTO_INCREMENT PRIMARY KEY,
                codigo VARCHAR(50) UNIQUE NOT NULL COMMENT 'Código único del material',
                nombre VARCHAR(200) NOT NULL COMMENT 'Nombre del material',
                descripcion TEXT COMMENT 'Descripción detallada',
                unidad_medida VARCHAR(20) DEFAULT 'UN' COMMENT 'UN, KG, M, L, etc.',
                peso_unitario DECIMAL(10,3) DEFAULT 0.000 COMMENT 'Peso en kg',
                volumen_unitario DECIMAL(10,3) DEFAULT 0.000 COMMENT 'Volumen en m³',
                stock_actual INT DEFAULT 0 COMMENT 'Stock actual disponible',
                stock_minimo INT DEFAULT 0 COMMENT 'Stock mínimo alerta',
                stock_maximo INT DEFAULT 0 COMMENT 'Stock máximo capacidad',
                costo_promedio DECIMAL(10,2) DEFAULT 0.00 COMMENT 'Costo promedio',
                ultimo_costo DECIMAL(10,2) DEFAULT 0.00 COMMENT 'Último costo de compra',
                activo BOOLEAN DEFAULT TRUE COMMENT 'Activo/Inactivo',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Fecha creación',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Fecha actualización',

                INDEX idx_codigo (codigo),
                INDEX idx_nombre (nombre),
                INDEX idx_activo (activo)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("   ✅ Tabla 'materiales' creada")

        # ============================================
        # 2. TABLA UBICACIONES
        # ============================================
        print("\n🏢 Creando tabla 'ubicaciones'...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ubicaciones (
                id INT AUTO_INCREMENT PRIMARY KEY,
                codigo VARCHAR(50) UNIQUE NOT NULL COMMENT 'Código único de ubicación',
                nombre VARCHAR(100) NOT NULL COMMENT 'Nombre descriptivo',
                tipo VARCHAR(20) DEFAULT 'ESTANTE' COMMENT 'ESTANTE, PISO, RACK, RECIBO',
                zona VARCHAR(50) COMMENT 'ZONA_A, ZONA_B, PICKING, RESERVA',
                pasillo VARCHAR(10) COMMENT 'Número de pasillo',
                estante VARCHAR(10) COMMENT 'Número de estante',
                nivel VARCHAR(10) COMMENT 'Nivel del estante',
                posicion VARCHAR(10) COMMENT 'Posición en el nivel',
                capacidad_maxima INT DEFAULT 0 COMMENT 'Capacidad máxima en unidades',
                ocupado INT DEFAULT 0 COMMENT 'Unidades ocupadas actualmente',
                activo BOOLEAN DEFAULT TRUE COMMENT 'Activo/Inactivo',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Fecha creación',

                INDEX idx_codigo (codigo),
                INDEX idx_zona (zona),
                INDEX idx_tipo (tipo),
                INDEX idx_activo (activo)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("   ✅ Tabla 'ubicaciones' creada")

        # ============================================
        # 3. TABLA USUARIOS
        # ============================================
        print("\n👤 Creando tabla 'usuarios'...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL COMMENT 'Nombre de usuario',
                email VARCHAR(100) UNIQUE NOT NULL COMMENT 'Correo electrónico',
                password_hash VARCHAR(255) NOT NULL COMMENT 'Hash de contraseña',
                nombre_completo VARCHAR(100) NOT NULL COMMENT 'Nombre completo',
                rol VARCHAR(20) DEFAULT 'OPERADOR' COMMENT 'ADMIN, SUPERVISOR, OPERADOR',
                activo BOOLEAN DEFAULT TRUE COMMENT 'Activo/Inactivo',
                ultimo_acceso TIMESTAMP NULL COMMENT 'Último acceso al sistema',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Fecha creación',

                INDEX idx_username (username),
                INDEX idx_email (email),
                INDEX idx_rol (rol)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("   ✅ Tabla 'usuarios' creada")

        # ============================================
        # 4. TABLA MOVIMIENTOS
        # ============================================
        print("\n🔄 Creando tabla 'movimientos'...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movimientos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tipo VARCHAR(20) NOT NULL COMMENT 'ENTRADA, SALIDA, TRASLADO, AJUSTE',
                numero_documento VARCHAR(50) COMMENT 'Número de documento externo',
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Fecha del movimiento',
                material_id INT NOT NULL COMMENT 'ID del material',
                ubicacion_origen_id INT COMMENT 'ID ubicación origen (para traslados/salidas)',
                ubicacion_destino_id INT COMMENT 'ID ubicación destino (para entradas/traslados)',
                cantidad INT NOT NULL COMMENT 'Cantidad movida',
                observaciones TEXT COMMENT 'Observaciones del movimiento',
                estado VARCHAR(20) DEFAULT 'COMPLETADO' COMMENT 'PENDIENTE, COMPLETADO, CANCELADO',
                created_by INT COMMENT 'ID usuario que creó el movimiento',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Fecha creación registro',

                INDEX idx_tipo (tipo),
                INDEX idx_fecha (fecha),
                INDEX idx_material (material_id),
                INDEX idx_documento (numero_documento),
                INDEX idx_estado (estado),

                FOREIGN KEY (material_id) 
                    REFERENCES materiales(id) 
                    ON DELETE RESTRICT ON UPDATE CASCADE,

                FOREIGN KEY (ubicacion_origen_id) 
                    REFERENCES ubicaciones(id) 
                    ON DELETE SET NULL ON UPDATE CASCADE,

                FOREIGN KEY (ubicacion_destino_id) 
                    REFERENCES ubicaciones(id) 
                    ON DELETE SET NULL ON UPDATE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("   ✅ Tabla 'movimientos' creada")

        # ============================================
        # 5. TABLA CATEGORÍAS (opcional)
        # ============================================
        print("\n📂 Creando tabla 'categorias'...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categorias (
                id INT AUTO_INCREMENT PRIMARY KEY,
                codigo VARCHAR(20) UNIQUE NOT NULL COMMENT 'Código de categoría',
                nombre VARCHAR(100) NOT NULL COMMENT 'Nombre de la categoría',
                descripcion TEXT COMMENT 'Descripción',
                activo BOOLEAN DEFAULT TRUE COMMENT 'Activo/Inactivo',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Fecha creación'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("   ✅ Tabla 'categorias' creada")

        # ============================================
        # 6. TABLA PROVEEDORES (opcional)
        # ============================================
        print("\n🏭 Creando tabla 'proveedores'...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proveedores (
                id INT AUTO_INCREMENT PRIMARY KEY,
                codigo VARCHAR(20) UNIQUE NOT NULL COMMENT 'Código de proveedor',
                nombre VARCHAR(200) NOT NULL COMMENT 'Nombre del proveedor',
                ruc VARCHAR(20) COMMENT 'RUC o identificador fiscal',
                direccion TEXT COMMENT 'Dirección',
                telefono VARCHAR(50) COMMENT 'Teléfono',
                email VARCHAR(100) COMMENT 'Email',
                activo BOOLEAN DEFAULT TRUE COMMENT 'Activo/Inactivo',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Fecha creación'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("   ✅ Tabla 'proveedores' creada")

        # ============================================
        # 7. TABLA STOCK POR UBICACIÓN (para tracking detallado)
        # ============================================
        print("\n📍 Creando tabla 'stock_ubicaciones'...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_ubicaciones (
                id INT AUTO_INCREMENT PRIMARY KEY,
                material_id INT NOT NULL COMMENT 'ID del material',
                ubicacion_id INT NOT NULL COMMENT 'ID de la ubicación',
                cantidad INT DEFAULT 0 COMMENT 'Cantidad en esta ubicación',
                lote VARCHAR(50) COMMENT 'Número de lote',
                fecha_vencimiento DATE COMMENT 'Fecha de vencimiento',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Fecha creación',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Fecha actualización',

                UNIQUE KEY uq_material_ubicacion_lote (material_id, ubicacion_id, lote),

                INDEX idx_material (material_id),
                INDEX idx_ubicacion (ubicacion_id),
                INDEX idx_lote (lote),

                FOREIGN KEY (material_id) 
                    REFERENCES materiales(id) 
                    ON DELETE CASCADE ON UPDATE CASCADE,

                FOREIGN KEY (ubicacion_id) 
                    REFERENCES ubicaciones(id) 
                    ON DELETE CASCADE ON UPDATE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("   ✅ Tabla 'stock_ubicaciones' creada")

        # Commit los cambios
        conn.commit()

        # ============================================
        # VERIFICACIÓN FINAL
        # ============================================
        print("\n🔍 Verificando tablas creadas...")
        cursor.execute("SHOW TABLES")
        tablas = cursor.fetchall()

        print("\n📊 RESUMEN DE TABLAS CREADAS:")
        for i, tabla in enumerate(tablas, 1):
            print(f"   {i:2}. {tabla[0]}")

        print(f"\n✅ Total: {len(tablas)} tablas creadas en 'taurus_wms'")

        # Cerrar conexión
        cursor.close()
        conn.close()

        print("\n🎉 ¡Base de datos configurada exitosamente!")
        print("\n💡 Próximos pasos:")
        print("   1. Ejecutar: python crear_datos_ejemplo.py")
        print("   2. Modificar tu app.py para usar estas tablas")

    except pymysql.err.OperationalError as e:
        print(f"❌ Error de conexión: {e}")
        print("\n💡 Asegúrate de que:")
        print("   - MySQL esté corriendo")
        print("   - La base de datos 'taurus_wms' exista")
        print("   - El usuario 'taurus' tenga privilegios")
        print("\n   Ejecuta primero: python crear_base_datos.py")

    except Exception as e:
        print(f"❌ Error inesperado: {e}")


if __name__ == "__main__":
    crear_tablas()