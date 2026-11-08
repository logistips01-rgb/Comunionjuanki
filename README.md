# Álbum Pokémon de Juanki

Web estática (GitHub Pages) para fotografiar y catalogar las cartas Pokémon.

- `index.html` — inicio con estadísticas
- `subir.html` — hacer foto (o elegir varias de la galería), buscar la carta en el catálogo TCGdex para autorrellenar los datos y guardar
- `album.html` — álbum con filtros por tipo, búsqueda, orden de peor a mejor (puntuación, estrellas, rareza, valor €, PS, etapa, tipo, nombre, colección, fecha), edición/borrado y pase de diapositivas con música
- `comun.js` / `estilos.css` — configuración de Firebase, catálogos y estilos compartidos

Los datos se guardan en Firebase Realtime Database (proyecto `juanki-cfec7`):

- `pokemon/meta/{id}` — datos de la carta + miniatura
- `pokemon/img/{id}` — foto grande (se carga solo al abrir la carta o en el pase)

La web anterior de la comunión está archivada en la rama `archivo/comunion-juanki`.
