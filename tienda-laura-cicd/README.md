# La tienda de Laura con CI/CD · parte 3: los ojos (CloudWatch + X-Ray)

Laboratorio de la clase 15 · Esumer · Cloud Computing, Redes y Ciberseguridad.

Es **la misma tienda y el mismo repositorio** de las clases 13 y 14: el pipeline ya la publica sola.
Hoy no se crea nada a mano. Le agregamos **ojos** y llegan **por pull request**, como cualquier cambio:

| | Parte 1 · clase 13 | Parte 2 · clase 14 | **Parte 3 · clase 15 (hoy)** |
|---|---|---|---|
| Qué se publica solo | la infraestructura | + la aplicación (back y front) | **+ los ojos**: logs en JSON, métricas, **trazas**, alarmas y tablero |
| Las pruebas | — | las del back (precios, tallas) | **+ en vivo**: el pipeline espera la traza de un pedido, y la página corre **4 pruebas de observabilidad** |

```
tienda-laura-cicd/
├── back/
│   ├── app.py              ← CAMBIA: log en JSON + métricas EMF + tramos de X-Ray + GET /?observar=
│   ├── test_app.py         ← CAMBIA: 7 pruebas nuevas (el log, las métricas, la falla, la lentitud, la cascada…)
│   └── requirements.txt    ← NUEVO: el SDK de X-Ray (el pipeline lo empaqueta junto a app.py)
├── front/                  ← CAMBIA: la sección 🔭 Pruebas de observabilidad
├── terraform/
│   ├── main.tf             ← CAMBIA una cosa: la Lambda deja trazas (tracing_config)
│   └── observabilidad.tf   ← NUEVO: SNS (correo) + 2 alarmas + 3 consultas guardadas + el tablero
└── bootstrap/
    ├── main.tf             ← CAMBIA: el rol del pipeline puede manejar CloudWatch y SNS
    └── pipeline.yml.tpl    ← CAMBIA: el pipeline completo, con la prueba de la traza
```

## Las tres patas de la observabilidad, en esta tienda

| | Responde | Dónde se ve |
|---|---|---|
| **Logs** | ¿qué pasó? (cada pedido, cada rechazo, cada error) | CloudWatch Logs y **Logs Insights** |
| **Métricas** | ¿cuánto? (pedidos, ventas, errores, cuánto tardan: p50 y p90) | el **tablero** y las **alarmas** |
| **Trazas** | ¿**dónde**? (el recorrido de UN pedido, tramo por tramo) | **X-Ray** y la sección 🔭 de la página |

Cada pedido deja su traza con estos tramos: `pedido` → `validar` → `DynamoDB · PutItem` → `cobrar`.
`cobrar` es una pasarela de pagos de mentiras con dos clientes especiales para practicar:
**`lento`** (tarda 3 segundos) y **`caos`** (se cae y la Lambda falla de verdad).

# PARTE 3 · Clase 15: la tienda con ojos

## PASO 12 · Trae lo nuevo

> ¿Tu proyecto ya tiene tus propias rutas, nombres o el lab en una subcarpeta? No copies la carpeta entera:
> sigue **`CAMBIOS-PARTE3.md`**: qué carpetas reemplazar, qué archivos del bootstrap cambian y qué no tocar. Después sigue aquí, desde el punto 2.

1. Baja el zip de hoy (`tienda-laura-cicd-parte3.zip`), ábrelo y entra a su carpeta `tienda-laura-cicd`.
   Selecciona todo (**Ctrl + A**) y **cópialo encima de tu carpeta del lab** (la de las clases 13 y 14, la que tiene `bootstrap/terraform.tfstate`):
   Windows pregunta → **Reemplazar los archivos en el destino**.
   (Si en el PASO 8 cambiaste el título, se vuelve a poner el original: no pasa nada.)
2. En la terminal de VS Code, en la carpeta principal, trae lo último y abre una **rama**:

```powershell
git checkout main
git pull
git checkout -b los-ojos
```

## PASO 13 · Más permisos para el pipeline (bootstrap, desde tu PC)

El rol `tienda-cicd-apply` solo sabe manejar la tienda. Para crear alarmas, el tablero y el correo necesita más permisos,
y **el pipeline no puede dárselos a sí mismo**: se los da una persona, desde su PC, con el bootstrap.

```powershell
cd bootstrap
terraform apply     # tu usuario/tienda-laura, igual que en la clase 13 · yes
cd ..
```

> Si el lab está en una subcarpeta de otro repo, igual que en la clase 13:
> `$c = git rev-parse --show-prefix` y `terraform apply -var="repo_github=TU-USUARIO/TU-REPO" -var="carpeta=$c"` (desde la carpeta del lab, antes del `cd bootstrap`).

Mira el plan antes del **yes**: cambia **la política del rol `tienda-cicd-apply`** y se reescribe **`.github/workflows/pipeline.yml`**
con el pipeline completo (también borra `parte2/`, que ya no hace falta). Nada de la tienda se toca desde aquí.

## PASO 14 · Tu correo, como secreto del repositorio

Las alarmas te escriben al correo, pero tu correo **no va en el código**. En GitHub → tu repositorio →
**Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

- Name: `CORREO`
- Secret: tu correo
- **Add secret**

El pipeline lo lee como `TF_VAR_correo` y GitHub lo tapa con `***` en los logs (aunque tu repo sea público).

## PASO 15 · El pull request

```powershell
git add .
git commit -m "la tienda con ojos"
git push -u origin los-ojos
```

(Si el lab está en una subcarpeta: `git add . ":/.github"`.)

En GitHub → **Compare & pull request** → **Create pull request**. Corre **Revisar (pruebas + terraform plan)** ✅:

- **Probar el back**: ahora son **12 pruebas** (las 5 de siempre + 7 de los ojos).
- **terraform plan**: `Plan: 9 to add, 1 to change, 0 to destroy`. Los 9 son los ojos; el 1 es la Lambda, que ahora deja trazas
  (`+ tracing_config { mode = "Active" }`).

**Merge pull request** → **Confirm merge**. En **Actions** corre el pipeline completo:

```
1 · Infra ──┬──▶ 2 · Back  (12 pruebas → zip con el SDK de X-Ray → Lambda) ──┬──▶ 3 · Finalizar
            └──▶ 2 · Front (probar → versión → S3)                          ──┘     ¿abre? ¿responde? ¿deja traza?
```

1. **1 · Infra**: *Los logs de la Lambda* (que existan y duren 7 días) y `terraform apply` → **9 added, 1 changed**.
2. **3 · Finalizar** → **¿Deja traza?**: el pipeline hace un pedido de prueba y espera **su traza** en X-Ray (de 10 a 60 segundos).
   En el log del paso salen los tramos: `DynamoDB`, `cobrar`… En el resumen: **🔎 La traza del pedido de prueba llegó a X-Ray** y el link del **📊 Tablero**.

📬 **Abre tu correo**: llega *AWS Notification - Subscription Confirmation* → **Confirm subscription**.
Sin eso, las alarmas suenan pero no te llega nada.

```powershell
git checkout main
git pull
```

## PASO 16 · Las pruebas de observabilidad, desde la página

Abre tu tienda → **Observar** (arriba a la derecha) → **▶ Correr las 4 pruebas**. Cada una hace un pedido especial,
**espera su traza** en X-Ray y revisa que la traza cuente lo que pasó:

| Prueba | El pedido | La traza tiene que decir |
|---|---|---|
| ✅ Pedido normal | una gorra | 200 · pasó por `DynamoDB` y por `cobrar` · sin fallas |
| 🚫 Pedido malo | talla XXL | 400 · pasó por `validar` · **no** tocó DynamoDB |
| 🐢 Pedido lento | cliente `lento` | 200 · dura más de 2 s · **el culpable es `cobrar`** |
| 💥 Pedido con falla | cliente `caos` | 500 · marcada con **falla** · la falla está en `cobrar` · …pero el pedido **sí** se guardó |

Tardan de 20 a 60 segundos: X-Ray recibe las trazas por partes. Al terminar, **Ver la traza** dibuja la cascada:
cada barra es un tramo y su largo es lo que tardó. En la lenta se ve de un golpe **dónde** se fueron los 3 segundos.

Fíjate en la última: el pedido **se guardó pero no se cobró**. Un log diría "error"; la métrica diría "1 error";
**la traza dice en qué paso**, y que ya habían pasado cosas antes.

**Abrir en la consola de AWS ↗** abre la misma traza en CloudWatch → **Trace Map** y la línea de tiempo.
Ahí, en *Traces*, puedes buscar por anotación: `annotation.cliente = "caos"`.

## PASO 17 · Las alarmas suenan

Las pruebas lento y con falla hacen sonar las dos alarmas. En 1 a 3 minutos:

- Arriba de las pruebas: **🚨 tienda-cicd-se-cayo · ALARM** y **🚨 tienda-cicd-lenta · ALARM** (botón **¿Cómo están las alarmas?**).
- 📬 Te llegan los correos *ALARM: "tienda-cicd-se-cayo"* y *ALARM: "tienda-cicd-lenta"*.
- Sin más fallas, a los minutos vuelven a **OK** y te llega otro correo.

`tienda-cicd-lenta` mira el **p90 de la Demora de los pedidos** (una métrica propia), no el promedio de la Lambda:
las consultas rápidas de la página no alcanzan a esconder al cliente que esperó 3 segundos.

## PASO 18 · Los logs

En la terminal: `aws logs tail /aws/lambda/tienda-cicd --follow --format short` y corre una prueba. Por cada pedido ves
`START`, tu log en JSON (con el campo `traza`), la línea `_aws` de las métricas y `REPORT`. `Ctrl + C` para salir.

Consola → CloudWatch → **Logs Insights** → *Consultas guardadas* → `tienda-cicd/ventas-por-producto`, `tienda-cicd/ultimos-pedidos` y `tienda-cicd/errores`.
Y debajo de la cascada, la página te da la consulta exacta para encontrar en los logs **el mismo pedido** de la traza: `filter traza = "1-…"`.

## PASO 19 · El tablero

El link está en el resumen del pipeline (o CloudWatch → **Paneles** → `tienda-cicd-laura`). Pulsa **⚡ Ráfaga** en la tienda un par de veces y espera 1 o 2 minutos:
💰 Ventas y 🧾 Pedidos (tus métricas), ⚡ la Lambda, 🐢 cuánto tardan los pedidos (p50, p90 y el peor), 🚪 el API y 📜 los últimos pedidos.

## PASO 20 · La alarma de la plata (AWS Budgets)

Con tu usuario de la consola: **Billing and Cost Management → Presupuestos → Crear un presupuesto** →
*Usar una plantilla* → **Presupuesto mensual de costos** → `5` USD → tu correo → **Crear presupuesto**.
Este se puede quedar: los dos primeros presupuestos son gratis.

## ¿Ya habías destruido la tienda en la clase 14?

No pasa nada: el pipeline la vuelve a crear entera. Haz el PASO 12 (sin la rama) y luego:

```powershell
cd bootstrap
terraform init
terraform apply      # 12 recursos nuevos (11 si ya tenías el proveedor de GitHub)
cd ..
```

Crea el secreto `CORREO` (PASO 14) y sube todo: `git add .`, `git commit`, `git push` (si protegiste main en el PASO 10, por pull request).
**1 · Infra** crea los 22 recursos (≈ 4 min por CloudFront) y sigue con el back, el front y la prueba de la traza.

## Al terminar: destruir EN ORDEN (¡importante!)

Tu usuario `terraform-lab` ahora también va a borrar alarmas, el tablero y el SNS: IAM → Usuarios → `terraform-lab` →
Agregar permisos → Adjuntar políticas directamente → `CloudWatchFullAccessV2` y `AmazonSNSFullAccess`.

```powershell
cd terraform
terraform init -backend-config="backend.hcl"
terraform destroy          # yes · Destroy complete! Resources: 22 destroyed.

cd ../bootstrap
terraform destroy          # yes · Destroy complete! (11 a 13 recursos, según tu cuenta)

# los logs de la Lambda los crea AWS (no Terraform): bórralos aparte
aws logs delete-log-group --log-group-name /aws/lambda/tienda-cicd
```

Las trazas y las métricas no se borran: X-Ray guarda las trazas 30 días y CloudWatch deja vencer las métricas solas.
Ninguna de las dos cobra si nadie manda datos nuevos.

## Lo que cuesta

Casi nada, y para el lab entra en la capa gratuita: 10 alarmas, 3 tableros, 5 GB de logs, 1 millón de peticiones a SNS
y **100.000 trazas** al mes. Lo único fuera de ella son las 7 métricas propias (Pedidos y Ventas por 3 productos, y Demora):
unos USD 0,30 al mes cada una, cobrados por hora. Unas horas de lab cuestan menos de un centavo.

## Lab vs. empresa

| | Este lab | Una empresa |
|---|---|---|
| La observabilidad | en Terraform, por pull request ✅ | igual: alarmas y tableros son código, con revisión |
| Las trazas | X-Ray con su SDK | X-Ray en todos los servicios, con las trazas buscadas por anotación desde CloudWatch |
| Las alarmas | al correo | a Slack, Teams o PagerDuty, con un turno de guardia |
| La prueba de humo | el pipeline espera una traza | igual, y además pruebas sintéticas cada minuto (CloudWatch Synthetics) |

## Si algo falla

| Mensaje | Qué hacer |
|---|---|
| `AccessDenied` en el `terraform apply` del pipeline (`cloudwatch:PutMetricAlarm`, `sns:CreateTopic`, `logs:CreateLogGroup`…) | Falta el PASO 13: el rol del pipeline no tiene los permisos nuevos. Corre el bootstrap y vuelve a correr el pipeline (**Re-run failed jobs**). |
| **3 · Finalizar** ❌ en *¿Deja traza?* | ¿El back se publicó con el SDK? En **2 · Back** → *Empaquetar el back* debe salir un `back.zip` de ≈ 350 KB. Si sí, **Re-run failed jobs**: a veces X-Ray tarda más. |
| Las pruebas de la página se quedan en *Esperando la traza…* | Igual que arriba. Revisa también Lambda → `tienda-cicd` → Configuración → Herramientas de supervisión → **Rastreo activo** (debe estar activado). |
| La página no muestra la sección 🔭 | El front viejo sigue publicado: revisa que **2 · Front** haya corrido después del merge y recarga con `Ctrl + F5`. |
| No llegan los correos | Confirma la suscripción (PASO 15) y revisa el spam. ¿Creaste el secreto `CORREO` **antes** del merge? Si no, créalo y en Actions → **Run workflow**. |
| `No value for required variable` | Tu `terraform/observabilidad.tf` es viejo: repite el PASO 12. |
| La alarma `tienda-cicd-lenta` no suena | Mira la métrica, no el promedio: corre otra vez la prueba 🐢 y espera 2 o 3 minutos. |
| `Not authorized to perform sts:AssumeRoleWithWebIdentity` (en Actions) | El repositorio quedó mal escrito o con otras mayúsculas. En `bootstrap`: `terraform apply -var="repo_github=TU-USUARIO/tienda-laura"`, `git add .`, commit, push (el `pipeline.yml` no cambia, pero los roles sí). Revisa también que la rama sea `main`. Si bajaste el zip antes del 22 de octubre, bájalo otra vez: GitHub cambió el formato del pase (`repo:usuario@123/repo@456:…`) y el bootstrap nuevo acepta los dos. |
| `EntityAlreadyExists ... oidc-provider` (en el bootstrap) | Tu cuenta ya tiene el proveedor de GitHub: `terraform apply -var="crear_proveedor=false"`. |
| `BucketAlreadyExists` o `BucketAlreadyOwnedByYou` (en el bootstrap) | Ya hiciste el bootstrap antes en esta cuenta y se perdió su estado. Borra el bucket `tienda-estado-…` en la consola (vacíalo primero) y repite. |
| `AccessDenied ... CreateOpenIDConnectProvider` o `CreateRole` | Falta la política del PASO 0. |
| `Unsupported argument ... use_lockfile` | Tu Terraform es anterior a la 1.10: actualízalo (`terraform version`). |
| `terraform fmt -check` ❌ en el plan | Quedó mal alineado un `=`. En tu PC: `cd terraform`, `terraform fmt`, commit y push a la misma rama. |
| `Too many command line arguments` en `terraform init` | En PowerShell, `-backend-config` va con comillas: `terraform init -backend-config="backend.hcl"` (sin ellas, PowerShell lo parte en el punto). |
| `Error acquiring the state lock` | Alguien (o el pipeline) está aplicando. Espera a que termine. Si un pipeline se canceló a la mitad y el candado quedó: `terraform force-unlock <ID>` con el ID del mensaje. |
| `git` no se reconoce | Instala Git para Windows y reabre VS Code. |
| `refusing to allow ... workflow ... without workflow scope` | Entraste con un token sin permiso `workflow`. Windows → **Administrador de credenciales** → Credenciales de Windows → borra `git:https://github.com` y vuelve a hacer `git push` (entra por el navegador). |
| `src refspec main does not match any` | Te faltó el `git commit` antes del push. |
