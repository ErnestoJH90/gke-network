import requests
import pandas as pd
from datetime import datetime, timedelta
import base64
import getpass
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side

# ========= CONFIG =========
ORG = "Tu_Organizacion"
PROJECT = "Tu_Proyecto"
PAT = "Tu_PAT_aqui"  # Personal Access Token de Azure DevOps

if not PAT:
    raise Exception("Falta configurar el PAT en variable AZDO_PAT")

auth = base64.b64encode(f":{PAT}".encode()).decode()

HEADERS = {
    "Authorization": f"Basic {auth}",
    "Content-Type": "application/json"
}

BASE_URL = f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/git"
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

ENV_BRANCHES = ["develop", "qa", "release", "master"]


# ========= RANGO =========
def obtener_rango(periodo):
    hoy = datetime.now()

    rangos = {
        "diario": 1,
        "semanal": 7,
        "quincenal": 15,
        "mensual": 30,
        "3meses": 90,
        "6meses": 180,
        "12meses": 365
    }

    dias = rangos.get(periodo, 7)
    return hoy - timedelta(days=dias), hoy


# ========= UTIL =========
def limpiar_rama(rama):
    return rama.replace("refs/heads/", "") if rama else ""


def parse_azure_datetime(value):
    if not value:
        return pd.NaT

    dt = pd.to_datetime(value, errors="coerce")
    if pd.isna(dt):
        return pd.NaT

    if dt.tzinfo is not None:
        return dt.tz_convert(None)

    return dt


def obtener_entorno_rama(rama):
    rama_limpia = limpiar_rama(rama)
    if not rama_limpia:
        return "otro"

    rama_limpia_lower = rama_limpia.lower()
    for entorno in ENV_BRANCHES:
        if (
            rama_limpia_lower == entorno
            or rama_limpia_lower.startswith(f"{entorno}/")
            or f"/{entorno}" in rama_limpia_lower
            or rama_limpia_lower.endswith(f"-{entorno}")
            or rama_limpia_lower.startswith(f"{entorno}-")
        ):
            return entorno

    return rama_limpia


# ========= REQUEST SEGURO =========
def safe_get(url):
    try:
        r = SESSION.get(url, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Error en request: {e}")
        return {}


# ========= PRs =========
def obtener_prs(fecha_inicio, fecha_fin):
    resultados = []
    skip = 0
    top = 100

    while True:
        url = (
            f"{BASE_URL}/pullrequests"
            f"?searchCriteria.status=all"
            f"&$top={top}&$skip={skip}&api-version=7.0"
        )

        data = safe_get(url)
        prs = data.get("value", [])

        if not prs:
            break

        for pr in prs:
            fecha_creacion = parse_azure_datetime(pr["creationDate"])

            if not (fecha_inicio <= fecha_creacion <= fecha_fin):
                continue

            revisores = ", ".join([
                r["displayName"]
                for r in pr.get("reviewers", [])
            ])

            fecha_cierre = parse_azure_datetime(pr.get("closedDate"))

            rama_origen = limpiar_rama(pr["sourceRefName"])
            rama_destino = limpiar_rama(pr["targetRefName"])

            resultados.append({
                "ID": pr["pullRequestId"],
                "Titulo": pr["title"],
                "Estado": pr["status"],
                "Repositorio": pr["repository"]["name"],
                "Rama Origen": rama_origen,
                "Rama Destino": rama_destino,
                "Entorno Origen": obtener_entorno_rama(rama_origen),
                "Entorno Destino": obtener_entorno_rama(rama_destino),
                "Autor": pr["createdBy"]["displayName"],
                "Revisores": revisores,
                "Fecha Creacion": fecha_creacion,
                "Fecha Cierre": fecha_cierre
            })

        skip += top

    return resultados


# ========= REPORTE =========
def generar_reporte(periodo):
    inicio, fin = obtener_rango(periodo)
    inicio_ejecucion = datetime.now()
    usuario = getpass.getuser()

    print(f"\n🟢 Auditando de {inicio.date()} a {fin.date()}")
    print(f"Inicio ejecución: {inicio_ejecucion.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Usuario: {usuario}")
    print(f"Obteniendo PRs para el proyecto {PROJECT}...\n")

    total = obtener_prs(inicio, fin)
    fin_ejecucion = datetime.now()
    df = pd.DataFrame(total)

    if df.empty:
        print("⚠️ Sin datos")
        print(f"Fin ejecución: {fin_ejecucion.strftime('%Y-%m-%d %H:%M:%S')}")
        return

    df["Auditado Por"] = usuario
    df["Inicio Auditoria"] = inicio_ejecucion
    df["Fin Auditoria"] = fin_ejecucion

    # ========= MÉTRICAS =========
    ahora = pd.Timestamp.now()
    df["Duracion (minutos)"] = df.apply(
        lambda row: ((row["Fecha Cierre"] if pd.notna(row["Fecha Cierre"]) else ahora) - row["Fecha Creacion"]).total_seconds() / 60,
        axis=1
    )

    resumen_estado = df["Estado"].value_counts()
    resumen_repo = df["Repositorio"].value_counts()
    resumen_autor = df["Autor"].value_counts()
    resumen_rama_origen = df["Rama Origen"].value_counts()
    resumen_rama_destino = df["Rama Destino"].value_counts()
    resumen_entorno_origen = df["Entorno Origen"].value_counts()
    resumen_entorno_destino = df["Entorno Destino"].value_counts()

    total_prs = len(df)
    prs_abiertas = int(df["Fecha Cierre"].isna().sum())
    prs_cerradas = total_prs - prs_abiertas
    prs_sin_review = int((df["Revisores"] == "").sum())
    tiempo_promedio = df.loc[df["Fecha Cierre"].notna(), "Duracion (minutos)"].mean()

    resumen_ejecutivo = pd.DataFrame([
        ["Reporte", f"Auditoría PR {periodo}"],
        ["Proyecto", PROJECT],
        ["Usuario", usuario],
        ["Inicio Ejecución", inicio_ejecucion],
        ["Fin Ejecución", fin_ejecucion],
        ["Rango Inicio", inicio],
        ["Rango Fin", fin],
        ["Total PRs", total_prs],
        ["PRs cerradas", prs_cerradas],
        ["PRs abiertas", prs_abiertas],
        ["PRs sin revisión", prs_sin_review],
        ["Duración promedio (min)", round(tiempo_promedio, 1) if not pd.isna(tiempo_promedio) else "N/A"]
    ], columns=["Métrica", "Valor"])

    metadata = pd.DataFrame([
        {
            "Proyecto": PROJECT,
            "Periodo": periodo,
            "Rango Inicio": inicio,
            "Rango Fin": fin,
            "Inicio Ejecucion": inicio_ejecucion,
            "Fin Ejecucion": fin_ejecucion,
            "Usuario": usuario,
            "Total PRs": total_prs
        }
    ])

    archivo = f"Auditoria_PR_{periodo}_{datetime.now().strftime('%Y%m%d')}.xlsx"

    with pd.ExcelWriter(archivo, engine='openpyxl') as writer:
        resumen_ejecutivo.to_excel(writer, sheet_name="Resumen Ejecutivo", index=False)
        metadata.to_excel(writer, sheet_name="Metadata", index=False)
        df.to_excel(writer, sheet_name="Detalle", index=False)
        resumen_estado.to_frame("Cantidad").to_excel(writer, sheet_name="Estados")
        resumen_repo.to_frame("Cantidad").to_excel(writer, sheet_name="Repositorios")
        resumen_autor.to_frame("Cantidad").to_excel(writer, sheet_name="Autores")
        resumen_rama_origen.to_frame("Cantidad").to_excel(writer, sheet_name="Ramas_Origen")
        resumen_rama_destino.to_frame("Cantidad").to_excel(writer, sheet_name="Ramas_Destino")
        resumen_entorno_origen.to_frame("Cantidad").to_excel(writer, sheet_name="Entornos_Origen")
        resumen_entorno_destino.to_frame("Cantidad").to_excel(writer, sheet_name="Entornos_Destino")

        wb = writer.book
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
        border = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))
        center_align = Alignment(horizontal="center", vertical="center")

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            for cell in next(ws.iter_rows(min_row=1, max_row=1)):
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = center_align
                cell.border = border
            for col in ws.columns:
                max_length = 0
                col_letter = col[0].column_letter
                for cell in col:
                    try:
                        cell_value = str(cell.value)
                    except Exception:
                        cell_value = ""
                    max_length = max(max_length, len(cell_value))
                ws.column_dimensions[col_letter].width = min(max_length + 2, 40)

        ws_summary = wb["Resumen Ejecutivo"]
        for row in ws_summary.iter_rows(min_row=2, max_col=2, max_row=ws_summary.max_row):
            row[0].font = Font(bold=True)
            row[0].alignment = Alignment(horizontal="right")

    print(f"\n✅ Reporte generado: {archivo}")

    print("\n📊 Estados:")
    print(resumen_estado)


# ========= MAIN =========
if __name__ == "__main__":
    print("\nSelecciona periodo:")
    print("1 - Diario")
    print("2 - Semanal")
    print("3 - Quincenal")
    print("4 - Mensual")
    print("5 - 3 Meses")
    print("6 - 6 Meses")
    print("7 - 12 Meses")

    opcion = input("Opción: ")

    mapa = {
        "1": "diario",
        "2": "semanal",
        "3": "quincenal",
        "4": "mensual",
        "5": "3meses",
        "6": "6meses",
        "7": "12meses"
    }

    generar_reporte(mapa.get(opcion, "semanal"))
