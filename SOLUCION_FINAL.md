# ✅ SOLUCIÓN APLICADA - Instrucciones para el servidor

## 🎉 BUENAS NOTICIAS

El diagnóstico confirmó que **tu servidor SÍ tiene acceso a Google**:
```
✅ PING: 172.217.165.202 - 22.7 ms
✅ CURL: HTTP/2 404 (conexión exitosa)
```

El problema era que **Docker no estaba usando el DNS correcto**.

---

## 🔧 CAMBIOS APLICADOS

1. ✅ Agregado `tabulate` a requirements.txt (fix tablas)
2. ✅ Configurado DNS explícito en docker-compose.yml:
   - Google DNS: 8.8.8.8, 8.8.4.4
   - Cloudflare DNS: 1.1.1.1

---

## 🚀 PASOS FINALES EN EL SERVIDOR

### 1. Actualizar código desde GitHub

```bash
cd ~/lab-ai/lab-IA
git pull origin main
```

**Deberías ver:**
```
Updating 300dcb0..83cb64f
Fast-forward
 docker-compose.yml | 4 ++++
 requirements.txt   | 1 +
 2 files changed, 5 insertions(+)
```

### 2. Reconstruir contenedores con nuevos cambios

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

⏱️ **Esto tomará 2-4 minutos** (instalando tabulate y reconstruyendo)

### 3. Verificar que los servicios estén saludables

```bash
docker compose ps
```

**Debe mostrar:**
```
NAME             STATUS         PORTS
labia_postgres   Up (healthy)   0.0.0.0:5433->5432/tcp
labia_app        Up (healthy)   0.0.0.0:8010->8010/tcp
```

### 4. Probar conectividad desde DENTRO del contenedor

```bash
docker compose exec app ping -c 3 generativelanguage.googleapis.com
```

**Debe responder:**
```
64 bytes from ... time=22.x ms
```

Si falla, ejecuta:
```bash
docker compose exec app cat /etc/resolv.conf
```

Debe mostrar:
```
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
```

### 5. Ejecutar la vectorización (CRÍTICO)

```bash
docker compose exec app python ingest.py --reset
```

**Cuando pregunte:** `¿Estás seguro de continuar? (escriba 'SI' para confirmar):`  
**Escribe:** `SI` (en mayúsculas)

⏱️ **Espera 5-10 minutos** (44 PDFs con tablas)

**Deberías ver:**
```
📄 [1/44] LLCII05 Instructivo de Medición...
  ✓ Extraído: 4327 caracteres, 2 tablas
  🔢 Unidades normalizadas: 20
  📑 Secciones detectadas: ['INICIO']
  ✓ Generados 5 chunks
  ✓ 2 tablas procesadas  ← YA NO debe decir "Missing tabulate"
  💾 Generando embeddings para 7 chunks...
  ✅ Almacenados 7 chunks (2 tablas)
```

**Al final debe decir:**
```
================================================================================
✅ INGESTA COMPLETADA
================================================================================
📊 Total PDFs procesados: 44
📝 Total chunks creados: ~438
📋 Total tablas procesadas: ~170
```

### 6. Verificar que se crearon los chunks en la base de datos

```bash
docker compose exec postgres psql -U postgres -d labia_db -c "SELECT COUNT(*) FROM langchain_pg_embedding;"
```

**Debe retornar:**
```
 count 
-------
   438
(1 row)
```

### 7. Probar el chatbot

**Desde el navegador:**
```
http://192.168.8.27:8010
```

**Pregunta de prueba:**
```
¿Cómo se calibra el pH metro?
```

**Debe responder** con procedimientos detallados del instructivo LLCCI13.

---

## 🔍 SI AÚN FALLA LA INGESTA

### Error: "DNS resolution failed" persiste

```bash
# Verificar DNS dentro del contenedor
docker compose exec app cat /etc/resolv.conf

# Verificar conectividad
docker compose exec app ping -c 3 8.8.8.8
docker compose exec app ping -c 3 generativelanguage.googleapis.com

# Ver logs detallados
docker compose logs -f app
```

### Si el DNS no se aplicó:

Edita manualmente `docker-compose.yml` en el servidor y asegúrate que tenga:

```yaml
  app:
    dns:
      - 8.8.8.8
      - 8.8.4.4
      - 1.1.1.1
```

Luego:
```bash
docker compose down
docker compose up -d
```

---

## 📊 CHECKLIST FINAL

- [ ] `git pull` ejecutado
- [ ] `docker compose build` completado
- [ ] Ambos contenedores "healthy"
- [ ] Ping funciona desde el contenedor
- [ ] `ingest.py --reset` ejecutado sin errores DNS
- [ ] 438 chunks verificados en PostgreSQL
- [ ] Chatbot accesible en http://192.168.8.27:8010
- [ ] Chatbot responde correctamente a preguntas

---

## ✅ ESTADO FINAL ESPERADO

```bash
docker compose ps
```
```
NAME             STATUS
labia_postgres   Up (healthy)
labia_app        Up (healthy)
```

```bash
docker compose exec postgres psql -U postgres -d labia_db -c "SELECT COUNT(*) FROM langchain_pg_embedding;"
```
```
 count 
-------
   438
```

```
Navegador: http://192.168.8.27:8010
Pregunta: ¿Cómo se mide el pH?
Respuesta: [Procedimiento detallado de LLCCI02]
```

---

## 🎯 PRÓXIMOS PASOS

1. Ejecuta los comandos en orden
2. Comparte el resultado de la ingesta
3. Si hay algún error, comparte los logs completos

**¡Ya casi está listo! 🚀**
