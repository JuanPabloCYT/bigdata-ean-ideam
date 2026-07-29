# Guía de incorporación · su primer día en el equipo de datos

**Reto de negocio · Sesión 2 · Competencia Power Humanise**

Bienvenido. Al terminar esta página debería tener el proyecto corriendo en su equipo, sin haberle preguntado nada a nadie. Si tiene que preguntar, la guía está mal y queremos saberlo: eso se arregla al final de esta página.

Tómese entre 30 y 45 minutos. La mayor parte es esperar descargas.

---

## Antes de empezar: instale estas tres cosas

1. **Git** — el sistema que guarda la historia del código. Descárguelo de <https://git-scm.com/downloads>.
2. **Docker Desktop** — el programa que levanta el entorno de trabajo ya armado, para que usted no tenga que instalar Python ni bases de datos a mano. Descárguelo de <https://www.docker.com/products/docker-desktop/> y **ábralo**: debe quedar corriendo, con su icono visible en la barra del sistema.
3. **Un navegador web** — el que ya usa.

No instale Python. No instale PostgreSQL. El proyecto los trae adentro; instalarlos por su cuenta no ayuda y puede confundir.

Necesitará también unos 4 GB libres en disco y su usuario de acceso al repositorio.

---

## Los pasos

**1. Abra una terminal.**
En macOS, `Terminal`. En Windows, `PowerShell`. En Linux, la que use. Todos los comandos de aquí en adelante se escriben ahí y se confirman con Enter.

**2. Descargue el proyecto.**

```bash
git clone <URL-DEL-REPOSITORIO>
```

**3. Entre a la carpeta que acaba de crearse.**

```bash
cd proyecto-ideam-precipitacion
```

**4. Cree su archivo de configuración personal.**

```bash
cp .env.example .env
```

En Windows con PowerShell, si `cp` no funciona: `copy .env.example .env`.

**5. Póngale una contraseña a su base de datos local.**
Abra el archivo `.env` con cualquier editor de texto y reemplace la palabra `cambieme` por cualquier contraseña que invente. Solo se usa en su equipo. No use una contraseña que ya utilice en otro lado.

**6. Levante el entorno.**

```bash
docker compose up
```

**La primera vez tarda entre 5 y 10 minutos** y llena la pantalla de texto. Es normal: está descargando el entorno completo. No cierre la ventana. Cuando deje de moverse y aparezca una línea con `http://127.0.0.1:8888`, ya está listo.

**7. Abra el proyecto en el navegador.**
Vaya a <http://localhost:8888>. No debería pedirle contraseña ni token.

**8. Compruebe que todo quedó bien.**
En el panel izquierdo entre a `notebooks` y abra `00_verificacion.ipynb`. En el menú de arriba: `Run` → `Run All Cells`.

---

## Cómo saber que quedó bien

El cuaderno debe terminar mostrando estas tres líneas, sin errores en rojo:

```
Entorno reproducible verificado: todas las versiones coinciden.
Motor: PostgreSQL 16.4 ...
OK · la restricción de la base reproduce el hallazgo de T1.
```

Si ve las tres, terminó: tiene el mismo entorno que el resto del equipo y puede empezar a trabajar.

---

## Si algo falla

**Primero, lo que resuelve la mayoría de los casos:** detenga el proceso con `Ctrl + C`, confirme que Docker Desktop está abierto y corriendo, y ejecute `docker compose up` otra vez.

**Si el error menciona un puerto ocupado** (`port is already allocated`), otro programa está usando el puerto 8888 o el 5432. Abra `.env`, cambie `JUPYTER_PORT=8888` por `JUPYTER_PORT=8889`, y entre a <http://localhost:8889> en lugar del anterior.

**Si el error dice `POSTGRES_PASSWORD`**, se saltó el paso 4 o el 5.

**Si no funciona ninguna de las anteriores:** escriba a Juan Pablo Castro (juanpablopug@gmail.com) o abra un *issue* en el repositorio. Incluya tres cosas: su sistema operativo, el número del paso donde se quedó, y copie y pegue el error completo. No es necesario que entienda el error; con que lo copie es suficiente.

**No pierda más de 30 minutos atascado en un paso.** Si algo no funciona, la guía tiene un vacío y arreglarlo es trabajo nuestro, no suyo. Preguntar temprano nos ayuda.

---

## Una última cosa, y es la más importante

Usted es la persona con la mirada más valiosa sobre este documento: es la única que lo está leyendo sin saber ya cómo funciona el proyecto. Esa ventaja se pierde en un par de días.

Mientras avanza, anote cualquier punto donde tuvo que suponer algo, buscar por fuera o preguntar. Al terminar, edite esta guía y corríjala. No hace falta pedir permiso.

La razón es concreta: este equipo ya perdió un reporte semanal porque el entorno que lo producía vivía en el portátil de una sola persona, que se fue. Todo este montaje existe para que eso no vuelva a pasar, y una guía que solo funciona para quien la escribió repetiría el mismo error en otra forma.
