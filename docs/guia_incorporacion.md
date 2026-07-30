# Guía de incorporación

**Reto de negocio · Sesión 2 · Competencia Power Humanise**

Bienvenido al equipo. Esta página es para que tenga el proyecto corriendo hoy mismo, sin tener que preguntarle nada a nadie.

Cuente entre 30 y 45 minutos. Casi todo es esperar descargas.

---

## Antes de empezar

Instale estas tres cosas:

1. **Git**, que es lo que guarda la historia del código. Está en <https://git-scm.com/downloads>.
2. **Docker Desktop**, que levanta el entorno ya armado para que usted no tenga que instalar nada más. Está en <https://www.docker.com/products/docker-desktop/>. Después de instalarlo, ábralo y déjelo corriendo: debe verse su icono en la barra del sistema.
3. **Un navegador**, el que ya use.

No instale Python ni PostgreSQL. El proyecto los trae adentro y tenerlos aparte solo confunde.

Necesita también unos 4 GB libres en disco y acceso al repositorio.

---

## Los pasos

**1. Abra una terminal.**
En macOS es `Terminal`; en Windows, `PowerShell`; en Linux, la que use. Todo lo que sigue se escribe ahí y se confirma con Enter.

**2. Descargue el proyecto.**

```bash
git clone https://github.com/JuanPabloCYT/bigdata-ean-ideam.git
```

**3. Entre a la carpeta.**

```bash
cd bigdata-ean-ideam
```

**4. Cree su archivo de configuración.**

```bash
cp .env.example .env
```

En PowerShell, si `cp` no le funciona, use `copy .env.example .env`.

**5. Póngale contraseña a su base de datos.**
Abra `.env` con cualquier editor y cambie la palabra `cambieme` por una contraseña que invente. Solo se usa en su equipo, así que no reutilice una que ya tenga en otro lado.

**6. Levante el entorno.**

```bash
docker compose up
```

Esto tarda entre 5 y 10 minutos la primera vez y llena la pantalla de texto. Es normal: está descargando el entorno completo. No cierre la ventana.

Durante buena parte de ese rato no va a pasar nada visible y el navegador no va a responder. También es normal: está instalando dependencias sin mostrarlo. Ya puede seguir cuando aparezca una línea con `http://127.0.0.1:8888`.

**7. Abra el proyecto.**
Vaya a <http://localhost:8888>. No le debe pedir contraseña ni token.

**8. Verifique que quedó bien.**
En el panel de la izquierda entre a `notebooks`, abra `00_verificacion.ipynb` y en el menú de arriba elija `Run` → `Run All Cells`.

---

## Cómo saber que quedó bien

El cuaderno debe terminar con estas tres líneas y sin nada en rojo:

```
Entorno reproducible verificado: todas las versiones coinciden.
Motor: PostgreSQL 16.4 ...
OK · la restricción de la base reproduce el hallazgo de T1.
```

Si las ve, terminó: tiene el mismo entorno que el resto del equipo.

---

## Si algo falla

Lo primero, que resuelve la mayoría de los casos: pare con `Ctrl + C`, confirme que Docker Desktop está abierto y corriendo, y vuelva a ejecutar `docker compose up`.

Si el error habla de un puerto ocupado (`port is already allocated`), algo más está usando el 8888 o el 5432. Abra `.env`, cambie `JUPYTER_PORT=8888` por `JUPYTER_PORT=8889` y entre a <http://localhost:8889>.

Si el error menciona `POSTGRES_PASSWORD`, se saltó el paso 4 o el 5.

Si nada de eso funciona, escríbame: Juan Pablo Castro, juanpablopug@gmail.com, o abra un *issue* en el repositorio. Mándeme tres cosas: su sistema operativo, en qué paso se quedó y el error completo copiado y pegado. No necesita entenderlo, solo copiarlo.

Y no se quede más de 30 minutos atascado en un paso. Si algo no funciona es porque a esta guía le falta algo, y arreglarlo me toca a mí. Avisar temprano ayuda.

---

## Un favor

Usted es la única persona que está leyendo esto sin saber ya cómo funciona el proyecto, y esa ventaja se pierde en dos días.

Mientras avanza, anote cualquier punto donde tuvo que adivinar, buscar por fuera o preguntar. Cuando termine, corrija esta guía directamente. No hace falta pedir permiso.

Lo pido por algo concreto: la razón de que todo esto esté montado con Docker y con versiones fijas es que un proyecto que solo funciona en el computador de una persona se pierde cuando esa persona se va. Una guía que solo sirve para quien la escribió tiene el mismo problema.
