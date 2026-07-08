# Cabeceras comunes de reverse-proxy hacia el backend FastAPI (uvicorn corre
# con --proxy-headers --forwarded-allow-ips=*, así respeta estos valores).
proxy_http_version 1.1;
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $fwd_proto;
proxy_set_header Upgrade           $http_upgrade;
proxy_set_header Connection        "upgrade";
proxy_read_timeout 120s;
