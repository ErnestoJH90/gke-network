#!/usr/bin/env python3
"""
GKE Gateway API Routes Mapper v.1.0.0
Extrae Torre, Proyecto, DNS, Path y Servicio usando HTTPRoutes (Gateway API).
Solo lectura.
"""

import subprocess
import json
import sys
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

console = Console()

PROYECTOS = {
    "1": {"id": "proyecto gcp", "label": "Desarrollo (DEV)"},
    "2": {"id": "proyecto gcp", "label": "QA"},
    "3": {"id": "proyecto gcp", "label": "Producción (PROD)"},
    "4": {"id": "proyecto gcp", "label": "Desarrollo proyecto (DEV)"},
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
# CACHE GLOBAL K8S
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

def get_liveness_from_cache(namespace, service, cache):
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
                l = c.get("livenessProbe", {})
                path = l.get("httpGet", {}).get("path")
                if path:
                    return path

    return "no encontrado"

# ---------------------------
# GKE
# ---------------------------
def get_clusters():
    out, rc = run_cmd(["gcloud", "container", "clusters", "list", "--format=json"])
    return json.loads(out) if rc == 0 else []

def connect_cluster(name, loc):
    _, rc = run_cmd([
        "gcloud", "container", "clusters",
        "get-credentials", name, "--zone", loc, "--quiet"
    ])
    return rc == 0

# ---------------------------
# CORE
# ---------------------------
def get_routes(project, cluster, cache):
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
            backends = rule.get("backendRefs", [])

            for backend in backends:
                svc = backend.get("name", "NA")

                # 🔥 LIVENESS REAL
                liv = get_liveness_from_cache(ns, svc, cache)

                # limpieza
                if "/actuator/" in liv:
                    liv = liv.split("/actuator/")[0]
                    if not liv.endswith("/"):
                        liv += "/"

                results.append({
                    "torre": "Compras.RMI",
                    "proyecto": project,
                    "cluster": cluster,
                    "dns": dns,
                    "path": liv,
                    "service": svc
                })

    return results

# ---------------------------
# EXCEL
# ---------------------------
def export_excel(data, proyecto):
    file = f"reporte_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    wb = openpyxl.Workbook()
    ws = wb.active

    headers = ["Torre","Proyecto","Cluster","DNS","Path","Service"]
    ws.append(headers)

    for r in data:
        ws.append([
            r["torre"], r["proyecto"], r["cluster"],
            r["dns"], r["path"], r["service"]
        ])

    wb.save(file)
    console.print(f"\n✅ Excel generado: {file}")

# ---------------------------
# MAIN
# ---------------------------
def main():
    console.print(Panel("GKE Gateway Extractor PRO", border_style="cyan"))

    # entorno
    for k,v in PROYECTOS.items():
        console.print(f"[{k}] {v['label']}")

    sel = input("Selecciona: ")
    proyecto = PROYECTOS[sel]["id"]

    switch_project(proyecto)

    clusters = get_clusters()

    for i,c in enumerate(clusters,1):
        console.print(f"[{i}] {c['name']}")

    sel_c = input("Cluster (0 = todos): ")

    if sel_c == "0":
        selected = clusters
    else:
        selected = [clusters[int(sel_c)-1]]

    total = []

    for c in selected:
        name = c["name"]
        loc = c.get("location")

        console.print(f"\n🔌 {name}")

        if connect_cluster(name, loc):

            console.print("⚡ Cacheando cluster...")
            cache = build_k8s_cache()

            console.print("📡 Extrayendo rutas...")
            rutas = get_routes(proyecto, name, cache)
            total.extend(rutas)

            console.print(f"✅ {len(rutas)} rutas")

    # tabla
    table = Table(box=box.SIMPLE)
    table.add_column("Cluster")
    table.add_column("Path")
    table.add_column("Service")

    for r in total:
        table.add_row(r["cluster"], r["path"], r["service"])

    console.print(table)

    export_excel(total, proyecto)

if __name__ == "__main__":
    main()
