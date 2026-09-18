# Ofertas para mi CV

App que toma tu CV (PDF o texto), consulta la **API pública de RemoteOK** y lista ofertas **reales/activas** ordenadas por afinidad.

## Fuente de datos (exacta)
- **RemoteOK API**: `GET https://remoteok.com/api`
- Header obligatorio: `User-Agent` personalizado (sin API key)
- Se conserva el `apply_url` literal de la API
- Antes de mostrar una oferta se hace GET real a `apply_url` y solo pasan las que responden **200**

No se usan bolsas argentinas en este repo (no hay API pública gratuita confiable de Bumeran/Computrabajo/ZonaJobs aquí).

## Stack
1. Python (`requests`, Flask, scikit-learn, pypdf)
2. HTML + JavaScript
3. SQLite

## Instalación
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución
```bash
python app.py
```
http://127.0.0.1:5055

## Tests
```bash
pytest -q
pytest -q -m integration
```
