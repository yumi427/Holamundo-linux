# Parte 3 sobre TU proyecto: qué carpetas cambian

Ya tienes el lab de las clases 13 y 14 funcionando, con tu repo y tus rutas. Copia del zip **solo esto** encima de tu carpeta del lab:

| Carpeta | Qué haces | Qué trae |
|---|---|---|
| `back/` | **reemplaza la carpeta completa** | `app.py` y `test_app.py` nuevos + `requirements.txt` (el SDK de X-Ray) |
| `front/` | **reemplaza la carpeta completa** | la sección 🔭 Observar con las 4 pruebas |
| `terraform/` | **agrega** `observabilidad.tf` y **reemplaza** `main.tf` | los ojos (SNS, alarmas, consultas, tablero) y la Lambda con trazas |
| `bootstrap/` | **reemplaza** `main.tf` y **agrega** `pipeline.yml.tpl` | más permisos para el pipeline y la plantilla del pipeline nuevo |
| `.gitignore` | **reemplaza** el archivo | ignora `paquete/` (lo arma el pipeline) |

## Lo que NO tocas (es tuyo)

| Archivo | Por qué |
|---|---|
| `bootstrap/terraform.tfstate` (y `.terraform/`, `.terraform.lock.hcl`) | el estado del bootstrap: sin él, el apply quiere crear todo otra vez |
| `terraform/backend.hcl` | el nombre de TU bucket del estado |
| `.github/workflows/pipeline.yml` | no lo editas a mano: lo reescribe el bootstrap con tus rutas |

El zip no trae ninguno de esos tres, así que copiarlo encima no los pisa.

## ¿Cambiaste algo dentro de esos archivos?

| Si cambiaste… | Haz esto |
|---|---|
| precios o productos en `back/app.py` | vuelve a ponerlos en `PRECIOS` (y en `test_precios_oficiales` de `test_app.py`) |
| el título u otro texto en `front/index.html` | vuelve a cambiarlo después de copiar |
| la memoria u otro valor en `terraform/main.tf` | en vez de reemplazarlo, agrégale solo esto dentro de `resource "aws_lambda_function" "back"`, después de `environment { … }`: `tracing_config { mode = "Active" }` |
| el nombre de la tienda (algo distinto de `tienda-cicd`) | cambia también `tienda-cicd` en `bootstrap/main.tf`, `bootstrap/pipeline.yml.tpl`, `terraform/observabilidad.tf` y `back/app.py` |

## Y después, el README desde el PASO 12 · punto 2

1. Rama: `git checkout -b los-ojos`.
2. En `bootstrap`: `terraform apply` con **los mismos valores de la clase 13** (tu `repo_github` y, si el lab está en una subcarpeta, `-var="carpeta=$c"`).
   Debe decir `1 added, 1 changed, 1 destroyed`: amplía los permisos del rol, reescribe tu `pipeline.yml` y borra `parte2/`.
3. Secreto `CORREO` en GitHub (Settings → Secrets and variables → Actions).
4. `git add .` (subcarpeta: `git add . ":/.github"`), commit, push y pull request: **12 pruebas** y `Plan: 9 to add, 1 to change`.
