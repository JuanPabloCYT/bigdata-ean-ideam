# Extiende la imagen oficial del nodemanager con Python 3.
#
# La imagen bde2020/hadoop-nodemanager corre sobre Debian Stretch, que
# ya salio de soporte y no trae Python. Hadoop Streaming ejecuta las
# tareas de map y de reduce como subprocesos del propio nodemanager
# (no en contenedores aparte), asi que el interprete tiene que existir
# AQUI, en esta imagen, no en el equipo anfitrion.
#
# Sin este Dockerfile, cualquiera que clone el repositorio y levante
# el compose obtendria mapas fallando con "subprocess failed with
# code 127" (comando no encontrado): exactamente el fallo que se
# encontro y se documenta en docs/T4_ejecucion.md.
FROM bde2020/hadoop-nodemanager:2.0.0-hadoop3.2.1-java8

USER root

# Stretch quedo fuera de soporte: sus repositorios normales devuelven
# 404. Se apunta al archivo historico de Debian y se desactivan las
# comprobaciones de vigencia de firma, porque un repositorio
# archivado por definicion ya "vencio" y eso es exactamente lo que se
# espera de el.
RUN echo "deb http://archive.debian.org/debian stretch main" > /etc/apt/sources.list \
 && echo "deb http://archive.debian.org/debian-security stretch/updates main" >> /etc/apt/sources.list \
 && apt-get -o Acquire::Check-Valid-Until=false update \
 && apt-get -o Acquire::Check-Valid-Until=false install -y --no-install-recommends python3 \
 && rm -rf /var/lib/apt/lists/*
