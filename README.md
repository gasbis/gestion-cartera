# Gestión Cartera

Aplicación web personal para el seguimiento de una cartera de valores (acciones), hecha con [Reflex](https://reflex.dev) (Python full-stack, sin JavaScript). Sustituye a una hoja de Excel: registra operaciones de compra/venta, dividendos y derechos, y calcula en vivo posiciones, plusvalías, rentabilidad (TIR) y reparto por zona/sector.

## Funcionalidades

- **Acceso con usuario y contraseña.** Alta de usuarios con contraseña inicial (obliga a cambiarla en el primer inicio de sesión), cambio de contraseña y de nombre de usuario voluntarios desde el propio menú, y cierre de sesión. La página de alta/gestión de usuarios solo es accesible para el administrador (`gasbis@hotmail.com`).
- **Dos carteras por usuario** (Largo Plazo / Corto Plazo), seleccionables desde cualquier página.
- **Inicio:** resumen general (valor de compra/actual, saldo, TIR), top-5 valores por revalorización y por YOC, dividendos cobrados por año y distribución de la cartera por zona geográfica y por sector.
- **Cartera:** listado de tenencias con cotización en vivo (se refresca sola al entrar), precio medio, plusvalía, YOC del año anterior y peso en cartera; también los valores ya liquidados del todo (saldo a cero títulos), con su resultado acumulado. Buscador y orden por columna.
- **Operaciones:** alta, edición y eliminación de movimientos (Compra, Venta, Dividendo, Script/derechos, Prima. Split y Spinoff), con validaciones y cálculo automático del importe unitario.
- **Detalle de un valor:** logo de la empresa, resumen con TIR individual (con y sin revalorización), rentabilidad y operaciones agrupadas por año, e histórico completo de movimientos de ese valor.
- **Brókers:** alta de brokers y control de existencias por bróker (para cuadrar contra el extracto real), agregando ambas carteras.
- Tema oscuro fijo y diseño adaptado a tablet/móvil (tablas con scroll horizontal cuando no caben, columnas de tarjetas y gráficos que se ajustan al ancho de pantalla).

## Stack técnico

- [Reflex](https://reflex.dev) (Python) + [Radix Themes](https://www.radix-ui.com/themes) para la interfaz.
- SQLModel + SQLite como base de datos, con [Alembic](https://alembic.sqlalchemy.org/) para las migraciones.
- [yfinance](https://github.com/ranaroussi/yfinance) (Yahoo Finance, sin API key) para las cotizaciones en vivo.
- [Twelve Data](https://twelvedata.com/) para el buscador de "dar de alta un valor nuevo" (requiere API key gratuita).
- [Logo.dev](https://www.logo.dev/) para los logos de empresa en la página de detalle.
- `bcrypt` para el hash de contraseñas.

## Estructura del proyecto

```
gestion_cartera/
├── gestion_cartera.py      # App Reflex: registro de páginas y tema
├── models.py                # Tablas (Usuario, Cartera, Broker, Sector, Valor, Operacion)
├── *_db.py                  # Consultas y lógica de negocio sobre la base de datos
├── seed_sectores.py          # Carga inicial de la jerarquía de sectores (Morningstar)
├── seed_brokers.py           # Carga inicial de brokers
├── services/                 # Integraciones externas (Yahoo Finance, Twelve Data, Logo.dev)
├── states/                   # Estado de cada página (rx.State)
├── components/                # Piezas de interfaz compartidas (header, formularios, diálogos...)
└── pages/                     # Las páginas de la app (inicio, cartera, operaciones, brokers, usuarios, detalle de valor)
```

## Puesta en marcha

Requiere Python 3.14+ y [uv](https://docs.astral.sh/uv/).

1. Clona el repositorio e instala las dependencias:
   ```bash
   uv sync
   ```
2. Crea un archivo `.env` en la raíz con tu API key gratuita de Twelve Data (solo se usa para el buscador de valores nuevos):
   ```
   TWELVEDATA_API_KEY=tu_clave_aquí
   ```
   Si además quieres apuntar a un Postgres en vez de al SQLite local (ver más abajo), añade también `DATABASE_URL` a este mismo archivo.
3. Inicializa la base de datos y aplica las migraciones:
   ```bash
   uv run reflex db migrate
   ```
4. Carga los datos de referencia (una sola vez):
   ```bash
   uv run python -m gestion_cartera.seed_sectores
   uv run python -m gestion_cartera.seed_brokers
   ```
5. Da de alta el primer usuario (administrador) directamente en la base de datos, o crea un pequeño script puntual con `auth_db.crear_usuario(email, nombre, password_inicial)`.
6. Arranca la app:
   ```bash
   uv run reflex run
   ```

## Base de datos: SQLite en local, Postgres en producción

Por defecto usa SQLite (`reflex.db`), pero si la variable de entorno `DATABASE_URL` está definida, se usa esa en su lugar (ver `rxconfig.py`). En Railway, al añadir un servicio de Postgres al proyecto, esa variable se puede referenciar directamente en el servicio de la app sin copiarla a mano.

Para trabajar en local directamente contra el Postgres de producción (por ejemplo, al importar datos históricos que luego no haría falta migrar), pon su URL pública (no la interna, que solo resuelve entre servicios de Railway) en tu `.env`:

```
DATABASE_URL=postgresql://usuario:contraseña@host.railway.app:puerto/basededatos
```

y ejecuta `uv run reflex db migrate` para aplicar las migraciones también ahí antes de arrancar.

## Notas y limitaciones

- **Cotizaciones vía Yahoo Finance:** `yfinance` interpreta las páginas públicas de Yahoo, no es una API oficial. Lleva años siendo estable, pero podría dejar de funcionar si Yahoo cambia algo.
- **Acceso a Usuarios:** restringido por código a un único correo (`ADMIN_EMAIL` en `states/auth_state.py`). Si en el futuro hace falta más de un administrador, ese es el sitio donde ampliarlo.
- **Logo.dev:** usa una clave pública ("publishable key", pensada para ir en el propio código/frontend) ya incluida en `services/company_logo.py`. Al ser una app de uso privado, no aplica el requisito de atribución de la capa gratuita (solo obligatorio en uso comercial).
