# Auditoría de Pull Requests para Azure DevOps
# Author: Ernesto Jimenez Huitron
# DevOps

PR Audit para Azure DevOps
Descripción
pr_audit.py es una herramienta de auditoría para Azure DevOps que permite recopilar información de Pull Requests (PRs) dentro de un rango de fechas específico. El script consulta la API REST de Azure DevOps para obtener datos de repositorios y PRs, con el objetivo de generar reportes de seguimiento y análisis de actividad de desarrollo. 
Funcionalidades

Consulta repositorios Git de un proyecto en Azure DevOps.
Obtiene Pull Requests dentro de un rango de fechas definido por el usuario. 
Normaliza nombres de ramas eliminando prefijos como refs/heads/. 
Consume la API REST de Azure DevOps utilizando autenticación mediante Personal Access Token (PAT). 
Genera reportes para auditoría y seguimiento de actividad en repositorios. 

Requisitos

Python 3.9+
Librerías:
requests
pandas

Instalación de dependencias:

Configuración

Antes de ejecutar el script, configure los siguientes parámetros:
PythonORG = "TuOrganizacion"PROJECT = "TuProyecto"PAT = "tu_personal_access_token"Show more lines
Donde:

ORG: Nombre de la organización en Azure DevOps.
PROJECT: Nombre del proyecto.
PAT: Personal Access Token con permisos de lectura sobre repositorios y Pull Requests.

Uso

Ejecute el script desde la línea de comandos:
python pr_audit.py

El sistema solicitará un rango de fechas para realizar la auditoría. Posteriormente consultará los repositorios y Pull Requests disponibles para generar el reporte correspondiente.

Flujo General
Usuario
   │
   ▼
Selecciona rango de fechas
   │
   ▼
Obtiene repositorios Azure DevOps
   │
   ▼
Consulta Pull Requests
   │
   ▼
Procesa resultados
   │
   ▼
Genera reporte de auditoría

Objetivo
Facilitar la revisión de actividad en repositorios Azure DevOps, permitiendo identificar Pull Requests creados, revisados y completados durante un período determinado para fines de auditoría, métricas o seguimiento de equipos de desarrollo.

Nota: El archivo actual se encuentra incompleto y requiere ajustes para ejecutarse correctamente, ya que algunas secciones de configuración, autenticación y consultas a la API aparecen truncadas.