// ===================== FRONT: lo que reacciona (JavaScript) =====================
// Este archivo corre en el navegador de Camila. Cualquiera lo puede ver con F12:
// por eso aquí NO van claves, ni precios "de verdad", ni reglas del negocio.
var API = window.API_URL; // la dirección de tu API Gateway (la escribe Terraform en config.js)

var CATALOGO = [
  { id: "camiseta", nombre: "Camiseta Laura", texto: "Algodón peinado, corte relajado.", precio: 59000, color: "#59c3ff", fondo: "#e3f4ff" },
  { id: "gorra", nombre: "Gorra Laura", texto: "Visera curva, ajuste trasero.", precio: 39000, color: "#16182b", fondo: "#efeefe" },
  { id: "buzo", nombre: "Buzo Laura", texto: "Felpa gruesa con capota.", precio: 119000, color: "#ff7aa8", fondo: "#ffe8f0" }
];

var $ = function (id) { return document.getElementById(id); };
var pesos = function (n) { return "$" + Number(n || 0).toLocaleString("es-CO"); };
var esc = function (t) { return String(t == null ? "" : t).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
var ultimos = {};

// ---------- la colección ----------
$("productos").innerHTML = CATALOGO.map(function (p) {
  return '<button type="button" class="producto" data-id="' + p.id + '">' +
    '<div class="producto-foto" style="background:' + p.fondo + '"><svg viewBox="0 0 220 220" style="color:' + p.color + '"><use href="#ico-' + p.id + '"/></svg></div>' +
    "<h3>" + p.nombre + "</h3><p>" + p.texto + "</p>" +
    '<div class="precio">' + pesos(p.precio) + "<span>S · M · L · XL</span></div></button>";
}).join("");

function elegir(id) {
  $("producto").value = id;
  document.querySelectorAll(".producto").forEach(function (b) { b.classList.toggle("elegido", b.dataset.id === id); });
}
document.querySelectorAll(".producto").forEach(function (b) {
  b.addEventListener("click", function () { elegir(b.dataset.id); $("pedido").scrollIntoView(); $("cliente").focus(); });
});
$("producto").addEventListener("change", function () { elegir($("producto").value); });
elegir("camiseta");

// ---------- el viaje del pedido (animación de los 5 pasos) ----------
var pasos = document.querySelectorAll("#pasos li");
function marcar(n) {
  pasos.forEach(function (li, i) { li.classList.toggle("activo", i === n); li.classList.toggle("hecho", i < n); });
}
function terminar() { pasos.forEach(function (li) { li.classList.remove("activo"); li.classList.add("hecho"); }); }
function medir(r, total) {
  $("m-frio").textContent = r.frio ? "🥶 en frío" : "🔥 caliente";
  $("m-inst").textContent = r.instancia;
  $("m-ms").textContent = r.ms + " ms";
  $("m-total").textContent = total + " ms";
}

// ---------- hablar con el BACK ----------
function leerPedido() {
  return {
    cliente: $("cliente").value,
    producto: $("producto").value,
    talla: document.querySelector("input[name=talla]:checked").value,
    cantidad: Number($("cantidad").value || 1)
  };
}
function guardar(pedido) {
  return fetch(API + "/", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(pedido) })
    .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || j.message || ("error " + r.status)); return j; }); });
}
function leer(cliente) {
  var url = API + (cliente ? "/?cliente=" + encodeURIComponent(cliente) : "/");
  return fetch(url).then(function (r) { return r.json(); });
}

function pintar(r, nuevos) {
  var nombre = { camiseta: "Camiseta", gorra: "Gorra", buzo: "Buzo" };
  $("estado-lista").textContent = r.operacion + " · " + r.pedidos.length + " pedido(s) · " + (r.frio ? "🥶 en frío" : "🔥 caliente") + " · " + r.ms + " ms";
  $("lista").innerHTML = r.pedidos.map(function (p) {
    var hora = new Date(String(p.fecha).split("#")[0]).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    var nuevo = nuevos && nuevos[p.fecha] ? ' class="nuevo"' : "";
    return "<tr" + nuevo + "><td><b>" + esc(p.cliente) + "</b></td><td>" + esc(nombre[p.producto] || p.producto) + "</td><td>" + esc(p.talla) + "</td><td>" + esc(p.cantidad || 1) + "</td><td>" + pesos(p.total) + "</td><td>" + hora + '</td><td><span class="chip">' + esc(p.instancia) + "</span></td></tr>";
  }).join("") || '<tr><td colspan="7">Todavía no hay pedidos. ¡Haz el primero!</td></tr>';
}
function refrescar(cliente, nuevos) {
  return leer(cliente).then(function (r) { pintar(r, nuevos); }).catch(function () { $("estado-lista").textContent = "No pude leer los pedidos: revisa que terraform apply haya terminado."; });
}

// ---------- comprar ----------
$("formulario").addEventListener("submit", function (e) {
  e.preventDefault();
  var msg = $("mensaje"), boton = $("comprar"), t0 = performance.now();
  msg.className = "mensaje"; msg.textContent = "Enviando tu pedido…"; boton.disabled = true;
  marcar(0);
  setTimeout(function () { marcar(1); }, 250);
  var envio = guardar(leerPedido());
  setTimeout(function () { marcar(2); }, 550);
  envio.then(function (r) {
    marcar(3);
    var total = Math.round(performance.now() - t0);
    setTimeout(function () {
      marcar(4);
      setTimeout(terminar, 350);
      medir(r, total);
      msg.className = "mensaje ok";
      msg.textContent = "✅ ¡Listo, " + r.pedido.cliente + "! " + r.pedido.cantidad + " × " + r.pedido.producto + " talla " + r.pedido.talla + " · total " + pesos(r.pedido.total);
      if (r.traza) msg.insertAdjacentHTML("beforeend", ' · <a href="' + consolaTraza(r.traza) + '" target="_blank" rel="noopener">🔎 ver su traza</a>');
      ultimos = {}; ultimos[r.pedido.fecha] = 1;
      refrescar("", ultimos);
    }, 300);
  }).catch(function (err) {
    pasos.forEach(function (li) { li.classList.remove("activo", "hecho"); });
    msg.className = "mensaje error"; msg.textContent = "❌ " + err.message;
  }).finally(function () { boton.disabled = false; });
});

// ---------- botones de la lista ----------
$("ver-todos").onclick = function () { refrescar(""); };
$("ver-mios").onclick = function () {
  var c = $("cliente").value.trim();
  if (!c) { $("estado-lista").textContent = "Escribe tu nombre arriba para buscar solo tus pedidos."; return; }
  refrescar(c);
};

// ---------- la ráfaga: 20 pedidos al mismo tiempo ----------
$("rafaga").onclick = function () {
  var base = leerPedido(), boton = $("rafaga"), out = $("rafaga-resultado");
  if (!base.cliente) base.cliente = "rafaga";
  boton.disabled = true; out.textContent = "⚡ enviando 20 pedidos al mismo tiempo…";
  var envios = [];
  for (var i = 0; i < 20; i++) envios.push(guardar(base).catch(function () { return null; }));
  Promise.all(envios).then(function (rs) {
    var inst = {}, frios = 0, frenados = 0, nuevos = {};
    rs.forEach(function (r) {
      if (!r || !r.instancia) { frenados++; return; }
      inst[r.instancia] = (inst[r.instancia] || 0) + 1;
      if (r.frio) frios++;
      nuevos[r.pedido.fecha] = 1;
    });
    var n = Object.keys(inst).length;
    out.textContent = "⚡ " + (20 - frenados) + " de 20 pedidos guardados · AWS prendió " + n + " instancia(s) de la Lambda (" + frios + " en frío)\n" +
      Object.keys(inst).map(function (k) { return "   instancia " + k + " → " + inst[k] + " pedido(s)"; }).join("\n") +
      (frenados ? "\n🚦 " + frenados + " frenado(s) por el límite de concurrencia de tu cuenta (las cuentas nuevas pueden empezar con 10)" : "");
    return refrescar("", nuevos);
  }).finally(function () { boton.disabled = false; });
};

// ---------- ¿qué versión estás viendo? (version.js lo escribe GitHub Actions) ----------
var V = window.VERSION;
if (V) {
  $("publicado").innerHTML = "🚀 Publicada por GitHub Actions · commit <b>" + esc(V.commit) + "</b> de " + esc(V.autor) + " · " + new Date(V.fecha).toLocaleString("es-CO");
} else {
  $("publicado").className = "franja manual";
  $("publicado").textContent = "🧱 Publicada a mano con terraform apply · todavía sin pipeline (haz tu primer push)";
}

// ===================== PARTE 3: las pruebas de observabilidad =====================
// Cada prueba hace un pedido con un nombre de prueba único. El back lo anota en la traza
// (anotación "prueba") y después la página le pregunta: GET /?observar=<prueba>
// → las trazas de esa prueba en X-Ray (tramo por tramo) y el estado de las alarmas.
function consolaTraza(id) { return "https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#xray:traces/" + id; }
function tiene(t, nombre) { return t.tramos.some(function (x) { return x.nombre === nombre; }); }
function tramoDe(t, nombre) { return t.tramos.filter(function (x) { return x.nombre === nombre; })[0] || { ms: 0 }; }
var dormir = function (ms) { return new Promise(function (ok) { setTimeout(ok, ms); }); };

var PRUEBAS = [
  {
    id: "normal", titulo: "✅ Pedido normal", texto: "Una gorra. Debe guardarse en DynamoDB y cobrarse sin fallas.",
    pedido: { cliente: "prueba", producto: "gorra", talla: "M" },
    revisar: function (http, t) {
      return [["el API respondió 200", http === 200], ["la traza llegó a X-Ray", !!t],
        ["pasó por DynamoDB (PutItem)", !!t && tiene(t, "DynamoDB")], ["pasó por cobrar", !!t && tiene(t, "cobrar")],
        ["sin fallas en la traza", !!t && !t.falla]];
    }
  },
  {
    id: "malo", titulo: "🚫 Pedido malo", texto: "Talla XXL, que no existe. El back lo rechaza antes de tocar la tabla.",
    pedido: { cliente: "prueba", producto: "buzo", talla: "XXL" },
    revisar: function (http, t) {
      return [["el API respondió 400", http === 400], ["la traza llegó a X-Ray", !!t],
        ["pasó por validar", !!t && tiene(t, "validar")], ["NO tocó DynamoDB", !!t && !tiene(t, "DynamoDB")]];
    }
  },
  {
    id: "lento", titulo: "🐢 Pedido lento", texto: "El cliente «lento»: la pasarela de pagos tarda 3 segundos. ¿Dónde se fue el tiempo?",
    pedido: { cliente: "lento", producto: "camiseta", talla: "S" },
    revisar: function (http, t) {
      return [["el API respondió 200 (lento, pero funciona)", http === 200], ["la traza llegó a X-Ray", !!t],
        ["la traza dura más de 2 s", !!t && t.ms > 2000], ["el culpable es cobrar (más de 2,5 s)", !!t && tramoDe(t, "cobrar").ms > 2500]];
    }
  },
  {
    id: "falla", titulo: "💥 Pedido con falla", texto: "El cliente «caos»: la pasarela de pagos se cae. La Lambda falla de verdad.",
    pedido: { cliente: "caos", producto: "buzo", talla: "L" },
    revisar: function (http, t) {
      return [["el API respondió 500", http === 500 || http === 0], ["la traza llegó a X-Ray", !!t],
        ["la traza está marcada con falla", !!t && (t.falla || t.error)], ["la falla está en cobrar", !!t && tramoDe(t, "cobrar").falla],
        ["…pero el pedido SÍ se guardó (DynamoDB)", !!t && tiene(t, "DynamoDB")]];
    }
  }
];

$("pruebas").innerHTML = PRUEBAS.map(function (p) {
  return '<article class="prueba" id="prueba-' + p.id + '"><h3>' + p.titulo + "</h3><p>" + p.texto + "</p>" +
    '<button class="boton boton-claro" type="button" data-prueba="' + p.id + '">Correr</button>' +
    '<p class="estado" role="status"></p><ul class="revision"></ul></article>';
}).join("");

// X-Ray guarda 1 petición por segundo (y el 5 % del resto): las peticiones de las pruebas van de a una
var ultima = 0, fila = Promise.resolve();
function turno() {
  fila = fila.then(function () {
    return dormir(Math.max(0, ultima + 1200 - Date.now())).then(function () { ultima = Date.now(); });
  });
  return fila;
}
function enviarPrueba(p, nombre) {
  var cuerpo = Object.assign({ cantidad: 1, prueba: nombre }, p.pedido);
  return turno().then(function () {
    return fetch(API + "/", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(cuerpo) });
  }).then(function (r) {
    return r.json().catch(function () { return {}; }).then(function (j) { return { http: r.status, cuerpo: j }; });
  }, function () { return { http: 0, cuerpo: {} }; }); // la falla puede llegar sin respuesta legible
}
function observar(nombre) {
  return turno().then(function () { return fetch(API + "/?observar=" + encodeURIComponent(nombre)); })
    .then(function (r) { return r.json(); });
}
function pintarAlarmas(lista) {
  if (!lista || !lista.length) { $("alarmas").textContent = "Tu cuenta todavía no tiene alarmas tienda-cicd-…"; return; }
  var icono = { OK: "✅", ALARM: "🚨", INSUFFICIENT_DATA: "⏳" };
  $("alarmas").innerHTML = "Alarmas: " + lista.map(function (a) {
    return '<span class="alarma ' + esc(a.estado) + '">' + (icono[a.estado] || "") + " " + esc(a.nombre) + " · " + esc(a.estado) + "</span>";
  }).join("");
}

function pintarTraza(p, t) {
  $("traza").hidden = false;
  document.querySelectorAll(".prueba").forEach(function (c) { c.classList.toggle("elegida", c.id === "prueba-" + p.id); });
  $("traza-nombre").textContent = "La traza de: " + p.titulo;
  $("traza-id").textContent = t.id + " · " + t.ms + " ms en total" + (t.falla ? " · 💥 con falla" : "");
  $("traza-consola").href = consolaTraza(t.id);
  $("traza-consulta").textContent = 'filter traza = "' + t.id + '"';
  var total = Math.max(1, t.ms, Math.max.apply(null, t.tramos.map(function (x) { return x.desde_ms + x.ms; })));
  var nombre = function (x) {
    if (x.origen === "AWS::Lambda") return "Lambda (el servicio)";
    if (x.origen === "AWS::Lambda::Function") return "tu función";
    if (x.origen && x.origen.indexOf("DynamoDB") >= 0) return "DynamoDB (la tabla)";
    return x.nombre + (x.operacion ? " · " + x.operacion : "");
  };
  $("cascada").innerHTML = t.tramos.map(function (x) {
    var clase = "tramo" + (x.origen && x.nombre !== "DynamoDB" ? " servicio" : "") + (x.nombre === "DynamoDB" ? " dynamo" : "") + (x.nombre === "cobrar" ? " cobrar" : "") + (x.falla ? " falla" : "");
    return '<div class="' + clase + '"><span class="tramo-nombre" style="padding-left:' + (x.nivel * 14) + 'px">' + esc(nombre(x)) + (x.falla ? " 💥" : "") + "</span>" +
      '<span class="tramo-carril"><span class="tramo-barra" style="left:' + (x.desde_ms / total * 100).toFixed(2) + "%;width:" + (x.ms / total * 100).toFixed(2) + '%"></span></span>' +
      '<span class="tramo-ms">' + x.ms + " ms</span></div>";
  }).join("");
}

// una traza está completa cuando ya llegaron tu función y el tramo "pedido"
function completa(t) { return t && tiene(t, "pedido") && t.tramos.some(function (x) { return x.origen === "AWS::Lambda::Function"; }); }

function correr(p) {
  var tarjeta = $("prueba-" + p.id), estado = tarjeta.querySelector(".estado"), lista = tarjeta.querySelector(".revision");
  var boton = tarjeta.querySelector("button");
  var nombre = p.id + "-" + Date.now().toString(36);
  tarjeta.className = "prueba"; lista.innerHTML = ""; boton.disabled = true;
  estado.textContent = "Enviando el pedido…";
  var envio, intentos = 0;
  function pedir() {
    return enviarPrueba(p, nombre).then(function (r) {
      envio = r; intentos++;
      // si X-Ray no guardó esta petición (muestreo), se repite con otro nombre
      if (r.cuerpo.muestreada === false && intentos < 4) { nombre = p.id + "-" + Date.now().toString(36); return pedir(); }
      return r;
    });
  }
  function esperar(vuelta) {
    estado.textContent = "⏳ Esperando la traza en X-Ray… (" + (vuelta * 4) + " s)";
    return dormir(4000).then(function () { return observar(nombre); }).then(function (o) {
      pintarAlarmas(o.alarmas);
      var t = o.trazas[0];
      if (completa(t)) return t;
      if (vuelta === 15 && !t) return pedir().then(function () { return esperar(vuelta + 1); }); // ¿se perdió? un pedido más
      if (vuelta >= 30) return t || null;
      return esperar(vuelta + 1);
    });
  }
  return pedir().then(function () { return esperar(1); }).then(function (t) {
    var checks = p.revisar(envio.http, t), bien = checks.every(function (c) { return c[1]; });
    lista.innerHTML = checks.map(function (c) { return '<li class="' + (c[1] ? "si" : "no") + '">' + esc(c[0]) + "</li>"; }).join("");
    tarjeta.classList.add(bien ? "paso" : "fallo");
    estado.textContent = bien ? "✅ La traza cuenta lo que pasó" : "❌ Algo no cuadra: mira qué falló";
    if (t) {
      pintarTraza(p, t);
      var ver = document.createElement("button");
      ver.className = "boton boton-claro"; ver.type = "button"; ver.textContent = "Ver la traza";
      ver.onclick = function () { pintarTraza(p, t); $("traza").scrollIntoView({ block: "nearest" }); };
      lista.after(ver);
    }
  }).catch(function (err) {
    tarjeta.classList.add("fallo");
    estado.textContent = "❌ El API de la tienda no responde (" + err.message + "). ¿La tienda sigue desplegada? Abre la página desde tu_tienda y vuelve a intentar.";
  }).finally(function () { boton.disabled = false; });
}

document.querySelectorAll("[data-prueba]").forEach(function (b) {
  b.onclick = function () {
    var viejo = b.parentNode.querySelector(".revision + .boton"); if (viejo) viejo.remove();
    correr(PRUEBAS.filter(function (p) { return p.id === b.dataset.prueba; })[0]);
  };
});
$("correr-todas").onclick = function () {
  var boton = $("correr-todas"); boton.disabled = true;
  document.querySelectorAll(".revision + .boton").forEach(function (v) { v.remove(); });
  // las 4 a la vez, pero cada petición espera su turno (1,2 s): cada prueba tiene su nombre y su traza
  Promise.all(PRUEBAS.map(correr)).finally(function () { boton.disabled = false; });
};
$("ver-alarmas").onclick = function () {
  observar("alarmas").then(function (o) { pintarAlarmas(o.alarmas); })
    .catch(function () { $("alarmas").textContent = "El API de la tienda no responde: ¿sigue desplegada?"; });
};

// al abrir la página: muestra los pedidos que ya existen
if (!API) { $("estado-lista").textContent = "Falta config.js: esta página debe abrirse desde tu_tienda (CloudFront)."; }
else refrescar("");
