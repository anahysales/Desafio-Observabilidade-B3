import concurrent.futures
import time
import urllib.request
import urllib.error

# URL da nossa API containerizada
URL = "http://127.0.0.1:8000/stream/authorize?user_id=usr_test_rush&movie_id=mov_blockbuster_2026"

def make_request(i):
    try:
        start_time = time.time()
        req = urllib.request.Request(URL)
        with urllib.request.urlopen(req) as response:
            status = response.status
            duration = time.time() - start_time
            return (status, duration)
    except urllib.error.HTTPError as e:
        return (e.code, 0)
    except Exception as e:
        return (500, 0)

def run_load_test(total_requests=100, concurrency=10):
    print(f"🚀 Iniciando teste de carga: {total_requests} requisições com concorrência de {concurrency}...")
    success_count = 0
    error_count = 0
    
    start_total = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(make_request, i) for i in range(total_requests)]
        for future in concurrent.futures.as_completed(futures):
            status, duration = future.result()
            if status == 200:
                success_count += 1
            else:
                error_count += 1

    total_time = time.time() - start_total
    print("\n📊 --- RESULTADOS DO TESTE DE CARGA ---")
    print(f"Total de Requisições: {total_requests}")
    print(f"Sucessos (200 OK): {success_count}")
    print(f"Erros / Falhas: {error_count}")
    print(f"Tempo Total: {total_time:.2f} segundos")
    print("----------------------------------------\n")

if __name__ == "__main__":
    run_load_test(total_requests=150, concurrency=15)