#!/usr/bin/env python3
"""
GKE Gateway API + Ingress Routes Mapper PRO v2.0
Extrae:
- Gateway API (HTTPRoutes)
- Ingress
- DNS
- Path (liveness/readiness)
- Servicio
- Puerto
- Namespace

Solo lectura
"""

import subprocess
import json
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

import openpyxl

console = Console()

PROYECTOS = {
    "1": {"id": "tu proyecto", "label": "Desarrollo (DEV)"},
    "2": {"id": "tu proyecto", "label": "QA"},
    "3": {"id": "tu proyecto", "label": "Producción (PROD)"},
    "4": {"id": "tu proyecto", "label": "diferente proyecto DEV"},
}

# ---------------------------
# UTIL
# ---------------------------
def run_cmd(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.strip(), r.returncode


def switch_project(project_id):
    _, rc = run_cmd(["gcloud", "config", "set", "project", project_id])
    return rc == 0


# ---------------------------
# CACHE K8S
# ---------------------------
def build_k8s_cache():
    cache = {"services": {}, "deployments": []}

    # services
    out, rc = run_cmd(["kubectl", "get", "svc", "--all-namespaces", "-o", "json"])
    if rc == 0 and out:
        data = json.loads(out)
        for s in data.get("items", []):
            ns = s["metadata"]["namespace"]
            name = s["metadata"]["name"]
            selector = s.get("spec", {}).get("selector", {})
            cache["services"][(ns, name)] = selector

    # deployments
    out, rc = run_cmd(["kubectl", "get", "deploy", "--all-namespaces", "-o", "json"])
    if rc == 0 and out:
        data = json.loads(out)
        cache["deployments"] = data.get("items", [])

    return cache


def get_probe_path(namespace, service, cache):
    selector = cache["services"].get((namespace, service))
    if not selector:
        return "no encontrado"

    for d in cache["deployments"]:
        if d["metadata"]["namespace"] != namespace:
            continue

        labels = d["spec"]["selector"].get("matchLabels", {})

        if all(labels.get(k) == v for k, v in selector.items()):
            containers = d["spec"]["template"]["spec"]["containers"]

            for c in containers:
                probe = c.get("livenessProbe") or c.get("readinessProbe")

                if probe:
                    path = probe.get("httpGet", {}).get("path")
                    if path:
                        return path

    return "no encontrado"


def get_service_port(namespace, service):
    out, rc = run_cmd([
        "kubectl", "get", "svc", service,
        "-n", namespace, "-o", "json"
    ])
    if rc != 0:
        return "NA"

    data = json.loads(out)
    ports = data.get("spec", {}).get("ports", [])

    if ports:
        return str(ports[0].get("port"))

    return "NA"


# ---------------------------
# GKE
# ---------------------------
def get_clusters():
    out, rc = run_cmd(["gcloud", "container", "clusters", "list", "--format=json"])
    return json.loads(out) if rc == 0 else []


def connect_cluster(name, loc):
    _, rc = run_cmd([
        "gcloud", "container", "clusters",
        "get-credentials", name,
        "--zone", loc, "--quiet"
    ])
    return rc == 0


# ---------------------------
# ROUTES - GATEWAY API
# ---------------------------
def get_gateway_routes(project, cluster, cache):
    out, rc = run_cmd(["kubectl", "get", "httproutes", "--all-namespaces", "-o", "json"])
    if rc != 0:
        return []

    data = json.loads(out)
    results = []

    for item in data.get("items", []):
        meta = item["metadata"]
        ns = meta.get("namespace", "default")

        spec = item.get("spec", {})
        dns = spec.get("hostnames", ["*"])[0]

        for rule in spec.get("rules", []):
            for backend in rule.get("backendRefs", []):
                svc = backend.get("name", "NA")

                path = get_probe_path(ns, svc, cache)
                port = get_service_port(ns, svc)

                # limpieza actuator
                if "/actuator/" in path:
                    path = path.split("/actuator/")[0]
                    if not path.endswith("/"):
                        path += "/"

                results.append({
                    "torre": "Compras.RMI",
                    "proyecto": project,
                    "cluster": cluster,
                    "namespace": ns,
                    "dns": dns,
                    "path": path,
                    "port": port,
                    "service": svc
                })

    return results


# ---------------------------
# ROUTES - INGRESS
# ---------------------------
def get_ingress_routes(project, cluster):
    out, rc = run_cmd(["kubectl", "get", "ingress", "--all-namespaces", "-o", "json"])
    if rc != 0:
        return []

    data = json.loads(out)
    results = []

    for item in data.get("items", []):
        ns = item["metadata"].get("namespace", "default")

        rules = item.get("spec", {}).get("rules", [])
        for r in rules:
            host = r.get("host", "*")

            paths = r.get("http", {}).get("paths", [])
            for p in paths:
                svc = p.get("backend", {}).get("service", {}).get("name", "NA")

                results.append({
                    "torre": "Compras.RMI",
                    "proyecto": project,
                    "cluster": cluster,
                    "namespace": ns,
                    "dns": host,
                    "path": p.get("path", "/"),
                    "port": "NA",
                    "service": svc
                })

    return results


# ---------------------------
# EXCEL
# ---------------------------
def export_excel(data):
    file = f"reporte_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    wb = openpyxl.Workbook()
    ws = wb.active

    headers = ["Torre","Proyecto","Cluster","Namespace","DNS","Path","Port","Service"]
    ws.append(headers)

    for r in data:
        ws.append([
            r["torre"], r["proyecto"], r["cluster"],
            r["namespace"], r["dns"], r["path"],
            r["port"], r["service"]
        ])

    wb.save(file)
    console.print(f"\n✅ Excel generado: {file}")


# ---------------------------
# MAIN
# ---------------------------
def main():
    console.print(Panel("GKE Routes Mapper PRO", border_style="cyan"))

    # seleccionar proyecto
    for k, v in PROYECTOS.items():
        console.print(f"[{k}] {v['label']}")

    sel = input("Selecciona: ")
    proyecto = PROYECTOS[sel]["id"]

    switch_project(proyecto)

    clusters = get_clusters()

    for i, c in enumerate(clusters, 1):
        console.print(f"[{i}] {c['name']}")

    sel_c = input("Cluster (0 = todos): ")

    if sel_c == "0":
        selected = clusters
    else:
        selected = [clusters[int(sel_c) - 1]]

    total = []

    for c in selected:
        name = c["name"]
        loc = c.get("location")

        console.print(f"\n🔌 {name}")

        if connect_cluster(name, loc):
            console.print("⚡ Cacheando cluster...")
            cache = build_k8s_cache()

            console.print("📡 Extrayendo Gateway API...")
            rutas = get_gateway_routes(proyecto, name, cache)

            console.print("🌐 Extrayendo Ingress...")
            rutas_ing = get_ingress_routes(proyecto, name)

            rutas.extend(rutas_ing)
            total.extend(rutas)

            console.print(f"✅ {len(rutas)} rutas")

    # tabla
    table = Table(box=box.SIMPLE)
    table.add_column("Namespace")
    table.add_column("DNS")
    table.add_column("Path")
    table.add_column("Port")
    table.add_column("Service")

    for r in total:
        table.add_row(
            r["namespace"],
            r["dns"],
            r["path"],
            r["port"],
            r["service"]
        )

    console.print(table)

    export_excel(total)


if __name__ == "__main__":
    main()