import socket
import threading
import select
import logging
import sys
import os

# Configurar o logging para desativar a exibição no console
logging.basicConfig(level=logging.CRITICAL)

# Lista de domínios bloqueados (adicionar mais conforme necessário)
blocked_domains = [
    "googleadservices.com",
    "googlesyndication.com",
    "doubleclick.net",
    "audio-fa.scdn.co"
    "spclient.wg.spotify.com",
    "adclick.g.doublecklick.net",
    "pagead46.l.doubleclick.net",
    "video-ad-stats.googlesyndication.com",
    "pagead2.googlesyndication.com",
    "pagead-googlehosted.l.google.com",
    "partnerad.l.doubleclick.net",
    "prod.spotify.map.fastlylb.net",
    "tpc.googlesyndication.com",
    "googleads.g.doubleclick.net",
    "omaze.com",
    "bounceexchange.com",
    "gads.pubmatic.com",
    "securepubads.g.doubleclick.net",
    "pubads.g.doubleclick.net",
    "audio2.spotify.com",
    "crashdump.spotify.com",
    "log.spotify.com",
    "analytics.spotify.com",
    "ads-fa.spotify.com",
    "audio-ec.spotify.com",
    "ads.pubmatic.com",
    "sto3.spotify.com",
    "partner.googleadservices.com",
    "audio-sp-tyo.spotify.com",
    "audio-sp-ash.spotify.com",
    "audio-fa.spotify.com",
    "audio-sp.spotify.com",
    "heads-fab.spotify.com",
    "ads.yahoo.com",
    "ade.googlesyndication.com"
]

def handle_client(client_socket, client_address):
    try:
        request = client_socket.recv(4096)
        
        if not request:
            client_socket.close()
            return
        
        first_line = request.decode().split('\n')[0]
        
        if not first_line.strip():
            client_socket.close()
            return
        
        method, path, version = first_line.split()

        # Verificação de requisição para a mensagem de boas-vindas
        if method == "GET" and path == "/":
            welcome_message = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/html\r\n"
                "Connection: close\r\n\r\n"
                "<html><body><h1>Bem-vindo ao Proxy!</h1><p>Este é o servidor proxy em execução.</p></body></html>"
            )
            client_socket.sendall(welcome_message.encode())
            client_socket.close()
            return

        # Verificação da requisição CONNECT
        if method == "CONNECT":
            host, port = path.split(':')
            port = int(port)
            
            # Verificar se o domínio está bloqueado
            if is_domain_blocked(host):
                block_message = (
                    "HTTP/1.1 403 Forbidden\r\n"
                    "Content-Type: text/html\r\n"
                    "Connection: close\r\n\r\n"
                    "<html><body><h1>Acesso Bloqueado</h1><p>O domínio foi bloqueado pelo proxy.</p></body></html>"
                )
                client_socket.sendall(block_message.encode())
                client_socket.close()
                return
            
            try:
                server_socket = socket.socket(socket.AF_INET6 if ':' in host else socket.AF_INET, socket.SOCK_STREAM)
                server_socket.connect((host, port))
                
                client_socket.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                
                threading.Thread(target=forward, args=(client_socket, server_socket)).start()
                threading.Thread(target=forward, args=(server_socket, client_socket)).start()
            except socket.error as e:
                logging.error(f"Erro ao conectar com {host}: {e}")
                client_socket.close()
        else:
            host = None
            for line in request.decode().split('\r\n'):
                if line.startswith("Host:"):
                    host = line.split(" ")[1]
                    break
            
            # Verificar se o domínio está bloqueado
            if is_domain_blocked(host):
                block_message = (
                    "HTTP/1.1 403 Forbidden\r\n"
                    "Content-Type: text/html\r\n"
                    "Connection: close\r\n\r\n"
                    "<html><body><h1>Acesso Bloqueado</h1><p>O domínio foi bloqueado pelo proxy.</p></body></html>"
                )
                client_socket.sendall(block_message.encode())
                client_socket.close()
                return
            
            if not host:
                client_socket.close()
                return
            
            try:
                server_socket = socket.socket(socket.AF_INET6 if ':' in host else socket.AF_INET, socket.SOCK_STREAM)
                server_socket.connect((host, 80))
                server_socket.sendall(request)
                forward(server_socket, client_socket)
            except socket.error as e:
                logging.error(f"Erro ao conectar com {host}: {e}")
            finally:
                client_socket.close()

    except ValueError as e:
        logging.error(f"Erro ao processar a requisição: {e}")
        client_socket.close()
    except socket.error as e:
        logging.error(f"Erro de socket: {e}")
        client_socket.close()

def forward(source, destination):
    try:
        while True:
            try:
                data = source.recv(4096)
                if len(data) == 0:
                    break
                destination.sendall(data)
            except socket.error as e:
                logging.error(f"Erro ao receber/enviar dados: {e}")
                break
    finally:
        source.close()
        destination.close()

def is_domain_blocked(host):
    # Verificar se o domínio está na lista de bloqueados
    for blocked in blocked_domains:
        if blocked in host:
            return True
    return False

def start_proxy():
    try:
        # IPv6 server
        server_ipv6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        server_ipv6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Permitir reutilização de endereço
        server_ipv6.bind(('::', 8100))
        server_ipv6.listen(5)
        print("Proxy Server running on [::]:8100...")

        # IPv4 server
        server_ipv4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_ipv4.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Permitir reutilização de endereço
        server_ipv4.bind(('0.0.0.0', 8100))
        server_ipv4.listen(5)
        print("Proxy Server also running on 0.0.0.0:8100...")

        inputs = [server_ipv6, server_ipv4]

        while True:
            readable, _, _ = select.select(inputs, [], [], 1)  # Timeout de 1 segundo para permitir interrupção
            
            for s in readable:
                if s == server_ipv6:
                    client_socket, client_address = server_ipv6.accept()
                    client_handler = threading.Thread(target=handle_client, args=(client_socket, client_address))
                    client_handler.start()
                elif s == server_ipv4:
                    client_socket, client_address = server_ipv4.accept()
                    client_handler = threading.Thread(target=handle_client, args=(client_socket, client_address))
                    client_handler.start()
    
    except KeyboardInterrupt:
        print("\nProxy Server interrompido.")
    finally:
        server_ipv6.close()
        server_ipv4.close()
        print("Servidores encerrados.")
        os._exit(0)

if __name__ == "__main__":
    start_proxy()
