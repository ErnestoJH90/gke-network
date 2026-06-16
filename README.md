# gke-network

Este script es una herramienta de auditoría/inventario para GKE (Google Kubernetes Engine) que:
👉 Recorre clusters de Kubernetes en varios proyectos de GCP
👉 Extrae rutas HTTP definidas con Gateway API (HTTPRoutes)
👉 Relaciona cada ruta con su servicio y path real (livenessProbe)
👉 Muestra resultados en consola y los exporta a Excel

🧠 Explicación clara por partes
1. 🎯 Propósito principal
El script sirve para generar un mapa de rutas (routes mapping) en un entorno GKE, mostrando:

Proyecto
Cluster
DNS (host)
Path (endpoint real derivado del liveness probe)
Servicio de Kubernetes

👉 Es útil para:

Inventarios de APIs/microservicios
Auditorías de rutas
Documentación de arquitectura
Diagnóstico de gateways


2. 🧩 Flujo general (qué hace paso a paso)
🔹 Paso 1: Selección de entorno
Te muestra opciones:
[1] Desarrollo (DEV)
[2] QA
[3] Producción (PROD)
[4] N proyectos ----> depende de ti

Cambia el proyecto activo de GCP (gcloud config set project)


🔹 Paso 2: Selección de cluster

Lista los clusters del proyecto
Puedes elegir uno o todos (0)


🔹 Paso 3: Conectar a cada cluster
Ejecuta:
Shellgcloud container clusters get-credentials

👉 Esto configura kubectl para hablar con ese cluster.

🔹 Paso 4: Construye un cache local de Kubernetes
Obtiene:

Servicios (Services) → con sus selectors
Deployments → con sus labels y probes

Esto sirve para hacer correlaciones después.

🔹 Paso 5: Extrae rutas (HTTPRoutes)
Ejecuta:
Shellkubectl get httproutes --all-namespaces -o json

De cada ruta obtiene:

DNS (hostnames)
Backends (servicios asociados)


🔹 Paso 6: Encuentra el PATH real 🔥
Aquí está lo más interesante:
👉 Para cada servicio:

Busca su selector
Encuentra el deployment que coincide con esos labels
Extrae el:

YAMLlivenessProbe.httpGet.path

💡 Ese path suele ser algo como:
/actuator/health

Luego lo limpia para dejar algo como:
/
/api/


🔹 Paso 7: Construye resultados

Cada fila contiene:
{
  "torre": "Tu-Proyecto",
  "proyecto": "...",
  "cluster": "...",
  "dns": "...",
  "path": "...",
  "service": "..."
}

🔹 Paso 8: Muestra tabla en consola

Ejemplo:
Cluster        Path      Service
cluster-1      /api/     user-service
cluster-2      /         auth-service


🔹 Paso 9: Exporta a Excel 📊
Genera un archivo como:
reporte_fecha_124500.xlsx

Con columnas:

Torre
Proyecto
Cluster
DNS
Path
Service


⚙️ Tecnologías usadas

gcloud → gestión de GKE
kubectl → consulta de recursos de Kubernetes
rich → UI bonita en consola
openpyxl → generar Excel
subprocess → ejecutar comandos shell


🔥 Qué lo hace poderoso
✅ No modifica nada → solo lectura
✅ Funciona multi-cluster
✅ Relaciona:

Gateway API (HTTPRoutes)
Services
Deployments

✅ Deduce endpoints reales automáticamente

⚠️ Limitaciones

Solo funciona si:

Tienes acceso a los clusters
kubectl y gcloud configurados


Depende de que:

Services usen selector
Deployments tengan livenessProbe



Si no:
path = "no encontrado"
