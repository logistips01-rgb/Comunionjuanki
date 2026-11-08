# Álbum Pokémon de Juanki

Web estática (GitHub Pages) para fotografiar y catalogar las cartas Pokémon.

- `index.html` — inicio con estadísticas
- `subir.html` — hacer foto (o elegir varias de la galería), buscar la carta en el catálogo TCGdex para autorrellenar los datos y guardar
- `album.html` — álbum con filtros por tipo, búsqueda, orden de peor a mejor (puntuación, estrellas, rareza, valor €, PS, etapa, tipo, nombre, colección, fecha), edición/borrado y pase de diapositivas con música
- `comun.js` / `estilos.css` — configuración de Firebase, catálogos y estilos compartidos

Los datos se guardan en Firebase Realtime Database (proyecto `juanki-cfec7`), protegidos por un PIN de 6 dígitos:

- `albumes/{clave}/ok` — marca de que el álbum existe
- `albumes/{clave}/meta/{id}` — datos de la carta + miniatura
- `albumes/{clave}/img/{id}` — foto grande (se carga solo al abrir la carta o en el pase)

`{clave}` es el SHA-256 del PIN: el PIN no aparece en el código y sin él no se sabe en qué ruta están las cartas.
Para que esto proteja de verdad, las reglas de la base de datos **no deben permitir leer la raíz ni `albumes`**
(ver `database.rules.json`, que se copia en Firebase → Realtime Database → Reglas).

El primer uso: en la pantalla del PIN pulsar **＋ Nuevo**, elegir el PIN y repetirlo.

La web anterior de la comunión está archivada en la rama `archivo/comunion-juanki`.
