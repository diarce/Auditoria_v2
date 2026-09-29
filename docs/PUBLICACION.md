# Publicación de la versión 6.0.0 y retiro de datos identificatorios

Las versiones anteriores del repositorio público contenían URL reales, nombres de plataformas y datos de contacto de comercios. Borrar esos archivos en un commit nuevo no alcanza: el historial de Git los conserva y cualquiera puede consultarlos.

## Opción recomendada: repositorio nuevo sin historial

1. En GitHub, abra *Settings → General → Danger Zone* del repositorio actual y cámbielo a **privado** (o archívelo). Conserve una copia local del historial si la necesita como registro interno.
2. Cree un repositorio público nuevo (puede reutilizar el nombre `Auditoria` después de renombrar el anterior).
3. Desde la carpeta de esta versión:

```bash
git init -b main
git add .
git status                 # confirme que no aparecen data/privado/ ni outputs/
git commit -m "AuditMayorista 6.0.0"
git remote add origin https://github.com/diarce/Auditoria.git
git push -u origin main
git tag -a v6.0.0 -m "Versión usada para el relevamiento"
git push origin v6.0.0
```

## Alternativa: reescribir el historial del repositorio existente

Reemplazar la rama principal por un commit sin historial y forzar la publicación (`git push --force`). Es irreversible para quienes tengan copias y no borra las bifurcaciones (forks) ni las vistas en caché. GitHub documenta el procedimiento y la solicitud de purga de caché en «Removing sensitive data from a repository» (docs.github.com).

## Después de publicar

- Si la aplicación de Streamlit Community Cloud sigue desplegada desde la versión anterior, vuelva a desplegarla desde la nueva o suspéndala.
- Archive la versión etiquetada con DOI (por ejemplo, con la integración entre GitHub y Zenodo) y cite en la tesis la versión y el commit.
- Antes de guardar el cuaderno de Colab en GitHub, borre todas sus salidas.
