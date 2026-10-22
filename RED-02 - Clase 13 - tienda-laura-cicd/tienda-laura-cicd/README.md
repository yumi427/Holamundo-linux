# La tienda de Laura con CI/CD (GitHub Actions + Terraform en el pipeline)

Laboratorio de las clases 13 y 14 · Esumer · Cloud Computing, Redes y Ciberseguridad.

La misma tienda serverless de la clase pasada, pero ahora **nadie la sube a mano, ni siquiera con Terraform**.
Va en dos partes: **primero toda la infraestructura, después la aplicación**.

| | Parte 1 · clase 13 · **la infraestructura** | Parte 2 · clase 14 · **la aplicación** |
|---|---|---|
| El pipeline | **1 · infra**: `terraform apply` en cada push a main y `terraform plan` en cada pull request | **1 · infra** → **2 · back** y **2 · front** (probar → empaquetar → publicar) → **3 · finalizar** |
| Qué haces | bootstrap, primer push, el estado en S3, un cambio por pull request y el candado | activas la app, cambias el título, rompes un precio y proteges main |
| Al terminar | **NO destruyas nada**: la infraestructura sigue para la parte 2 | destruyes todo, en orden |

- El **estado** de Terraform vive en un bucket S3 **con versiones y candado**, no en ningún PC.
- GitHub entra a tu AWS **sin llaves**, con un pase temporal (OIDC) y dos roles: uno que solo mira (plan) y otro que aplica (apply).
- Lo único que corres a mano es el **bootstrap**, una sola vez: crea el bucket del estado y los roles.
  Es el huevo y la gallina: el pipeline guarda su estado en ese bucket, así que el bucket tiene que existir antes.

```
tienda-laura-cicd/
├── front/                 ← FRONT: S3 + CloudFront (lo sube el pipeline · parte 2)
│   ├── index.html
│   ├── estilos.css
│   └── app.js
├── back/                  ← BACK: la Lambda (lo empaqueta y lo sube el pipeline · parte 2)
│   ├── app.py                 valida, pone el precio y guarda
│   └── test_app.py            las pruebas que corre el pipeline
├── bootstrap/             ← PASO 2: lo ÚNICO a mano (una vez, desde tu PC)
│   ├── main.tf                bucket del estado + proveedor OIDC + roles plan y apply
│   ├── pipeline-1-infra.yml.tpl   plantilla del pipeline de la parte 1
│   └── pipeline-2-app.yml.tpl     plantilla del pipeline de la parte 2
├── terraform/             ← la infraestructura: la aplica el PIPELINE, no tú
│   ├── main.tf                backend "s3" + toda la infraestructura (la Lambda nace con un código de espera)
│   └── backend.hcl            ← lo escribe bootstrap (el nombre de TU bucket del estado)
├── .github/workflows/
│   └── pipeline.yml           ← lo escribe bootstrap: el de la PARTE 1 (solo infra)
├── parte2/
│   └── pipeline.yml           ← lo escribe bootstrap: el de la PARTE 2 (infra + app), guardado para la clase 14
├── .gitignore                 lo que nunca se sube a GitHub
├── .gitattributes             finales de línea iguales en Windows y en GitHub
└── politica-iam-cicd.json
```

# PARTE 1 · Clase 13: la infraestructura se publica sola

## Lo que necesitas

- Una cuenta de GitHub (gratis): https://github.com/signup
- Git instalado. En la terminal de VS Code: `git --version`. Si dice que no se reconoce,
  instala Git para Windows (https://git-scm.com/download/win) y **cierra y vuelve a abrir VS Code**.
- Terraform **1.10 o más nuevo**: `terraform version` (el candado del estado en S3 llegó en la 1.10).
- Tu usuario `terraform-lab` de AWS, el de las clases pasadas.

## PASO 0 · Permisos de terraform-lab (una sola vez)

IAM → Usuarios → `terraform-lab` → Agregar permisos:

1. Adjuntar políticas directamente (si no las tienes de las clases pasadas): `AmazonS3FullAccess`, `AWSLambda_FullAccess`,
   `AmazonAPIGatewayAdministrator`, `AmazonDynamoDBFullAccess` y `CloudFrontFullAccess`
   (las necesitas al final, para destruir desde tu PC).
2. Crear política insertada → pestaña **JSON** → pega `politica-iam-cicd.json` → nombre `solo-roles-y-github`.

## PASO 1 · Crea tu repositorio en GitHub

GitHub → **New repository** → nombre `tienda-laura` → **Private** → **no** marques "Add a README" → **Create repository**.

Copia tu `usuario/tienda-laura` de la URL, **exacto** (con las mismas mayúsculas).

## PASO 2 · El bootstrap (lo único a mano)

En la terminal de VS Code, **dentro de la carpeta `bootstrap`**:

```powershell
cd bootstrap
terraform init
terraform apply
```

Te pregunta `var.repo_github`: escribe tu `usuario/tienda-laura` y Enter. Luego **yes**.
Tarda menos de 1 minuto: **13 recursos** (12 si tu cuenta ya tenía el proveedor de GitHub).

Al terminar aparecieron tres archivos con TUS datos:

- `terraform/backend.hcl` → el nombre de tu bucket del estado (`tienda-estado-<tu número de cuenta>`).
- `.github/workflows/pipeline.yml` → el pipeline de **hoy**: solo la infraestructura.
- `parte2/pipeline.yml` → el pipeline **completo**, guardado para la clase 14.

Fíjate: **la infraestructura todavía no existe**. Esa la va a crear el pipeline.

> **¿Usas un repositorio que ya tienes?** (el lab queda en una subcarpeta, no en la raíz)
> GitHub solo corre los pipelines de `.github/workflows/` en la **raíz** del repositorio.
> Dile a bootstrap dónde está el lab, con la ruta desde la raíz de tu repo:
>
> ```powershell
> terraform apply -var="carpeta=RED-02/tienda-laura-cicd"
> ```
>
> Así el `pipeline.yml` queda en la raíz de tu repo, corre dentro de tu carpeta y solo se dispara
> cuando cambia algo del lab. En `repo_github` escribe ese repositorio (ejemplo `tu-usuario/mi-repo`).
> En el PASO 3 no hagas `git init` ni `git remote add`: tu repo ya existe. Desde la carpeta del lab basta:
> `git add .` · `git add ../.github` (o la ruta hasta la raíz) · `git commit` · `git push`.

## PASO 3 · El primer push: el pipeline crea la infraestructura

Vuelve a la carpeta principal y sube todo a GitHub (cambia `TU-USUARIO`):

```powershell
cd ..
git config --global user.name "Tu Nombre"
git config --global user.email "tu-correo@ejemplo.com"
git init
git add .
git commit -m "primera version de la tienda"
git branch -M main
git remote add origin https://github.com/TU-USUARIO/tienda-laura.git
git push -u origin main
```

La primera vez se abre el navegador para que entres a GitHub. En tu repositorio, pestaña **Actions**:

**1 · Infra (terraform apply)** ✅ → `terraform init` (estado en S3) y `terraform apply`: **13 recursos**, ≈ 4 min por CloudFront.

Abre la ejecución: abajo, en el **resumen**, sale **"Infraestructura lista: https://…cloudfront.net"**. Ábrela:
dice **"🧱 La infraestructura ya está lista"**. La tabla, la Lambda, el API, el bucket y CloudFront existen, y nadie corrió `terraform apply` en su PC.
La tienda de verdad (el back y el front) llega en la parte 2.

## PASO 4 · El estado por dentro

Consola de AWS → **S3** → `tienda-estado-<tu número de cuenta>` → `tienda/` → `terraform.tfstate`:

- Pestaña **Versiones** (activa "Mostrar versiones"): hay **una versión por cada apply** del pipeline.
  Si un estado se daña, se recupera la versión anterior.
- Descárgalo y ábrelo en VS Code: es un JSON con **todo** lo que Terraform creó (por eso es privado y cifrado).

Ahora mira el mismo estado **desde tu PC**:

```powershell
cd terraform
terraform init -backend-config=backend.hcl
terraform state list
terraform plan
cd ..
```

`state list` muestra los 13 recursos que creó el pipeline y `plan` dice **No changes**: tu PC y el pipeline ven **el mismo estado**.

## PASO 5 · Un cambio de infraestructura por pull request

En una empresa nadie cambia main directo: se abre una **rama** y un **pull request**, y el pipeline muestra el `plan` para que alguien lo revise.

```powershell
git checkout -b mas-memoria
```

En `terraform/main.tf` cambia la memoria de la Lambda: `memory_size = 128` → `memory_size = 256`. Y:

```powershell
git add .
git commit -m "lambda con mas memoria"
git push -u origin mas-memoria
```

En GitHub sale el botón **Compare & pull request** → **Create pull request**. En la pestaña **Checks** o **Actions**:

**Revisar (terraform plan)** ✅ → en el resumen: **Plan: 0 to add, 1 to change, 0 to destroy** y,
en "Ver el plan completo", `~ memory_size = 128 -> 256`. **Nada cambió todavía en AWS**: el rol `tienda-cicd-plan` solo puede mirar.

Revisa el plan y, si está bien, **Merge pull request** → **Confirm merge**. Eso es un push a main:
en **Actions** corre **1 · Infra** y ahora sí, `1 changed`. Compruébalo en la consola: Lambda → `tienda-cicd` → Configuración → Memoria **256 MB**.

Vuelve a main en tu PC:

```powershell
git checkout main
git pull
```

## PASO 6 · Reto: el candado en acción

En **Actions** → **Pipeline de la tienda de Laura** → **Run workflow** y, **mientras corre 1 · Infra**:

- En S3, recarga `tienda/`: aparece **`terraform.tfstate.tflock`**, el candado. Cuando el apply termina, desaparece.
- En tu PC:

```powershell
cd terraform
terraform plan
```

Terraform responde **Error acquiring the state lock** con el `Who` y el `Created` del pipeline: el candado evita que dos personas (o una persona y el pipeline) cambien la infraestructura al mismo tiempo.
Espera a que el pipeline termine y vuelve a correrlo: ahora sí funciona.

## Al terminar la parte 1: NO destruyas

La infraestructura se queda encendida hasta la clase 14 (cuesta prácticamente cero: todo es serverless y se cobra por uso).
**No borres la carpeta** `tienda-laura-cicd`: en `bootstrap/` está el estado del bootstrap.

# PARTE 2 · Clase 14: la aplicación se publica sola

## PASO 7 · Activa la aplicación en el pipeline

Copia el pipeline completo encima del de la parte 1 y súbelo, en la carpeta principal:

```powershell
Copy-Item parte2\pipeline.yml .github\workflows\pipeline.yml
git add .
git commit -m "pipeline completo: infra y aplicacion"
git push
```

> Si el lab está en una subcarpeta de otro repo, el destino es el `.github\workflows\pipeline.yml` de la **raíz**
> de ese repo (ejemplo: `Copy-Item parte2\pipeline.yml ..\.github\workflows\pipeline.yml`).

En **Actions** ahora el pipeline tiene cuatro trabajos, en este orden:

```
1 · Infra (terraform apply) ──┬──▶ 2 · Back  (probar → zip → Lambda)       ──┬──▶ 3 · Finalizar
                              └──▶ 2 · Front (probar → versión → S3)         ──┘
```

1. **1 · Infra** ✅ → `terraform apply` dice **No changes**: la infraestructura ya estaba.
2. **2 · Back** ✅ y **2 · Front** ✅, al mismo tiempo: cada uno se **prueba**, se **empaqueta** y se **publica**
   (el back como zip a la Lambda, el front como archivos al bucket S3).
3. **3 · Finalizar** ✅ → abre la tienda y el API en vivo.

En el **resumen** sale **"Tienda publicada: https://…"**: es el mismo link de la parte 1, pero ahora con la tienda de verdad.
La franja dice **"Publicada por GitHub Actions · commit …"**.

## PASO 8 · Cambia la tienda con un push

Abre `front/index.html`, cambia el título (`Ropa que <em>llega volando</em>.`) por lo que quieras y:

```powershell
git add .
git commit -m "nuevo titulo"
git push
```

En **Actions** mira **1 · Infra**: el `terraform apply` dice **No changes** (la infraestructura no cambió); el back y el front se vuelven a probar, empaquetar y publicar.
En ≈ 1 minuto recarga tu tienda: el cambio y el commit nuevo ya están en internet.

## PASO 9 · El error que el pipeline atrapa

En `back/app.py` cambia el precio de la camiseta de `59000` a `5900` (un cero de menos) y haz push.
En **Actions**: **1 · Infra** ✅ (No changes), **2 · Front** ✅ y **2 · Back** ❌ en *Probar el back* (falla `test_precios_oficiales`):
el back **no se empaqueta ni se sube**, y **3 · Finalizar** ni arranca. Tu tienda **sigue funcionando** con el precio bueno. Para arreglarlo:

```powershell
git revert HEAD --no-edit
git push
```

## PASO 10 · La regla: a main solo se llega por pull request

Repositorio → **Settings** → **Rules** → **Rulesets** → **New ruleset** → **New branch ruleset**:

- Nombre: `main protegido` · Enforcement status: **Active**
- Target branches → **Add target** → **Include default branch**
- Marca **Require a pull request before merging**
- Marca **Require status checks to pass** → **Add checks** → `Revisar (pruebas + terraform plan)`
- **Create**

Prueba: cambia algo del front en main y haz `git push`. GitHub lo **rechaza** (`GH013: Repository rule violations`):
desde ahora todo cambio pasa por un pull request con pruebas y plan en verde.

> Si GitHub te avisa que el ruleset *won't be enforced* (no se aplicará) en este repositorio privado, es porque el plan gratis no aplica reglas en repos privados.
> La regla queda escrita, pero no bloquea: en las empresas (GitHub Team o Enterprise) sí.

## PASO 11 · Al terminar: destruir EN ORDEN (¡importante!)

Primero **la tienda** (su estado está en el bucket) y **después** el bootstrap (que borra el bucket):

```powershell
cd terraform
terraform init -backend-config=backend.hcl
terraform destroy          # yes · Destroy complete! Resources: 13 destroyed.

cd ../bootstrap
terraform destroy          # yes · Destroy complete! Resources: 13 destroyed.
```

Si lo haces al revés, se borra el estado y Terraform ya no sabe qué destruir: tocaría borrar la tienda a mano en la consola.
Fíjate en el primero: **el pipeline creó la tienda y tu PC la destruye**, porque los dos leen el mismo estado en S3.

El repositorio de GitHub puedes dejarlo: sin los roles, el pipeline ya no puede entrar a tu AWS.

## Lab vs. empresa

| | Este lab | Una empresa |
|---|---|---|
| Estado | S3 con versiones y candado ✅ | igual (a veces, en Terraform Cloud) |
| Plan en cada pull request y apply al unir a main | ✅ | igual, y a veces el apply espera una aprobación (*environment*) |
| Entrada sin llaves (OIDC) con roles separados | ✅ | igual, y una cuenta de AWS por ambiente (dev, prod) |
| Bootstrap | a mano, desde tu PC | una sola vez, lo hace el equipo de plataforma |

## Si algo falla

| Mensaje | Qué hacer |
|---|---|
| `Not authorized to perform sts:AssumeRoleWithWebIdentity` (en Actions) | El repositorio quedó mal escrito o con otras mayúsculas. En `bootstrap`: `terraform apply -var="repo_github=TU-USUARIO/tienda-laura"`, `git add .`, commit, push (el `pipeline.yml` no cambia, pero los roles sí). Revisa también que la rama sea `main`. |
| `EntityAlreadyExists ... oidc-provider` (en el bootstrap) | Tu cuenta ya tiene el proveedor de GitHub: `terraform apply -var="crear_proveedor=false"`. |
| `BucketAlreadyExists` o `BucketAlreadyOwnedByYou` (en el bootstrap) | Ya hiciste el bootstrap antes en esta cuenta y se perdió su estado. Borra el bucket `tienda-estado-…` en la consola (vacíalo primero) y repite. |
| `AccessDenied ... CreateOpenIDConnectProvider` o `CreateRole` | Falta la política del PASO 0. |
| `Unsupported argument ... use_lockfile` | Tu Terraform es anterior a la 1.10: actualízalo (`terraform version`). |
| **2 · Back** ❌ en *Subir el back a Lambda* con `ResourceNotFoundException` | La Lambda no existe: revisa que **1 · Infra** haya terminado en verde. |
| **3 · Finalizar** ❌ en *¿La tienda abre?* | CloudFront recién creado puede tardar unos minutos más: en Actions → **Re-run failed jobs**. |
| `AccessDenied` en el `terraform apply` del pipeline | El rol `tienda-cicd-apply` solo maneja recursos que empiezan por `tienda-cicd-`. Si cambiaste un nombre en `main.tf`, déjalo como estaba. |
| La página dice *AccessDenied* en vez de "La infraestructura ya está lista" | El paso *Poner el aviso 🚧* no corrió: revisa que **1 · Infra** haya terminado en verde y recarga. |
| `terraform fmt -check` ❌ en el plan | Quedó mal alineado un `=`. En tu PC: `cd terraform`, `terraform fmt`, commit y push a la misma rama. |
| `Error acquiring the state lock` | Alguien (o el pipeline) está aplicando. Espera a que termine. Si un pipeline se canceló a la mitad y el candado quedó: `terraform force-unlock <ID>` con el ID del mensaje. |
| `git` no se reconoce | Instala Git para Windows y reabre VS Code. |
| `refusing to allow ... workflow ... without workflow scope` | Entraste con un token sin permiso `workflow`. Windows → **Administrador de credenciales** → Credenciales de Windows → borra `git:https://github.com` y vuelve a hacer `git push` (entra por el navegador). |
| `src refspec main does not match any` | Te faltó el `git commit` antes del push. |
