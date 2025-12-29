"""
Configuración gRPC para resolver problemas de DNS en Docker
Este archivo fuerza a gRPC a usar el resolver nativo en lugar de c-ares
"""
import os
import grpc

# Forzar IPv4 y deshabilitar IPv6 (causa problemas DNS en Docker)
os.environ['GRPC_DNS_RESOLVER'] = 'native'
os.environ['GRPC_VERBOSITY'] = 'ERROR'  # Reducir verbosidad en producción
os.environ['GRPC_ENABLE_FORK_SUPPORT'] = '1'

# Deshabilitar IPv6 para evitar timeouts
try:
    import socket
    old_getaddrinfo = socket.getaddrinfo
    
    def new_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        """Wrapper que fuerza IPv4 (AF_INET) en lugar de IPv6"""
        # Forzar AF_INET (IPv4) en lugar de AF_UNSPEC (cualquiera)
        return old_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
    
    socket.getaddrinfo = new_getaddrinfo
    print("✅ gRPC configurado para usar IPv4 únicamente")
except Exception as e:
    print(f"⚠️  No se pudo forzar IPv4: {e}")
