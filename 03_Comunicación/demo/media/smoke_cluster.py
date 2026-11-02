"""Prueba de flujo integrado contra el chat base en Kubernetes.

Se ejecuta dentro del cluster (o vía kubectl exec) para comunicarse con:
- users: http://users.servicios-base.svc.cluster.local:8000
- channels: http://channels.servicios-base.svc.cluster.local:8000
- media: http://localhost:8000 (o la URL de Media)
"""
import hashlib
import os
import sys
from uuid import uuid4
import httpx

USERS_URL = os.getenv("USERS_URL", "http://users.servicios-base.svc.cluster.local:8000")
CHANNELS_URL = os.getenv("CHANNELS_URL", "http://channels.servicios-base.svc.cluster.local:8000")
MEDIA_URL = os.getenv("MEDIA_URL", "http://localhost:8000")

def main():
    print("=" * 60)
    print(" INICIANDO FLUJO INTEGRADO CONTRA EL CHAT BASE EN K8S")
    print("=" * 60)
    print(f"[*] USERS:    {USERS_URL}")
    print(f"[*] CHANNELS: {CHANNELS_URL}")
    print(f"[*] MEDIA:    {MEDIA_URL}")
    print("-" * 60)

    with httpx.Client(timeout=10) as client:
        # 1. Crear usuarios en el servicio del núcleo (users)
        r_u1 = client.post(f"{USERS_URL}/api/v1/users", json={"display_name": "Estudiante Uploader"})
        assert r_u1.status_code == 201, f"Error creando usuario 1: {r_u1.text}"
        user1_id = r_u1.json()["id"]
        print(f"[+] Usuario 1 creado en el núcleo: {user1_id}")

        r_u2 = client.post(f"{USERS_URL}/api/v1/users", json={"display_name": "Estudiante Reader"})
        assert r_u2.status_code == 201, f"Error creando usuario 2: {r_u2.text}"
        user2_id = r_u2.json()["id"]
        print(f"[+] Usuario 2 creado en el núcleo: {user2_id}")

        # 2. Crear canal en el servicio del núcleo (channels)
        channel_name = f"demo-k8s-{uuid4().hex[:6]}"
        r_ch = client.post(f"{CHANNELS_URL}/api/v1/channels", json={"name": channel_name})
        assert r_ch.status_code == 201, f"Error creando canal: {r_ch.text}"
        channel_id = r_ch.json()["id"]
        print(f"[+] Canal creado en el núcleo: {channel_name} ({channel_id})")

        # 3. Subir archivo al microservicio Media
        payload = b"%PDF-1.4\nDemostracion Microservicio Media en Kubernetes\n%%EOF"
        expected_sha = hashlib.sha256(payload).hexdigest()
        files = {"file": ("entrega_final.pdf", payload, "application/pdf")}
        headers_u1 = {"X-User-Id": user1_id}
        headers_u2 = {"X-User-Id": user2_id}

        r_att = client.post(f"{MEDIA_URL}/api/v1/channels/{channel_id}/attachments",
                            headers=headers_u1, files=files)
        assert r_att.status_code == 201, f"Error subiendo adjunto: {r_att.text}"
        att = r_att.json()
        print(f"[+] Archivo PDF subido a Media:")
        print(f"    - ID: {att['id']}")
        print(f"    - SHA-256: {att['sha256']}")
        print(f"    - Tamaño: {att['size_bytes']} bytes")
        assert att["sha256"] == expected_sha, "El hash SHA-256 no coincide"

        # 4. Descargar archivo usando el segundo usuario
        download_url = f"{MEDIA_URL}{att['download_url']}"
        r_down = client.get(download_url, headers=headers_u2)
        assert r_down.status_code == 200, f"Error descargando: {r_down.text}"
        assert r_down.content == payload, "El contenido descargado no coincide con el original"
        print(f"[+] Archivo descargado exitosamente por Usuario 2 ({len(r_down.content)} bytes)")

        # 5. Consultar galería del canal
        r_gal = client.get(f"{MEDIA_URL}/api/v1/channels/{channel_id}/attachments?category=DOCUMENT",
                           headers=headers_u2)
        assert r_gal.status_code == 200, f"Error en galería: {r_gal.text}"
        gallery = r_gal.json()
        assert any(item["id"] == att["id"] for item in gallery["items"])
        print(f"[+] Galería de adjuntos validada ({len(gallery['items'])} items)")

        # 6. Validar cuota del canal
        r_quota = client.get(f"{MEDIA_URL}/api/v1/channels/{channel_id}/quota", headers=headers_u1)
        assert r_quota.status_code == 200
        quota = r_quota.json()
        print(f"[+] Cuota del canal validada: {quota['used_bytes']} bytes usados (Límite: {quota['limit_bytes']} bytes)")

        # 7. Intentar borrar con un usuario que no es el uploader (debe fallar 403)
        r_del_fail = client.delete(f"{MEDIA_URL}/api/v1/attachments/{att['id']}", headers=headers_u2)
        assert r_del_fail.status_code == 403, "Debería rechazar borrado por usuario no propietario"
        print("[+] Control de borrado verificado: Usuario 2 no puede borrar archivo de Usuario 1 (403 Forbidden)")

        # 8. Borrar con el propietario (debe ser 204)
        r_del_ok = client.delete(f"{MEDIA_URL}/api/v1/attachments/{att['id']}", headers=headers_u1)
        assert r_del_ok.status_code == 204
        print("[+] Archivo eliminado por Usuario 1 (204 No Content)")

        # 9. Verificar liberación de cuota
        r_quota_after = client.get(f"{MEDIA_URL}/api/v1/channels/{channel_id}/quota", headers=headers_u1).json()
        assert r_quota_after["used_bytes"] == 0
        print("[+] Liberación de cuota confirmada: 0 bytes usados")

    print("=" * 60)
    print(" >>> RESULTADO: FLUJO INTEGRADO 100% EXITOSO CONTRA EL CORE <<<")
    print("=" * 60)

if __name__ == "__main__":
    main()
