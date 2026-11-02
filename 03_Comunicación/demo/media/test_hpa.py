"""Script de prueba de carga para evidenciar el Autoscaling (HPA) del servicio Media.

Genera peticiones concurrentes para elevar el uso de CPU por encima del 50% del request (50m)
y gatillar el escalamiento horizontal en Kubernetes.
"""
import argparse
import concurrent.futures
import time
import httpx


def hit_health(url: str):
    try:
        response = httpx.get(url, timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Prueba de carga para HPA")
    parser.add_argument("--url", default="http://media.134.199.176.3.nip.io/health",
                        help="URL del endpoint /health de Media (vía Ingress o port-forward)")
    parser.add_argument("--workers", type=int, default=25, help="Hilos concurrentes")
    parser.add_argument("--duration", type=int, default=120, help="Duración en segundos")
    args = parser.parse_args()

    print(f"[*] Iniciando prueba de carga contra: {args.url}")
    print(f"[*] Hilos concurrentes: {args.workers} durante {args.duration}s")
    print("[*] Revisa el escalamiento en Freelens o ejecutando:")
    print("    kubectl get hpa media-hpa --watch\n")

    start = time.time()
    total_reqs = 0
    success_reqs = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        while time.time() - start < args.duration:
            futures = [executor.submit(hit_health, args.url) for _ in range(args.workers)]
            for f in concurrent.futures.as_completed(futures):
                total_reqs += 1
                if f.result():
                    success_reqs += 1
            elapsed = int(time.time() - start)
            print(f"\rEnviadas: {total_reqs} reqs | Exitosas: {success_reqs} | Tiempo: {elapsed}/{args.duration}s", end="")

    print(f"\n[+] Prueba completada. Total: {total_reqs} peticiones.")


if __name__ == "__main__":
    main()
