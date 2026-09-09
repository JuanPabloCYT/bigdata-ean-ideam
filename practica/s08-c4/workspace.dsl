/*
 * T8 · Hito A · Nivel Frontera de la práctica de S08
 * El mismo modelo C4 de los archivos .drawio, expresado como código.
 *
 * Vía elegida del nivel Frontera: "modelo como código", no "componente suelto".
 * La razón: este proyecto ya versiona todo lo que decide (imágenes ancladas por
 * digest, dependencias con ==, evidencias en el repositorio). Un diagrama que
 * vive como texto entra en esa misma disciplina: se revisa en un diff, no se
 * compara a ojo entre dos capturas de pantalla.
 *
 * Genera las mismas tres vistas: contexto (nivel 1), contenedor (nivel 2) y
 * componente (nivel 3) de UN SOLO contenedor, la ingesta.
 *
 * Para renderizarlo:
 *   docker run -it --rm -p 8080:8080 -v "$PWD":/usr/local/structurizr structurizr/lite
 *   y abrir http://localhost:8080
 */

workspace "bigdata-ean-ideam" "Plataforma de datos de precipitación del IDEAM (s54a-sgyg)" {

    model {
        operador = person "Operador de gestión del riesgo" "Vigila la lluvia del turno y activa el protocolo ante una creciente súbita"
        analista = person "Analista de recursos hídricos" "Estudia el comportamiento de la precipitación por departamento"
        gerencia = person "Gerencia de planeación" "Recibe el consolidado mensual para planear e informar"

        socrata = softwareSystem "Portal de Datos Abiertos de Colombia" "Publica el conjunto s54a-sgyg como extracto consolidado, una vez al día" "Externo"
        telemetria = softwareSystem "Telemetría de estaciones del IDEAM" "Canal de lectura por estación. Supuesto declarado en T7; hoy no se consume" "Externo,Planificado"

        plataforma = softwareSystem "Plataforma de datos de precipitación" "Conserva la precipitación del IDEAM de forma íntegra y versionada, y la entrega ya agregada a quien decide con ella" {

            ingesta = container "Ingesta de la partición diaria" "Descarga la partición, verifica su huella SHA-256 y la deposita en la capa cruda sin reescribirla si ya existe" "Python 3.12 · boto3" {
                clienteSocrata = component "Cliente de Socrata" "Arma la consulta del día y descarga la partición paginada, concatenando los bytes crudos de la respuesta sin re-serializar" "source_url, download_source"
                claveParticion = component "Constructor de la clave particionada" "Traduce una fecha a la clave anio=/mes=/dia= del lago" "object_key"
                preparadorCubos = component "Preparador de cubos y versionado" "Crea los tres cubos si faltan y activa el versionado de la capa cruda" "ensure_buckets"
                escritorInmutable = component "Escritor inmutable" "Compara el ETag antes de escribir: si el contenido ya está, no sobrescribe" "head_object, upload_immutable"
            }

            lago = container "Lago de datos por capas" "lago-crudo, lago-refinado y lago-curado. La capa cruda es inmutable y versionada" "MinIO · API S3" "Almacen"
            refinador = container "Refinador a Parquet" "Convierte el CSV crudo a Parquet con codec zstd y lo escribe en la capa refinada" "Python · PyArrow"
            motor = container "Motor de agregación por lotes" "Agrega la precipitación promedio por departamento, con combinador" "Hadoop MapReduce Streaming"
            analitica = container "Base analítica" "Sirve el agregado con la clave candidata de T1 como clave primaria" "PostgreSQL" "Almacen"
            cuaderno = container "Cuaderno de análisis y panel" "Consulta selectiva sobre Parquet sin cargar el archivo entero, y alimenta el panel operativo" "Jupyter · DuckDB"
            detector = container "Detector de umbral de lluvia intensa" "Evalúa el umbral sobre las lecturas recientes de la cuenca y dispara la alerta en segundos" "Componente de flujo · no implementado" "Planificado"
        }

        # Nivel 1 · contexto
        socrata -> plataforma "Entrega la partición diaria" "CSV sobre HTTP · 1 vez al día · 21.953.076 B"
        telemetria -> plataforma "Enviaría las lecturas por estación" "unos 1/min por estación · planificado"
        plataforma -> operador "Dispara la alerta de creciente súbita" "segundos · planificado"
        plataforma -> operador "Actualiza el panel operativo" "casi real · cada 2-5 min"
        plataforma -> analista "Entrega la precipitación agregada por departamento" "por lotes"
        plataforma -> gerencia "Entrega el reporte mensual por departamento" "por lotes"

        # Nivel 2 · contenedor
        socrata -> ingesta "Entrega la partición" "CSV sobre HTTP, paginado"
        ingesta -> lago "Escribe la capa cruda, idempotente por ETag" "S3 PutObject"
        refinador -> lago "Lee la cruda y escribe la refinada" "S3 · Parquet zstd"
        motor -> lago "Lee la refinada y escribe el agregado en la curada" "S3 · Hadoop Streaming"
        motor -> analitica "Carga el agregado por departamento" "SQL"
        cuaderno -> lago "Consulta la capa refinada sin cargarla entera" "DuckDB sobre Parquet"
        cuaderno -> analitica "Consulta el agregado servido" "SQL"
        telemetria -> detector "Entregaría las lecturas por estación" "planificado"
        detector -> lago "Depositaría sus eventos en la cruda, para poder auditar qué vio la alerta" "planificado"

        # Nivel 3 · componentes de la ingesta
        socrata -> clienteSocrata "Responde la consulta paginada" "HTTP"
        clienteSocrata -> escritorInmutable "Entrega los bytes descargados"
        claveParticion -> escritorInmutable "Le da la clave de destino"
        preparadorCubos -> lago "Crea los cubos y activa el versionado" "S3"
        escritorInmutable -> lago "Escribe solo si el ETag difiere" "S3 PutObject"
    }

    views {
        systemContext plataforma "Nivel1Contexto" {
            include *
            autolayout tb
            description "Nivel 1 · el sistema como una sola caja, sus actores y sus fuentes externas"
        }

        container plataforma "Nivel2Contenedor" {
            include *
            autolayout lr
            description "Nivel 2 · las piezas ejecutables y los almacenes, con la vía por lotes y el componente de flujo acotado"
        }

        component ingesta "Nivel3ComponenteIngesta" {
            include *
            autolayout lr
            description "Nivel 3 · componentes de UN SOLO contenedor: la ingesta de la partición diaria"
        }

        styles {
            element "Person" {
                shape Person
                background #08427B
                color #FFFFFF
            }
            element "Software System" {
                background #1168BD
                color #FFFFFF
            }
            element "Container" {
                background #438DD5
                color #FFFFFF
            }
            element "Component" {
                background #85BBF0
                color #000000
            }
            element "Externo" {
                background #999999
                color #FFFFFF
            }
            element "Almacen" {
                shape Cylinder
            }
            element "Planificado" {
                background #A9C9E8
                color #1A1A1A
                border dashed
            }
        }
    }
}
