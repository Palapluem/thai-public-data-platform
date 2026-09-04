# Operational Scripts

Operational helpers belong here only when they are part of the reproducible
project workflow. The current entry points live in the installable package
(`python -m thai_data_platform`) so local CLI and Airflow use the same logic.
Do not put credentials, local machine paths or generated data in this directory.
