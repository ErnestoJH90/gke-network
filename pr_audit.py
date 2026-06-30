import requests
import pandas as pd
from datetime import datetime
import base64
import os

# ========= CONFIG =========
ORG = "TuOrganizacion"  # Cambiar por tu organización en Azure DevOps
PROJECT = "tu_proyecto"  # Cambiar por tu proyecto en Azure DevOps
PAT = "tu_personal_access_token"  # Cambiar por tu Personal Access Token (PAT) de Azure DevOps

if not PAT:
    raise Exception("Falta configurar el PAT en variable AZDO_PAT")

auth = base64.b64encode(f":{PAT}".encode()).decode()

HEADERS = {
    "Authorization": f"Basic {auth}"
}

BASE_URL = f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/git"


# ========= HELPERS =========
def limpiar_rama(rama):
    return rama.replace("refs/heads/", "") if rama else ""


def safe_get(url):
    try:
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Error: {e}")
        return {}


def obtener_repositorios():
    url = f"{BASE_URL}/repositories?api-version=7.0"
    return safe_get(url).get("value", [])


# ========= RANGO PERSONALIZADO =========
def rango_personalizado():
    print("\nFecha inicio (YYYY-MM-DD): ")
    inicio = datetime.strptime(input("Inicio: "), "%Y-%m-%d")

    print("Fecha fin (YYYY-MM-DD): ")
    fin = datetime.strptime(input("Fin: "), "%Y-%m-%d")

    return inicio, fin


# ========= OBTENER PRs =========
def obtener_prs(repo_id, inicio, fin):
    resultados = []
    skip = 0
    top = 100

    while True:
        url = (
            f"{BASE_URL}/repositories/{repo_id}/pullrequests"
            f"?searchCriteria.status=all"
            f"&$top={top}&$skip={skip}&api-version=7.0"
        )

        data = safe_get(url)
        prs = data.get("value", [])

        if not prs:
            break

        for pr in prs:
            fecha_creacion = pd.to_datetime(
                pr["creationDate"]
            ).tz_localize(None)

            if not (inicio <= fecha_creacion <= fin):
                continue

            fecha_cierre = pd.to_datetime(
                pr.get("closedDate"), errors='coerce'
            )

            if pd.notna(fecha_cierre):
                fecha_cierre = fecha_cierre.tz_localize(None)

            revisores = [r["displayName"] for r in pr.get("reviewers", []) if r["vote"] != 0]

            resultados.append({
                "ID": pr["pullRequestId"],
                "Titulo": pr["title"],
                "Estado": pr["status"],
                "Repositorio": pr["repository"]["name"],
                "Rama Origen": limpiar_rama(pr["sourceRefName"]),
                "Rama Destino": limpiar_rama(pr["targetRefName"]),
                "Autor": pr["createdBy"]["displayName"],
                "Revisores": ", ".join(revisores),
                "Fecha Creacion": fecha_creacion,
                "Fecha Cierre": fecha_cierre
            })

        skip += top

    return resultados


# ========= REPORTE ENTERPRISE =========
def generar_reporte(inicio, fin):
    print(f"\n🟢 Auditoría de {inicio.date()} a {fin.date()}")

    repos = obtener_repositorios()
    data = []

    for repo in repos:
        print(f"Repo: {repo['name']}")
        data.extend(obtener_prs(repo["id"], inicio, fin))

    df = pd.DataFrame(data)

    if df.empty:
        print("⚠️ Sin datos")
        return

    # ========= MÉTRICAS =========
    df["Duracion"] = (
        df["Fecha Cierre"] - df["Fecha Creacion"]
    ).dt.days

    df["Mes"] = df["Fecha Creacion"].dt.to_period("M")

    # ✅ SLA (más de 3 días)
    df["SLA Incumplido"] = df["Duracion"] > 3

    # ✅ PRs activos envejecidos
    hoy = pd.Timestamp.now()
    activos = df[df["Estado"] == "active"].copy()
    activos["Dias Abierto"] = (hoy - activos["Fecha Creacion"]).dt.days

    # ✅ PR sin revisión
    sin_review = df[df["Revisores"] == ""]

    # ========= KPIs =========
    resumen_estado = df["Estado"].value_counts()
    resumen_repo = df["Repositorio"].value_counts()
    resumen_autor = df["Autor"].value_counts()
    resumen_mes = df["Mes"].value_counts()
    top_reviewers = (
        df["Revisores"]
        .str.split(", ")
        .explode()
        .value_counts()
    )

    # ========= EXPORT =========
    archivo = f"Auditoria_ENTERPRISE_{inicio.date()}_{fin.date()}.xlsx"

    with pd.ExcelWriter(archivo, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Detalle", index=False)
        resumen_estado.to_frame("Cantidad").to_excel(writer, sheet_name="Estados")
        resumen_repo.to_frame("Cantidad").to_excel(writer, sheet_name="Repos")
        resumen_autor.to_frame("Cantidad").to_excel(writer, sheet_name="Autores")
        resumen_mes.to_frame("Cantidad").to_excel(writer, sheet_name="PorMes")
        top_reviewers.to_frame("Cantidad").to_excel(writer, sheet_name="Reviewers")

        activos.to_excel(writer, sheet_name="Activos_Envejecidos", index=False)
        sin_review.to_excel(writer, sheet_name="Sin_Review", index=False)

    print(f"\n✅ Reporte PullRequest generado: {archivo}")

    print("\n📊 KPIs CLAVE")
    print(resumen_estado)


# ========= MAIN =========
if __name__ == "__main__":
    inicio, fin = rango_personalizado()
    generar_reporte(inicio, fin)
